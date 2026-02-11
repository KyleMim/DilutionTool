# Scoring Data Quality: Outlier Detection & Trailing Window

## Problem

The dilution scoring engine was producing wildly inaccurate FCF burn rates and cash runway estimates for many companies. Two root causes were identified:

### 1. Bad data from FMP API

Financial Modeling Prep (FMP) occasionally returns erroneous values for quarterly financials. For example, NNE (Nano Nuclear Energy) had a 2025-Q1 free cash flow of **-$9.24 billion** — roughly 1000x its actual quarterly burn of ~$9.5 million. A second field (stock-based compensation) was also off by 1000x in the same quarter.

A full scan of all 1,978 tracked companies found **2,737 outlier data points** across 1,232 companies (62% of the universe):

| Field                        | Outlier Count |
|------------------------------|---------------|
| shares_outstanding_diluted   | 685           |
| stock_based_compensation     | 622           |
| free_cash_flow               | 515           |
| cash_and_equivalents         | 463           |
| revenue                      | 452           |

### 2. Full-history averaging diluted burn rate accuracy

Both `_calc_fcf_burn_rate()` and `_calc_cash_runway_months()` averaged **all 12 quarters** of FCF data. For growing companies whose burn rates changed substantially over 3 years, this produced misleading results. Example: NNE's 2022-2023 quarters showed $0.6M-$1.2M burns, while 2025 quarters showed ~$9.5M. Averaging all 12 gave ~$3.3M — neither reflecting current reality nor historical reality.

### Combined impact on NNE

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| Avg quarterly burn | $773M (poisoned by -$9.2B outlier) | $7.4M (trailing 4Q, outlier excluded) |
| Cash runway | 0.8 months | 82.9 months |
| Composite score | 82.1 | 53.1 |

After rescoring all companies, **1,572 out of 1,978 (79%)** had their composite scores change, with an average absolute change of 2.44 points and maximum changes of ~30 points.

## Solution

### 1. IQR-based outlier detection (`scoring.py`)

Added `_remove_outliers()` helper using the **Interquartile Range (IQR) method** with a 3x fence:

```python
def _remove_outliers(values: list[float], label: str = "") -> list[float]:
    # Q1, Q3, IQR computed from sorted values
    # Fence: [Q1 - 3*IQR, Q3 + 3*IQR]
    # Values outside fence are excluded and logged as warnings
    # Requires 4+ data points to activate
    # Never returns empty list (falls back to original if all filtered)
```

The 3x fence is deliberately wide — it only catches truly absurd outliers (1000x magnitude spikes), not normal business variation.

Applied in both:
- `_calc_fcf_burn_rate()` — before computing mean burn rate
- `_calc_cash_runway_months()` — before computing mean burn rate for runway

### 2. Trailing 4-quarter window (`scoring.py`)

Both functions now use `fundamentals[-4:]` (most recent 4 quarters) instead of all 12 quarters. This matches the existing pattern used by `_calc_sbc_revenue_pct()` and ensures the burn rate reflects current operations, not historical levels from years ago.

### 3. Validation CLI (`pipelines/validate.py`)

A standalone command to scan the database for outliers and optionally correct them using Anthropic's web search:

```bash
# Scan & report all outliers
python -m backend.pipelines.validate

# Scan a single company
python -m backend.pipelines.validate --ticker NNE

# Fix outliers via web search (interactive, confirm each)
python -m backend.pipelines.validate --fix

# Auto-fix all outliers (no confirmation prompts)
python -m backend.pipelines.validate --fix --yes
```

The validator:
1. Groups `FundamentalsQuarterly` rows by company
2. Applies the same IQR method to detect outliers across all numeric fields (FCF, cash, revenue, SBC, shares)
3. When `--fix` is passed, uses Anthropic API with web search to look up the correct value for each outlier
4. Presents a report and optionally updates the database

### 4. Score-only backfill mode (`pipelines/backfill.py`)

Added `--score-only` flag to rescore all tracked companies using existing DB data without re-fetching from FMP:

```bash
python -m backend.pipelines.backfill --score-only
```

This is useful after:
- Changing scoring logic (like this change)
- Running `validate --fix` to correct bad data
- Any situation where you want fresh scores without API calls

It performs: scoring -> price change fetch -> percentile-based tier assignment.

## Files Modified

| File | Change |
|------|--------|
| `backend/services/scoring.py` | Added `_remove_outliers()`, changed FCF functions to trailing 4Q + outlier filter |
| `backend/pipelines/backfill.py` | Added `--score-only` flag and execution path |
| `backend/pipelines/validate.py` | **New** — CLI tool for outlier detection and web-search-based correction |

## Verification

```bash
# Run existing tests (all 18 pass)
pytest monitor/backend/tests/test_scoring.py

# Check a specific company
python -m backend.pipelines.validate --ticker NNE

# Rescore everything
python -m backend.pipelines.backfill --score-only
```
