import logging
import statistics
from datetime import date, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.config import ScoringConfig
from backend.models import Company, FundamentalsQuarterly, SecFiling, DilutionScore
from backend.services.filters import is_spac_name, is_non_equity

logger = logging.getLogger(__name__)


def score_company(db_session: Session, company_id: int, config: ScoringConfig) -> DilutionScore:
    """Compute composite dilution score for a company and save to DB."""
    company = db_session.get(Company, company_id)
    if not company:
        raise ValueError(f"Company {company_id} not found")

    # Pull last 12 quarters ordered oldest -> newest
    fundamentals = (
        db_session.query(FundamentalsQuarterly)
        .filter(FundamentalsQuarterly.company_id == company_id)
        .order_by(FundamentalsQuarterly.fiscal_period.asc())
        .limit(12)
        .all()
    )

    # Pull all filings
    filings = (
        db_session.query(SecFiling)
        .filter(SecFiling.company_id == company_id)
        .all()
    )

    # Calculate sub-scores
    scores = {}
    metrics = {}

    # 1. Share CAGR score
    share_cagr = _calc_share_cagr(fundamentals)
    metrics["share_cagr_3y"] = share_cagr
    if share_cagr is not None:
        scores["share_cagr_score"] = min(share_cagr / config.share_cagr_ceiling * 100, 100)
    else:
        scores["share_cagr_score"] = None

    # 2. FCF burn score
    fcf_burn_rate = _calc_fcf_burn_rate(fundamentals, company.market_cap)
    metrics["fcf_burn_rate"] = fcf_burn_rate
    if fcf_burn_rate is not None:
        scores["fcf_burn_score"] = min(abs(fcf_burn_rate) / config.fcf_burn_ceiling * 100, 100)
    else:
        scores["fcf_burn_score"] = 0

    # 3. SBC/Revenue score
    sbc_rev_pct = _calc_sbc_revenue_pct(fundamentals)
    metrics["sbc_revenue_pct"] = sbc_rev_pct
    if sbc_rev_pct is not None:
        scores["sbc_revenue_score"] = max(0, min(sbc_rev_pct / config.sbc_revenue_ceiling * 100, 100))
    elif _has_sbc_no_revenue(fundamentals):
        scores["sbc_revenue_score"] = 100
        metrics["sbc_revenue_pct"] = 1.0
    else:
        scores["sbc_revenue_score"] = None

    # 4. Offering frequency score
    three_years_ago = date.today() - timedelta(days=3 * 365)
    offering_count = sum(
        1 for f in filings
        if f.is_dilution_event and f.filed_date and f.filed_date >= three_years_ago
    )
    metrics["offering_count_3y"] = offering_count
    scores["offering_freq_score"] = min(offering_count / config.offering_freq_ceiling * 100, 100)

    # 5. Cash runway score
    cash_runway = _calc_cash_runway_months(fundamentals)
    metrics["cash_runway_months"] = cash_runway
    if cash_runway is not None:
        scores["cash_runway_score"] = max(0, (config.cash_runway_max_months - cash_runway) / config.cash_runway_max_months * 100)
    else:
        scores["cash_runway_score"] = 0

    # 6. ATM active score (decay-based)
    atm_score, atm_active = _calc_atm_score(filings)
    metrics["atm_program_active"] = atm_active
    scores["atm_active_score"] = atm_score

    # Composite: weighted average with renormalization for missing scores
    composite = _weighted_composite(scores, config)

    # Carry forward price_change_12m from previous score (if any)
    prev_score = (
        db_session.query(DilutionScore)
        .filter_by(company_id=company_id)
        .order_by(desc(DilutionScore.id))
        .first()
    )
    prev_price = prev_score.price_change_12m if prev_score else None

    # Save to DB
    dilution_score = DilutionScore(
        company_id=company_id,
        score_date=date.today(),
        composite_score=round(composite, 2),
        share_cagr_score=_round_or_none(scores.get("share_cagr_score")),
        fcf_burn_score=_round_or_none(scores.get("fcf_burn_score")),
        sbc_revenue_score=_round_or_none(scores.get("sbc_revenue_score")),
        offering_freq_score=_round_or_none(scores.get("offering_freq_score")),
        cash_runway_score=_round_or_none(scores.get("cash_runway_score")),
        atm_active_score=_round_or_none(scores.get("atm_active_score")),
        share_cagr_3y=metrics.get("share_cagr_3y"),
        fcf_burn_rate=metrics.get("fcf_burn_rate"),
        sbc_revenue_pct=metrics.get("sbc_revenue_pct"),
        offering_count_3y=metrics.get("offering_count_3y"),
        cash_runway_months=metrics.get("cash_runway_months"),
        atm_program_active=metrics.get("atm_program_active"),
        price_change_12m=prev_price,
    )
    db_session.add(dilution_score)
    db_session.commit()

    logger.info("Scored %s: composite=%.1f", company.ticker, composite)
    return dilution_score


