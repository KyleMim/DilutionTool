"""
Backfill pipeline: screens the US equity universe, identifies dilution
candidates, enriches with fundamentals + SEC filings, and scores.

Usage:
  python -m backend.pipelines.backfill [--quick] [--max-companies 500] [--resume]
"""
import argparse
import logging
import sys
import time
from datetime import date, timedelta

from sqlalchemy import select
from backend.config import get_config
from backend.database import SessionLocal, create_tables
from backend.models import Company, FundamentalsQuarterly, SecFiling
from backend.services.fmp_client import FMPClient, _date_to_fiscal_period
from backend.services.edgar_client import EdgarClient
from backend.services.scoring import score_company, score_all
from backend.services.filters import is_spac_name
from backend.pipelines.validate import validate_incoming_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def assign_tiers(db_session, scores: list, config) -> dict:
    """Assign tracking tiers by percentile rank and return tier counts."""
    sorted_scores = sorted(scores, key=lambda s: s.composite_score)
    n = len(sorted_scores)
    critical_idx = int(n * config.scoring.critical_percentile / 100)
    watchlist_idx = int(n * config.scoring.watchlist_percentile / 100)

    counts = {"critical": 0, "watchlist": 0, "monitoring": 0}
    for i, score in enumerate(sorted_scores):
        company = db_session.get(Company, score.company_id)
        if i >= critical_idx:
            company.tracking_tier = "critical"
            counts["critical"] += 1
        elif i >= watchlist_idx:
            company.tracking_tier = "watchlist"
            counts["watchlist"] += 1
        else:
            company.tracking_tier = "monitoring"
            counts["monitoring"] += 1
    db_session.commit()
    return counts


def print_top_scores(db_session, scores: list, n: int = 10):
    """Print a summary table of the top N scores."""
    top = sorted(scores, key=lambda s: s.composite_score, reverse=True)[:n]
    if not top:
        return
    print("\n" + "=" * 70)
    print(f"{'Rank':<6}{'Ticker':<10}{'Score':<10}{'Share CAGR':<12}{'FCF Burn':<10}{'Offerings':<10}")
    print("-" * 70)
    for rank, score in enumerate(top, 1):
        company = db_session.get(Company, score.company_id)
        cagr = f"{score.share_cagr_3y:.0%}" if score.share_cagr_3y is not None else "N/A"
        burn = f"{score.fcf_burn_rate:.0%}" if score.fcf_burn_rate is not None else "N/A"
        offerings = score.offering_count_3y if score.offering_count_3y is not None else 0
        print(f"{rank:<6}{company.ticker:<10}{score.composite_score:<10.1f}{cagr:<12}{burn:<10}{offerings:<10}")
    print("=" * 70 + "\n")


def fetch_prices(db_session, fmp_client, scores: list, only_missing: bool = False):
    """Fetch trailing 12-month price changes for scored companies.

    Args:
        only_missing: If True, skip companies that already have price_change_12m
                      (carried forward from previous score). Saves API calls.
    """
    if not fmp_client:
        logger.info("Skipping price fetch (no FMP client)")
        return

    logger.info("Fetching trailing 12-month price changes%s...",
                " (only missing)" if only_missing else "")
    price_updated = 0
    skipped = 0
    for score in scores:
        if only_missing and score.price_change_12m is not None:
            skipped += 1
            continue
        company = db_session.get(Company, score.company_id)
        try:
            pct = fmp_client.get_price_change_12m(company.ticker)
            if pct is not None:
                score.price_change_12m = round(pct, 4)
                price_updated += 1
        except Exception as e:
            logger.warning("Price fetch failed for %s: %s", company.ticker, e)
    db_session.commit()
    logger.info("Updated 12-month price change for %d companies (skipped %d with existing data)",
                price_updated, skipped)


