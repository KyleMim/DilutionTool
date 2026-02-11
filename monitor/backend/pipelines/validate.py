"""
Validate fundamentals data: detect statistical outliers and optionally correct
them using web search.

Two modes:
  1. CLI: scan existing DB records for outliers and optionally fix via web search.
  2. Ingestion: validate incoming FMP records before storing (called from backfill).

CLI Usage:
  python -m backend.pipelines.validate                 # Scan & report only
  python -m backend.pipelines.validate --fix           # Interactive fix (confirm each)
  python -m backend.pipelines.validate --fix --yes     # Auto-fix all
  python -m backend.pipelines.validate --ticker NNE    # Scan single company
"""
import argparse
import logging
import os
import re
import statistics
import sys

from dotenv import load_dotenv

load_dotenv()

from backend.database import SessionLocal, create_tables
from backend.models import Company, FundamentalsQuarterly
from backend.services.scoring import _remove_outliers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Fields to check for outliers (all numeric columns on FundamentalsQuarterly)
NUMERIC_FIELDS = [
    "free_cash_flow",
    "cash_and_equivalents",
    "revenue",
    "stock_based_compensation",
    "shares_outstanding_diluted",
]

# Map from FMP merged record keys to FundamentalsQuarterly column names
FMP_TO_DB_FIELD = {
    "fcf": "free_cash_flow",
    "cash": "cash_and_equivalents",
    "revenue": "revenue",
    "sbc": "stock_based_compensation",
    "shares_outstanding": "shares_outstanding_diluted",
}

# Incoming values that deviate by more than this factor from the median
# of existing quarters are flagged as suspect and sent to web search.
SUSPECT_THRESHOLD = 5.0

# For new companies with no history, cap values relative to market cap.
# E.g., FCF shouldn't exceed 3x market cap in a single quarter.
MARKET_CAP_RATIO_LIMIT = 3.0


def validate_incoming_record(
    ticker: str,
    fiscal_period: str,
    incoming: dict,
    existing_fundamentals: list[FundamentalsQuarterly],
    market_cap: float | None = None,
) -> dict:
    """Validate an incoming FMP record against existing data for a company.

    Checks each numeric field:
      - If the company has 3+ existing quarters, flag values that deviate
        by more than SUSPECT_THRESHOLD from the median.
      - If no history exists, apply market-cap-relative bounds.
      - Suspect values are validated via web search. If web search returns
        a corrected value, use that. If it confirms the value is wrong
        but can't find the correct one, discard the field (set to None).

    Args:
        ticker: Company ticker symbol
        fiscal_period: e.g. "2025-Q1"
        incoming: Dict with FMP keys (fcf, cash, revenue, sbc, shares_outstanding)
        existing_fundamentals: List of existing FundamentalsQuarterly rows for this company
        market_cap: Company's current market cap (for absolute bounds on new companies)

    Returns:
        Cleaned copy of incoming dict with suspect values corrected or removed.
    """
    cleaned = dict(incoming)

    for fmp_key, db_field in FMP_TO_DB_FIELD.items():
        value = incoming.get(fmp_key)
        if value is None:
            continue

        # Collect existing values for this field
        existing_vals = [
            getattr(f, db_field) for f in existing_fundamentals
            if getattr(f, db_field) is not None
        ]

        is_suspect = False
        reason = ""

        if len(existing_vals) >= 3:
            # Compare against median of existing data
            median_val = statistics.median(existing_vals)

            if median_val != 0:
                ratio = abs(value / median_val)
                if ratio > SUSPECT_THRESHOLD:
                    is_suspect = True
                    reason = f"{ratio:.1f}x median ({median_val:,.0f})"
            elif abs(value) > 0:
                # Median is 0 but incoming is non-zero — check if existing
                # values are all near zero
                max_existing = max(abs(v) for v in existing_vals) if existing_vals else 0
                if max_existing > 0 and abs(value) / max_existing > SUSPECT_THRESHOLD:
                    is_suspect = True
                    reason = f"{abs(value)/max_existing:.1f}x max existing ({max_existing:,.0f})"
                elif max_existing == 0 and abs(value) > 1e6:
                    # All existing are 0, incoming is large — suspicious
                    is_suspect = True
                    reason = f"all existing are 0, incoming is {value:,.0f}"

        elif market_cap and market_cap > 0:
            # New company or sparse data — use market cap as sanity check
            if abs(value) > market_cap * MARKET_CAP_RATIO_LIMIT:
                is_suspect = True
                reason = f"{abs(value)/market_cap:.1f}x market cap ({market_cap:,.0f})"

        if is_suspect:
            logger.warning(
                "SUSPECT %s %s %s: %s = %.0f (%s) -- validating via web search",
                ticker, fiscal_period, db_field, fmp_key, value, reason,
            )

            corrected = web_search_correct_value(ticker, db_field, fiscal_period, value)
            if corrected is not None:
                # Web search found a value — use it
                logger.info(
                    "Web search corrected %s %s %s: %.0f -> %.0f",
                    ticker, fiscal_period, db_field, value, corrected,
                )
                cleaned[fmp_key] = corrected
            else:
                # Web search couldn't find the correct value — discard this field
                # rather than store a potentially bad value
                logger.warning(
                    "Web search inconclusive for %s %s %s -- discarding value %.0f",
                    ticker, fiscal_period, db_field, value,
                )
                cleaned[fmp_key] = None

    return cleaned