def score_all(db_session: Session, config: ScoringConfig) -> list[DilutionScore]:
    """Score every watchlist company, skipping SPACs and non-equity securities."""
    companies = (
        db_session.query(Company)
        .filter(Company.tracking_tier.in_(["critical", "watchlist", "monitoring"]))
        .all()
    )
    results = []
    for company in companies:
        if is_spac_name(company.name) or is_non_equity(company.ticker, company.name):
            logger.info("Skipping non-equity/SPAC: %s (%s)", company.ticker, company.name)
            company.tracking_tier = "inactive"
            db_session.commit()
            continue
        try:
            score = score_company(db_session, company.id, config)
            results.append(score)
        except Exception as e:
            logger.error("Failed to score %s: %s", company.ticker, e)
    return results


def get_latest_scores(db_session: Session) -> list[tuple[Company, DilutionScore]]:
    """Get the latest score for each company, joined with Company."""
    # Subquery for max score_date per company
    from sqlalchemy import func
    latest_sub = (
        db_session.query(
            DilutionScore.company_id,
            func.max(DilutionScore.id).label("max_id"),
        )
        .group_by(DilutionScore.company_id)
        .subquery()
    )

    results = (
        db_session.query(Company, DilutionScore)
        .join(DilutionScore, Company.id == DilutionScore.company_id)
        .join(latest_sub, DilutionScore.id == latest_sub.c.max_id)
        .order_by(DilutionScore.composite_score.desc())
        .all()
    )
    return results


# ------------------------------------------------------------------ #
# Internal calculation helpers
# ------------------------------------------------------------------ #

def _calc_share_cagr(fundamentals: list[FundamentalsQuarterly]) -> float | None:
    """Annualized share count CAGR."""
    shares = [
        (f.fiscal_period, f.shares_outstanding_diluted)
        for f in fundamentals
        if f.shares_outstanding_diluted and f.shares_outstanding_diluted > 0
    ]
    if len(shares) < 2:
        return None

    oldest_shares = shares[0][1]
    newest_shares = shares[-1][1]
    num_quarters = len(shares) - 1

    if oldest_shares <= 0 or num_quarters == 0:
        return None

    cagr = (newest_shares / oldest_shares) ** (4 / num_quarters) - 1
    return max(cagr, 0)  # Only care about growth (dilution)


def _remove_outliers(values: list[float], label: str = "") -> list[float]:
    """Remove absurd outliers using IQR method (3x fence).

    Only activates with 4+ data points.  Returns the filtered list.
    """
    if len(values) < 4:
        return values

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1

    # Use absolute values for the fence when all values share the same sign,
    # so that a 1000x magnitude spike is always caught.
    lower = q1 - 3 * iqr
    upper = q3 + 3 * iqr

    filtered = [v for v in values if lower <= v <= upper]
    removed = len(values) - len(filtered)
    if removed:
        excluded = [v for v in values if v < lower or v > upper]
        logger.warning(
            "Outlier filter (%s): removed %d value(s) %s  (fence [%.2g, %.2g])",
            label, removed, excluded, lower, upper,
        )
    return filtered if filtered else values  # never return empty


def _calc_fcf_burn_rate(fundamentals: list[FundamentalsQuarterly], market_cap: float | None) -> float | None:
    """Trailing 4Q average negative FCF / market_cap, annualized."""
    if not market_cap or market_cap <= 0:
        return None

    recent = fundamentals[-4:] if len(fundamentals) >= 4 else fundamentals
    negative_fcf = [f.free_cash_flow for f in recent if f.free_cash_flow is not None and f.free_cash_flow < 0]
    if not negative_fcf:
        return None

    negative_fcf = _remove_outliers(negative_fcf, "fcf_burn")
    avg_quarterly_burn = sum(negative_fcf) / len(negative_fcf)
    annualized_burn = avg_quarterly_burn * 4
    return annualized_burn / market_cap  # Will be negative