def run_backfill(db_session, fmp_client, edgar_client, config, max_companies=3000, quick_mode=False, resume=False, enrich_only=False, score_only=False):
    """Main backfill pipeline."""

    if score_only:
        # ------------------------------------------------------------------ #
        # Score-only mode: skip Steps 1-3, just rescore + retier
        # No price fetch — score_company() carries forward price_change_12m
        # ------------------------------------------------------------------ #
        logger.info("Score-only mode: rescoring all tracked companies with existing data...")
        company_count = db_session.query(Company).filter(
            Company.tracking_tier.in_(["critical", "watchlist", "monitoring"])
        ).count()
        logger.info("Found %d tracked companies to rescore", company_count)
        if company_count == 0:
            logger.warning("No tracked companies found — database may be empty. Nothing to rescore.")
            return []

        scores = score_all(db_session, config.scoring)
        counts = assign_tiers(db_session, scores, config)
        logger.info("Critical: %d, Watchlist: %d, Monitoring: %d",
                     counts["critical"], counts["watchlist"], counts["monitoring"])
        print_top_scores(db_session, scores)
        return scores

    if enrich_only:
        # ------------------------------------------------------------------ #
        # Enrich-only mode: skip Steps 1 & 2 entirely
        # ------------------------------------------------------------------ #
        logger.info("Enrich-only mode: skipping screening, loading existing candidates...")
        # Include already-promoted companies AND inactive ones that have fundamentals
        # (enriched in a previous run but never scored/promoted)
        promoted = (
            db_session.query(Company)
            .filter(Company.tracking_tier.in_(["critical", "watchlist", "monitoring"]))
            .all()
        )
        enriched_inactive = (
            db_session.query(Company)
            .filter(
                Company.tracking_tier == "inactive",
                Company.id.in_(
                    db_session.query(FundamentalsQuarterly.company_id).distinct()
                ),
            )
            .all()
        )
        candidates = promoted + enriched_inactive
        logger.info("Found %d candidates (%d promoted + %d enriched-inactive)",
                     len(candidates), len(promoted), len(enriched_inactive))
    else:
        # ------------------------------------------------------------------ #
        # Step 1: Pull universe
        # ------------------------------------------------------------------ #
        logger.info("Step 1: Pulling stock universe from FMP...")
        stock_list = fmp_client.get_stock_list()

        # Filter: market_cap > 0
        stock_list = [s for s in stock_list if s.get("market_cap") and s["market_cap"] > 0]
        logger.info("Loaded %d US equities with market cap > 0", len(stock_list))

        # Insert/update into companies table
        for stock in stock_list:
            existing = db_session.query(Company).filter_by(ticker=stock["ticker"]).first()
            if existing:
                existing.name = stock["name"] or existing.name
                existing.sector = stock["sector"] or existing.sector
                existing.exchange = stock["exchange"] or existing.exchange
                existing.market_cap = stock["market_cap"]
            else:
                db_session.add(Company(
                    ticker=stock["ticker"],
                    name=stock["name"] or stock["ticker"],
                    sector=stock.get("sector"),
                    exchange=stock.get("exchange"),
                    market_cap=stock["market_cap"],
                    tracking_tier="inactive",
                ))
        db_session.commit()
        logger.info("Universe synced to database")

        # ------------------------------------------------------------------ #
        # Step 2: Quick screen
        # ------------------------------------------------------------------ #
        logger.info("Step 2: Quick screening for dilution candidates...")
        companies = db_session.query(Company).order_by(Company.market_cap.asc()).all()

        if quick_mode:
            companies = companies[:min(max_companies, 500)]
            logger.info("Quick mode: screening %d companies", len(companies))
        else:
            companies = companies[:max_companies]

        candidates = []
        screened = 0
        to_screen = []

        if resume:
            processed = [c for c in companies if c.tracking_tier in ("critical", "watchlist", "monitoring")]
            cutoff_cap = max((c.market_cap or 0) for c in processed) if processed else 0

            for c in companies:
                if c.tracking_tier in ("critical", "watchlist", "monitoring"):
                    candidates.append(c)
                elif (c.market_cap or 0) <= cutoff_cap:
                    continue
                else:
                    to_screen.append(c)
            logger.info("Resume: %d already processed, %d already screened (skipped), %d new to screen",
                         len(candidates), len(companies) - len(candidates) - len(to_screen), len(to_screen))
        else:
            to_screen = companies

        for i, company in enumerate(to_screen):
            if i % 50 == 0:
                logger.info("Screening progress: %d/%d (candidates so far: %d)", i, len(to_screen), len(candidates))

            # Skip SPACs
            if is_spac_name(company.name):
                company.is_spac = True
                continue

            try:
                income = fmp_client.get_income_statements(company.ticker, limit=8)
                cashflow = fmp_client.get_cashflow_statements(company.ticker, limit=8)

                shares = [
                    r["shares_outstanding_diluted"] for r in income
                    if r.get("shares_outstanding_diluted") and r["shares_outstanding_diluted"] > 0
                ]

                is_candidate = False

                if len(shares) >= 2:
                    oldest = shares[-1]
                    newest = shares[0]
                    num_q = len(shares) - 1
                    if oldest > 0 and num_q > 0:
                        cagr = (newest / oldest) ** (4 / num_q) - 1
                        if cagr > config.scoring.share_cagr_min:
                            is_candidate = True

                neg_fcf = sum(
                    1 for r in cashflow
                    if r.get("free_cash_flow") is not None and r["free_cash_flow"] < 0
                )
                if neg_fcf >= config.scoring.fcf_negative_quarters:
                    is_candidate = True

                if is_candidate:
                    candidates.append(company)

            except Exception as e:
                logger.warning("Error screening %s: %s", company.ticker, e)

            screened += 1

        logger.info("Screened %d companies, %d candidates identified", screened, len(candidates))

    # ------------------------------------------------------------------ #
    # Step 3: Enrich candidates
    # ------------------------------------------------------------------ #
    logger.info("Step 3: Enriching %d candidates with fundamentals + filings...", len(candidates))
    enriched = 0

    for i, company in enumerate(candidates):
        if i % 10 == 0:
            logger.info("Enriching progress: %d/%d", i, len(candidates))

        # In resume mode, skip SEC filings fetch for already-enriched companies
        # but still re-fetch fundamentals to pick up new quarters and corrections
        skip_filings = False
        if resume:
            has_fundamentals = db_session.query(FundamentalsQuarterly).filter_by(company_id=company.id).count() > 0
            if has_fundamentals:
                skip_filings = True

        try:
            # Pull full fundamentals
            fundamentals = fmp_client.get_full_fundamentals(company.ticker, limit=12)

            # Load existing fundamentals for this company (for validation)
            existing_fundamentals = (
                db_session.query(FundamentalsQuarterly)
                .filter_by(company_id=company.id)
                .order_by(FundamentalsQuarterly.fiscal_period.asc())
                .all()
            )

            for record in fundamentals:
                fiscal_period = record.get("fiscal_period", "unknown")

                # Validate incoming record against existing data
                record = validate_incoming_record(
                    ticker=company.ticker,
                    fiscal_period=fiscal_period,
                    incoming=record,
                    existing_fundamentals=existing_fundamentals,
                    market_cap=company.market_cap,
                )

                existing = (
                    db_session.query(FundamentalsQuarterly)
                    .filter_by(company_id=company.id, fiscal_period=fiscal_period)
                    .first()
                )
                if existing:
                    existing.shares_outstanding_diluted = record.get("shares_outstanding")
                    existing.free_cash_flow = record.get("fcf")
                    existing.stock_based_compensation = record.get("sbc")
                    existing.revenue = record.get("revenue")
                    existing.cash_and_equivalents = record.get("cash")
                else:
                    # Parse fiscal year/quarter from period
                    fy, fq = _parse_fiscal_period(fiscal_period)
                    new_row = FundamentalsQuarterly(
                        company_id=company.id,
                        fiscal_period=fiscal_period,
                        fiscal_year=fy,
                        quarter=fq,
                        shares_outstanding_diluted=record.get("shares_outstanding"),
                        free_cash_flow=record.get("fcf"),
                        stock_based_compensation=record.get("sbc"),
                        revenue=record.get("revenue"),
                        cash_and_equivalents=record.get("cash"),
                    )
                    db_session.add(new_row)
                    # Add to existing_fundamentals so subsequent records
                    # in the same batch can be validated against it
                    existing_fundamentals.append(new_row)

            # Look up CIK and pull filings (skip in resume mode if already done)
            if skip_filings:
                db_session.commit()
                enriched += 1
                continue

            cik = edgar_client.lookup_cik(company.ticker)
            if cik:
                company.cik = cik
                filings = edgar_client.get_recent_filings(cik)

                for filing in filings:
                    # Skip if already in DB
                    exists = db_session.query(SecFiling).filter_by(
                        accession_number=filing["accession_number"]
                    ).first()
                    if exists:
                        continue

                    classification = edgar_client.classify_filing(
                        filing["form"], filing.get("primary_doc_url")
                    )

                    filed_date = None
                    if filing.get("filing_date"):
                        try:
                            parts = filing["filing_date"].split("-")
                            filed_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                        except (ValueError, IndexError):
                            pass

                    db_session.add(SecFiling(
                        company_id=company.id,
                        accession_number=filing["accession_number"],
                        filing_type=filing["form"],
                        filed_date=filed_date,
                        filing_url=filing.get("primary_doc_url"),
                        is_dilution_event=classification["is_dilution_event"],
                        dilution_type=classification.get("dilution_type"),
                        offering_amount_dollars=classification.get("offering_amount"),
                    ))

            # Commit after each company so progress isn't lost
            db_session.commit()
            enriched += 1

        except Exception as e:
            logger.error("Error enriching %s: %s", company.ticker, e)
            db_session.rollback()

    logger.info("Enriched %d candidates", enriched)

    # ------------------------------------------------------------------ #
    # Step 4: Score
    # ------------------------------------------------------------------ #
    logger.info("Step 4: Scoring all candidates...")

    # Set candidates to monitoring tier before scoring
    for company in candidates:
        if company.tracking_tier == "inactive":
            company.tracking_tier = "monitoring"
    db_session.commit()

    scores = score_all(db_session, config.scoring)

    # Step 4b: Fetch prices only for companies missing price_change_12m
    # (score_company carries forward from previous scores, so only truly
    # new companies need a fresh fetch)
    fetch_prices(db_session, fmp_client, scores, only_missing=True)

    # Assign tiers by percentile rank
    counts = assign_tiers(db_session, scores, config)
    logger.info("Critical: %d, Watchlist: %d, Monitoring: %d",
                counts["critical"], counts["watchlist"], counts["monitoring"])

    print_top_scores(db_session, scores)
    return scores