def detect_outliers_for_company(
    fundamentals: list[FundamentalsQuarterly],
) -> list[dict]:
    """Return a list of outlier records for one company.

    Each dict: {row, field, value, q1, q3, lower, upper}
    """
    outliers = []

    for field in NUMERIC_FIELDS:
        values_with_row = [
            (f, getattr(f, field))
            for f in fundamentals
            if getattr(f, field) is not None
        ]
        if len(values_with_row) < 4:
            continue

        vals = [v for _, v in values_with_row]
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[(3 * n) // 4]
        iqr = q3 - q1
        lower = q1 - 3 * iqr
        upper = q3 + 3 * iqr

        for row, value in values_with_row:
            if value < lower or value > upper:
                outliers.append({
                    "row": row,
                    "field": field,
                    "value": value,
                    "q1": q1,
                    "q3": q3,
                    "lower": lower,
                    "upper": upper,
                })

    return outliers


def _parse_number(text: str) -> float | None:
    """Try to extract a dollar number from LLM text (e.g. '-$9.6 million')."""
    text = text.replace(",", "").replace("$", "")

    # Match patterns like -9.6 million, 203 billion, etc.
    m = re.search(
        r"(-?[\d.]+)\s*(billion|million|thousand|trillion)?",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    num = float(m.group(1))
    multiplier = (m.group(2) or "").lower()
    mult_map = {
        "trillion": 1e12,
        "billion": 1e9,
        "million": 1e6,
        "thousand": 1e3,
        "": 1,
    }
    return num * mult_map.get(multiplier, 1)


def web_search_correct_value(
    ticker: str, field: str, fiscal_period: str, current_value: float
) -> float | None:
    """Use Anthropic web search to look up the correct value."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping web validation")
        return None

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    field_label = field.replace("_", " ")
    # Parse period like "2025-Q1" into something readable
    prompt = (
        f"What was {ticker}'s {field_label} for fiscal quarter {fiscal_period}? "
        f"Our database currently shows {current_value:,.0f} which looks wrong. "
        f"Give me the correct number in dollars. Reply with JUST the number and "
        f"unit (e.g. '-9.6 million' or '203 million'). If you cannot find it, "
        f"reply 'UNKNOWN'."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=256,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        text = "".join(b.text for b in response.content if hasattr(b, "text"))
        logger.info("Web search response for %s %s %s: %s", ticker, field, fiscal_period, text.strip())

        if "UNKNOWN" in text.upper():
            return None

        return _parse_number(text)

    except Exception as e:
        logger.error("Web search failed for %s %s: %s", ticker, fiscal_period, e)
        return None


def run_validate(ticker: str | None = None, fix: bool = False, auto_yes: bool = False):
    """Main validation routine."""
    create_tables()
    db = SessionLocal()

    # Get companies to check
    query = db.query(Company).filter(Company.tracking_tier != "inactive")
    if ticker:
        query = query.filter(Company.ticker == ticker.upper())
    companies = query.all()

    if not companies:
        print(f"No companies found{f' matching {ticker}' if ticker else ''}.")
        return

    total_outliers = 0
    fixed = 0

    for company in companies:
        fundamentals = (
            db.query(FundamentalsQuarterly)
            .filter(FundamentalsQuarterly.company_id == company.id)
            .order_by(FundamentalsQuarterly.fiscal_period.asc())
            .all()
        )

        if not fundamentals:
            continue

        outliers = detect_outliers_for_company(fundamentals)
        if not outliers:
            continue

        print(f"\n{'='*60}")
        name = company.name.encode("ascii", errors="replace").decode("ascii")
        print(f"  {company.ticker} - {name}")
        print(f"{'='*60}")

        for o in outliers:
            total_outliers += 1
            row = o["row"]
            print(
                f"  [{row.fiscal_period}] {o['field']}: "
                f"{o['value']:>18,.0f}  "
                f"(expected range: {o['lower']:,.0f} to {o['upper']:,.0f})"
            )

            if fix:
                corrected = web_search_correct_value(
                    company.ticker, o["field"], row.fiscal_period, o["value"]
                )
                if corrected is not None:
                    print(f"    -> Web search suggests: {corrected:,.0f}")

                    if auto_yes:
                        proceed = True
                    else:
                        answer = input("    Apply correction? [y/N] ").strip().lower()
                        proceed = answer == "y"

                    if proceed:
                        setattr(row, o["field"], corrected)
                        db.commit()
                        print(f"    -> FIXED")
                        fixed += 1
                    else:
                        print(f"    -> Skipped")
                else:
                    print(f"    -> Web search: could not determine correct value")

    print(f"\n{'-'*60}")
    print(f"Total outliers found: {total_outliers}")
    if fix:
        print(f"Fixed: {fixed}")
    print(f"{'-'*60}")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Validate fundamentals data for outliers")
    parser.add_argument("--ticker", type=str, help="Check a single ticker")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix outliers via web search")
    parser.add_argument("--yes", action="store_true", help="Auto-apply fixes without confirmation")
    args = parser.parse_args()

    run_validate(ticker=args.ticker, fix=args.fix, auto_yes=args.yes)


if __name__ == "__main__":
    main()
