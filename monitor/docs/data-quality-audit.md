# Dilution Monitor — Data Quality Audit & Remediation Guide

**Date:** February 17, 2026
**Scope:** 12 companies verified against public filings (CGC, SOC, LXRX, NNE, ALT, SLDB, CAN, BTDR, EOSE, QSI, TBN, LXEO)

---

## Context

After verifying 12 high-scoring companies against public filings and market data, we found **systemic data quality issues** that affect the reliability of the tool's core output: the composite dilution score and tier assignments. This document catalogs every issue found, proposes fixes grounded in the actual codebase, and identifies additional pitfalls that haven't manifested yet but likely will.

---

## Part 1: Issues Found (Verified Across 12 Companies)

### Issue 1: Cash Runway Ignores Liquid Investments (CRITICAL)

**What happens:** `_calc_cash_runway_months()` in `scoring.py:271-296` uses only `cash_and_equivalents` from the balance sheet. Many companies park the majority of their liquidity in Treasury bills, money market funds, or short-term corporate bonds reported under "marketable securities" or "short-term investments."

**Impact:** Runway understated by 4-8x for companies like QSI ($31M cash vs $231M total liquidity), SLDB, and LXEO.

**Root cause:** The `FundamentalsQuarterly` model in `models.py:37-57` has no field for marketable securities. The FMP data pipeline in `backfill.py` fetches balance sheets but only extracts `cash_and_equivalents`. FMP's balance sheet endpoint **does** return `shortTermInvestments` and `longTermInvestments` — we just don't store them.

**Evidence:**

| Company | cash_and_equivalents | + Marketable Securities | DB Runway | Actual Runway |
|---------|---------------------|------------------------|-----------|---------------|
| QSI | $30.9M | $230.5M | 3.5 mo | ~29 mo |
| SLDB | (low) | $236.1M | 5.5 mo | ~18 mo |
| LXEO | (low) | ~$276M | 4.6 mo | ~31 mo |

**Fix methodology:**
1. Add `short_term_investments` column to `FundamentalsQuarterly` model
2. Update `backfill.py` FMP balance sheet extraction to pull `shortTermInvestments`
3. Modify `_calc_cash_runway_months()` to use `(cash_and_equivalents + short_term_investments)` as the numerator
4. Run a one-time re-backfill to populate the new field for existing companies
5. Re-score all companies

**Validation:** After fix, spot-check QSI, SLDB, LXEO runway against their 10-Q guidance ("sufficient to fund operations into [date]"). Should match within 20%.

---

### Issue 2: S-3 Filings Auto-Classified as ATM Shelves (MODERATE)

**What happens:** In `edgar_client.py:153-160`, every S-3 and S-3/A filing is automatically tagged as `dilution_type: "atm_shelf"` with `is_dilution_event: True`. No text analysis is performed on S-3s — only 424B5 and 8-K filings get the `classify_text()` treatment.

**Impact:** Warrant-resale registrations (CGC), secondary resale shelves, and non-ATM shelf registrations are all misclassified as ATM programs. TBN was flagged as having an "active ATM" when they only do traditional underwritten offerings.

**Evidence:**
- CGC Feb 6 S-3: Warrant-resale shelf for lender warrants -> tagged `atm_shelf`
- CGC Jan 9 S-3: Secondary resale registration -> tagged `atm_shelf`
- TBN: No ATM program exists, only underwritten public offerings -> still flagged

**Root cause:** The classification logic takes a shortcut: "if S-3, assume ATM." In reality, S-3 shelves are used for many purposes:
- ATM programs (correct to flag)
- Warrant-resale registrations (incorrect to flag as ATM)
- Secondary/resale shelves for existing holders (incorrect)
- Mixed-use universal shelves (ambiguous)
- Debt-only shelves (incorrect)