def _parse_fiscal_period(fiscal_period: str) -> tuple[int | None, int | None]:
    """Parse '2024-Q3' into (2024, 3)."""
    try:
        parts = fiscal_period.split("-Q")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Backfill dilution monitor data")
    parser.add_argument("--quick", action="store_true", help="Quick mode: screen first 500 companies only")
    parser.add_argument("--max-companies", type=int, default=3000, help="Max companies to screen")
    parser.add_argument("--resume", action="store_true", help="Skip already-enriched companies")
    parser.add_argument("--enrich-only", action="store_true", help="Skip screening, just enrich/score existing candidates")
    parser.add_argument("--score-only", action="store_true", help="Skip all data fetching, just rescore + retier using existing DB data")
    args = parser.parse_args()

    config = get_config()

    if not args.score_only and not config.fmp_api_key:
        print("ERROR: FMP_API_KEY not set. Add it to .env file.")
        print("  cp .env.example .env")
        print("  # Edit .env and add your API key")
        sys.exit(1)

    create_tables()
    session = SessionLocal()

    fmp = FMPClient(api_key=config.fmp_api_key or "") if config.fmp_api_key else None
    edgar = EdgarClient(user_agent=config.edgar_user_agent)

    try:
        run_backfill(
            db_session=session,
            fmp_client=fmp,
            edgar_client=edgar,
            config=config,
            max_companies=args.max_companies,
            quick_mode=args.quick,
            resume=args.resume,
            enrich_only=args.enrich_only,
            score_only=args.score_only,
        )
    except KeyboardInterrupt:
        logger.info("Backfill interrupted. Progress has been saved.")
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