def _calc_sbc_revenue_pct(fundamentals: list[FundamentalsQuarterly]) -> float | None:
    """Trailing 4Q SBC / trailing 4Q revenue."""
    recent = fundamentals[-4:] if len(fundamentals) >= 4 else fundamentals
    if not recent:
        return None

    total_sbc = sum(f.stock_based_compensation or 0 for f in recent)
    total_rev = sum(f.revenue or 0 for f in recent)

    if total_rev <= 0:
        return None  # Handled separately by _has_sbc_no_revenue

    return total_sbc / total_rev


def _has_sbc_no_revenue(fundamentals: list[FundamentalsQuarterly]) -> bool:
    """Check if company has SBC but no revenue (= max dilution concern)."""
    recent = fundamentals[-4:] if len(fundamentals) >= 4 else fundamentals
    if not recent:
        return False

    total_sbc = sum(f.stock_based_compensation or 0 for f in recent)
    total_rev = sum(f.revenue or 0 for f in recent)

    return total_sbc > 0 and total_rev <= 0


def _calc_cash_runway_months(fundamentals: list[FundamentalsQuarterly]) -> float | None:
    """Latest cash / abs(trailing 4Q avg FCF burn), in months."""
    if not fundamentals:
        return None

    latest_cash = None
    for f in reversed(fundamentals):
        if f.cash_and_equivalents is not None:
            latest_cash = f.cash_and_equivalents
            break

    if latest_cash is None:
        return None

    recent = fundamentals[-4:] if len(fundamentals) >= 4 else fundamentals
    negative_fcf = [f.free_cash_flow for f in recent if f.free_cash_flow is not None and f.free_cash_flow < 0]
    if not negative_fcf:
        return None  # Not burning cash

    negative_fcf = _remove_outliers(negative_fcf, "cash_runway")
    avg_quarterly_burn = abs(sum(negative_fcf) / len(negative_fcf))
    if avg_quarterly_burn == 0:
        return None

    quarters_of_runway = latest_cash / avg_quarterly_burn
    return quarters_of_runway * 3  # Convert to months


def _calc_atm_score(filings: list[SecFiling]) -> tuple[float, bool]:
    """Score ATM risk based on shelf registration age and selling activity.

    A fresh shelf with no sales = highest risk (fully loaded, no dilution priced in).
    An old shelf with heavy sales = lower risk (capacity likely exhausted).
    """
    two_years_ago = date.today() - timedelta(days=2 * 365)

    # Find the most recent S-3/ATM shelf filing within 2 years
    shelf_filings = [
        f for f in filings
        if (f.filing_type in ("S-3", "S-3/A") or f.dilution_type == "atm")
        and f.filed_date and f.filed_date >= two_years_ago
    ]

    if not shelf_filings:
        return 0.0, False

    # Sort by date descending, take most recent
    shelf_filings.sort(key=lambda f: f.filed_date, reverse=True)
    latest_shelf = shelf_filings[0]
    shelf_date = latest_shelf.filed_date

    # Check for dilutive filings after the shelf date (evidence of selling)
    has_selling = any(
        f.is_dilution_event
        and f.filed_date and f.filed_date > shelf_date
        and f.filing_type not in ("S-3", "S-3/A")
        for f in filings
    )

    # Calculate shelf age in months
    days_since = (date.today() - shelf_date).days
    months_since = days_since / 30.44  # average days per month

    # Decay matrix
    if months_since < 6:
        score = 100.0 if not has_selling else 90.0
    elif months_since < 12:
        score = 70.0 if not has_selling else 80.0
    else:  # 12-24 months
        score = 25.0 if not has_selling else 60.0

    return score, True


def _weighted_composite(scores: dict, config: ScoringConfig) -> float:
    """Calculate weighted composite, renormalizing when sub-scores are missing."""
    weight_map = {
        "share_cagr_score": config.weight_share_cagr,
        "fcf_burn_score": config.weight_fcf_burn,
        "sbc_revenue_score": config.weight_sbc_revenue,
        "offering_freq_score": config.weight_offering_freq,
        "cash_runway_score": config.weight_cash_runway,
        "atm_active_score": config.weight_atm_active,
    }

    total_weight = 0
    weighted_sum = 0

    for key, weight in weight_map.items():
        score = scores.get(key)
        if score is not None:
            weighted_sum += score * weight
            total_weight += weight

    if total_weight == 0:
        return 0

    return weighted_sum / total_weight


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)