**Fix methodology:**
1. For S-3/S-3/A filings, fetch the first 5000 chars of the document (same as 424B5/8-K already do)
2. Apply `classify_text()` to distinguish:
   - "at-the-market" or "equity distribution agreement" -> `atm_shelf`
   - "resale" + "warrant" or "resale" + "selling stockholder" -> `resale_shelf` (new type, not a dilution event from the company's perspective)
   - "debt securities" only -> `debt_shelf` (new type)
   - Generic/mixed -> `universal_shelf` (flag but with lower confidence)
3. Add `resale_shelf`, `debt_shelf`, `universal_shelf` as dilution_type options
4. Re-classify existing S-3 filings in the database

**Validation:** Check CGC, TBN, NNE S-3 classifications after fix. CGC Feb 6 should become `resale_shelf`, TBN should lose ATM flag.

---

### Issue 3: FCF Burn Rate Calculation Artifacts (MODERATE)

**What happens:** `_calc_fcf_burn_rate()` in `scoring.py` takes trailing 4Q negative FCF, averages it, annualizes it, and divides by `company.market_cap`. When a company has one extremely negative quarter (e.g., a large inventory build or one-time payment), the ratio can spike to implausible levels.

**Impact:** CAN showed -4.8x FCF/market cap, but actual annual FCF was ~$218M on a ~$272M cap (= -0.8x). The 6x overstatement appears to be from a single quarter with outsized negative FCF being annualized.

**Root cause:** The IQR outlier filter (`_remove_outliers()`) uses a 3x fence, which may not catch extreme single-quarter spikes in cyclical businesses (like bitcoin miners with lumpy capex). Also, for companies like CAN that operate in crypto, large inventory purchases (mining rigs) flow through operating cash flow and distort the "burn rate" concept.

**Fix methodology:**
1. Add a sanity cap: if computed `fcf_burn_rate` exceeds -3.0 (burning 300% of market cap), flag for manual review or cap at -3.0
2. Consider using median instead of mean for the trailing 4Q average to reduce single-quarter spike sensitivity
3. Log a warning when the computed ratio exceeds -2.0 for manual inspection

**Validation:** Re-score CAN. Expected ratio should be in the -0.5 to -1.0 range, not -4.8.

---

### Issue 4: Stale Market Caps Between Backfill Runs (LOW-MODERATE)

**What happens:** Market cap is refreshed in Step 1 of `backfill.py` from FMP's stock screener list. Between backfill runs, the value can become stale, especially for volatile stocks.

**Impact:** SOC showed $848M (actual $1.26B, 48% off). BTDR showed $2.8B (actual $2.25B, 20% off). EOSE showed $3.2B (actual $3.6B).

**Root cause:** Backfill cadence — if the pipeline runs weekly or less frequently, market caps drift. For the FCF burn rate calculation specifically, this introduces error since it's the denominator.

**Fix methodology:**
1. This is mostly a pipeline scheduling issue — more frequent backfills help
2. Consider a lightweight "market cap refresh" job that runs daily (just hits the FMP stock list endpoint, no full fundamentals pull)
3. Alternatively, accept staleness as a known limitation and document the data freshness date in the UI

---

### Issue 5: Offering Count Inconsistencies (LOW-MODERATE)

**What happens:** The `offering_count_3y` metric counts `is_dilution_event=True` filings within a 3-year window. But counting depends heavily on what the EDGAR pipeline ingests (limited to 10-20 recent filings per company) and how filings are classified.

**Impact:**
- SOC: DB shows 2, reality is 3-5+ events (undercounted — EDGAR pull may have missed older filings)
- SLDB: DB shows 6, reality is 3 large offerings + ATM (overcounted — may be counting ATM quarterly supplements as separate events)
- LXRX: $94.6M combined raise captured as only $29.1M (missed concurrent tranches)

**Root cause:**
1. EDGAR pull limit of 10-20 filings misses events for prolific filers
2. Multiple filings for one economic event (424B5 + 8-K + S-3/A for same offering) may be double-counted
3. Multi-tranche deals (public offering + concurrent PIPE) may only capture one filing

**Fix methodology:**
1. Increase EDGAR filing pull limit from 20 to 50 for companies with `tracking_tier='critical'`
2. Add deduplication: if two `is_dilution_event` filings land within 5 business days, check if they reference the same transaction (via amount or text similarity)
3. For 424B5 filings, check if they're quarterly ATM sales updates vs. new offering prospectuses (quarterly updates often contain "sales agreement" + period language)

---

### Issue 6: Crypto Holdings Ignored in Runway (NICHE)

**What happens:** For crypto-native companies (CAN, BTDR, HUT), significant liquidity sits in BTC/ETH holdings that aren't captured in `cash_and_equivalents` or even `short_term_investments`.

**Impact:** CAN has $80.8M cash but ~$166M in crypto = $247M total liquidity. The 1.1-month runway should be ~3-4 months.

**Root cause:** Crypto holdings are reported on the balance sheet under various line items ("digital assets", "crypto assets") that don't map to standard FMP fields.

**Fix methodology:** This is a niche issue affecting <1% of companies. Options:
1. **Do nothing** — accept as a known limitation for crypto companies
2. **Manual override** — add a field for analyst-entered liquidity adjustments
3. **Flag crypto companies** — add an `is_crypto_company` flag and note that runway may be understated

**Recommendation:** Option 1 or 2. Not worth engineering a general solution for.

---

## Part 2: Other Potential Pitfalls Not Yet Observed

### Pitfall A: Reverse Stock Splits Breaking Share CAGR

**Risk:** If a company does a reverse split (common for sub-$1 stocks facing delisting), the `shares_outstanding_diluted` values across quarters become incomparable. A 1:10 reverse split would make it look like shares decreased 90%, masking ongoing dilution.

**How it could manifest:** A heavily dilutive company does a reverse split, suddenly appears to have "negative dilution" in the share CAGR calculation, and drops from critical to monitoring tier.

**Detection:** FMP historical data is supposed to be split-adjusted, but this depends on FMP's data quality. If fundamentals are pulled before the split adjustment propagates, stale pre-split share counts could coexist with post-split counts.

**Mitigation:**
1. When `share_cagr_3y` is strongly negative (shares apparently shrinking), flag for review
2. Cross-reference with SEC filings for 8-K events mentioning "reverse stock split"
3. Add a `split_adjustment_verified` flag or timestamp

---

### Pitfall B: Fiscal Year Misalignment

**Risk:** Companies with non-calendar fiscal years (e.g., SLDB ends March 31, CGC ends March 31) have their quarters stored as "2025-Q4" which might actually be Oct-Dec 2025 for one company and Jan-Mar 2026 for another.

**How it could manifest:** The "trailing 4 quarters" window in scoring functions could inadvertently compare different calendar periods across companies, or miss the most recent data for off-cycle filers.

**Current state:** The `fiscal_period` field stores the company-reported period (e.g., "FY2025-Q3"). The scoring code takes the last N records by ID order, which should work as long as FMP returns them chronologically.

**Mitigation:** Low risk if FMP data is consistently ordered, but worth adding a sort by `filed_date` or `fiscal_period` in scoring queries rather than relying on insertion order.

---

### Pitfall C: Pre-Revenue Companies Breaking SBC/Revenue Ratio

**Risk:** The `_calc_sbc_revenue_pct()` function divides SBC by revenue. For pre-revenue companies (QSI, LXEO, SLDB), revenue is near-zero, making the ratio explode to infinity.

**Current handling:** The code already handles this — if revenue <= 0 and SBC > 0, it returns score 100 (max risk). This is correct behavior. However, it means all pre-revenue companies with any SBC get the same max score regardless of how much SBC they actually have, losing granularity.

**Potential improvement:** For pre-revenue companies, normalize SBC against market cap or total operating expenses instead of revenue. This would differentiate between a company spending $2M/year in SBC vs $50M/year.

---

### Pitfall D: Convertible Note Dilution Not Captured in Share CAGR

**Risk:** Convertible notes (like EOSE's $600M at $16.29 conversion) represent massive latent dilution that won't show up in `shares_outstanding_diluted` until conversion actually occurs. The share CAGR metric only measures historical dilution, not pending structural overhang.

**How it could manifest:** A company raises $500M in convertible notes instead of equity. Share count stays flat. Share CAGR score drops. Company appears less dilutive. Then notes convert and shares spike 30% overnight.

**Current state:** Convertible filings are tagged as `dilution_type: "convertible"` and counted in offering frequency, but the potential share impact isn't quantified.

**Mitigation options:**
1. Add a `potential_dilution_shares` field to SEC filings (extractable from 424B5 text: "up to X shares upon conversion")
2. Create a "dilution overhang" sub-score that factors in unexercised warrants + unconverted notes
3. This would be a significant feature addition, not a quick fix

---

### Pitfall E: ATM Programs Expiring Without Detection

**Risk:** The `_calc_atm_active_score()` function (scoring.py) checks if any S-3 filing exists within 2 years. But ATM programs can be:
- Terminated early by the company
- Fully drawn down (capacity exhausted)
- Replaced by a new program

The current logic has no way to detect termination or exhaustion — it just looks at filing age.

**How it could manifest:** A company filed an S-3 18 months ago, fully drew down the ATM 12 months ago, and has no active program. Our tool still flags it as "active ATM" for another 6 months.

**Current scoring behavior:**
- 0-6 months since S-3: score 70-100
- 6-12 months: score 60-80
- 12-24 months: score 25-60
- The score naturally decays with age, partially mitigating this issue

**Mitigation:**
1. Track 424B5 "completion" filings that indicate an ATM is fully drawn
2. Track 8-K filings announcing ATM termination
3. If a new S-3 is filed, supersede the old one

---

### Pitfall F: International Companies with Non-USD Reporting

**Risk:** Companies like CAN (Canaan, reports in RMB) and TBN (Tamboran, Australian entity) may have fundamentals reported in local currency by FMP. If the pipeline doesn't normalize to USD, cash positions and burn rates could be wildly wrong.

**Current state:** FMP typically returns values in USD for US-listed ADRs, but this isn't guaranteed for all endpoints. The pipeline has no explicit currency normalization.

**Detection:** If a company's `cash_and_equivalents` seems 6-7x too high or too low, it may be a currency issue (RMB/USD ~ 7x).

**Mitigation:** Add a currency sanity check: if `cash_and_equivalents` / `market_cap` > 2.0 or < 0.0001, flag for review.

---

### Pitfall G: EDGAR Filing Limit Missing Older Events

**Risk:** The pipeline pulls only 10-20 recent filings per company from EDGAR. For companies that file frequently (10-Qs, 10-Ks, 8-Ks, plus amendments), the 20-filing window may only cover 6-12 months, missing dilutive events from year 2 and 3 of the 3-year offering count window.

**Impact:** Offering frequency score is understated for prolific filers. SOC showed 2 events vs 3-5+ actual.

**Mitigation:**
1. Increase the filing pull limit to 40-50 for `tracking_tier in ('critical', 'watchlist')`
2. Or specifically query EDGAR for S-3, 424B5, and S-1 filing types (EDGAR supports type filtering) rather than pulling all types and filtering client-side

---

## Part 3: Priority Matrix

| Issue | Severity | Effort | Priority |
|-------|----------|--------|----------|
| Cash runway ignoring liquid investments | Critical | Medium (schema + pipeline + scoring) | **P0** |
| S-3 auto-classification as ATM | Moderate | Medium (text analysis for S-3s) | **P1** |
| FCF burn rate artifacts | Moderate | Low (add sanity cap) | **P1** |
| Offering count inconsistencies | Low-Moderate | Medium (deduplication logic) | **P2** |
| Stale market caps | Low-Moderate | Low (daily refresh job) | **P2** |
| Crypto holdings in runway | Niche | Low-Medium | **P3** |
| Convertible dilution overhang | Forward-looking | High (new feature) | **P3** |
| Reverse split detection | Preventive | Medium | **P3** |
| EDGAR filing limit | Low | Low (config change) | **P2** |

---

## Part 4: Verification Plan (Post-Fix)

After implementing fixes, re-verify these 12 companies:

**Group A — Runway should change dramatically:**
- QSI: expect ~29 months (was 3.5)
- SLDB: expect ~18 months (was 5.5)
- LXEO: expect ~31 months (was 4.6)
- EOSE: expect 12+ months (was 2.9)

**Group B — ATM classification should change:**
- CGC Feb 6 S-3: should become `resale_shelf`, not `atm_shelf`
- TBN: should lose ATM active flag entirely

**Group C — FCF burn should normalize:**
- CAN: expect -0.7 to -0.8 (was -4.8)

**Group D — Scores should be stable (our data was accurate):**
- BTDR: all metrics confirmed, score should hold
- ALT: all metrics confirmed
- NNE: metrics confirmed (but note: 30+ year runway = false positive for "critical")

---

## Appendix: ATM Disclosure Timing (Reference)

ATM programs are the most disclosure-opaque equity issuance mechanism available. Key facts:

| Event | Filing/Source | Timing |
|-------|-------------|--------|
| ATM program announced | 424B5 + 8-K | Same day or next business day |
| Individual daily sales | None required | **No public disclosure** |
| Material block trade | 8-K (sometimes) | Within 4 business days |
| Quarterly aggregate sales | 424B5 supplement or 10-Q | 40-75 days after quarter end |

**Implication for our tool:** We cannot track ATM execution in real-time. The "active ATM" flag is the best available signal. Actual sales are only discoverable quarterly when 10-Q filings land. This is a structural limitation of SEC disclosure rules, not a bug in our system.

---

## Appendix: Company-by-Company Verification Summary

### Companies Where Our Data Is Accurate
| Company | Score | Key Metrics Verified |
|---------|-------|---------------------|
| **BTDR** | 64.0 | All metrics confirmed. FCF -0.6x, 6 offerings, 49% YoY share growth. Market cap stale ($2.8B vs $2.25B). |
| **ALT** | — | Registered direct $75M confirmed. Cash ~$260-270M, ~3yr runway. |
| **CAN** | 66.4 | Dilution confirmed (4x ADS growth). FCF ratio and runway need recalibration. |

### Companies Where Our Data Has Major Errors
| Company | Score | Key Error |
|---------|-------|-----------|
| **QSI** | 70.0 | Runway 3.5mo vs actual 29mo (ignoring $199M marketable securities) |
| **SLDB** | 79.0 | Runway 5.5mo vs actual 18mo (missing $236M total liquidity) |
| **LXEO** | 69.3 | Runway 4.6mo vs actual 31mo (pre-Oct 2025 $154M raise) |
| **EOSE** | 67.2 | Runway 2.9mo vs actual 12+mo (pre-Nov 2025 $1.06B raise) |
| **CGC** | 31.9 | Feb 6 S-3 misclassified as ATM (is warrant-resale shelf) |
| **TBN** | 74.2 | Flagged as "active ATM" but no ATM program exists |
| **SOC** | 73.7 | Offering count 2 vs actual 3-5+; market cap $848M vs $1.26B |

### Companies That Are False Positives
| Company | Score | Why It's a False Positive |
|---------|-------|--------------------------|
| **NNE** | — | 7 filings but $577M cash, $16M/yr burn = 30+ year runway. Dilutes from strength. |
