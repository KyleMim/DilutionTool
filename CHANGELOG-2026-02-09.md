# UX Improvements Session - Metric Explanations & Config Context

## Date
2026-02-09

## Summary
Added comprehensive tooltips, pipeline transparency, config impact messages, and improved ATM scoring to make the Dilution Tool more understandable and user-friendly.

## Key Changes

### 1. Metric Tooltips System
- **New files:**
  - `monitor/frontend/src/data/metricDefinitions.ts` - Single source of truth for all 6 metric definitions
  - `monitor/frontend/src/components/Tooltip.tsx` - Reusable CSS-only hover tooltip component

- **What it provides:**
  - Every metric now has: label, shortDesc, detailedDesc, calculation formula, time period, score interpretation, default weight, and optional caveats
  - Two tooltip variants: compact (for Screener headers) and detailed (for CompanyDetail ScoreCards)
  - No external library needed - pure Tailwind CSS with `group-hover` pattern

- **Integration:**
  - Screener: 6 column headers now have tooltips (Share CAGR, FCF Burn, SBC/Rev, Offerings, Runway, ATM)
  - CompanyDetail: Each ScoreCard has an info icon (ⓘ) that shows detailed explanation on hover

### 2. Pipeline Explainer
- **New file:** `monitor/frontend/src/components/PipelineExplainer.tsx`

- **What it shows:**
  - **Collapsed:** "How we find companies: Universe → Screen → Enrich → Score & Rank"
  - **Expanded:** Full 4-step breakdown:
    1. Universe Pull - All US equities from FMP (market cap > $0)
    2. Quick Screen - 8Q fundamentals check (Share CAGR > 5% OR ≥4 negative FCF quarters)
    3. Enrich - Full 12Q fundamentals + SEC filings from EDGAR (classified as ATM, registered direct, follow-on, convertible, PIPE)
    4. Score & Rank - 6 sub-scores → weighted composite → tier assignment (Watchlist ≥25, else Monitoring; Critical ≥75)

- **Location:** Screener page, between stats cards and sector tabs

### 3. Config Impact Messages
- **New file:** `monitor/frontend/src/data/configImplications.ts`

- **What it does:**
  - Pure functions that generate plain-English explanations when config values change
  - `getThresholdImplication()` - explains implications of changing screening/scoring thresholds
  - `getWeightImplication()` - explains how weight changes affect composite scoring

- **Examples:**
  - `share_cagr_min` 5%→10%: "Companies with less than 10% annual share growth over 3 years won't qualify as candidates during screening. This narrows the pool — only more aggressive diluters will be tracked."
  - `weight_share_cagr` 0.25→0.35: "Share dilution now accounts for 35% of the composite score (up from 25%). Companies with high share growth will rank significantly higher overall."

- **Integration:**
  - Conditional inline messages below each slider in Config page
  - Only appears when value differs from saved value (uses `Math.abs(oldVal - newVal) > EPSILON`)
  - Disappears once saved (values match again)
  - Styled as indigo-tinted info blocks (`bg-accent/10 border border-accent/20`)

### 4. ATM Decay Scoring
- **Modified file:** `monitor/backend/services/scoring.py`

- **Problem solved:**
  - Old logic was binary (100/0) based on presence of S-3/ATM filing in last 2 years
  - Didn't account for shelf age or whether company was actively selling
  - Treated fresh unused shelf the same as old exhausted shelf

- **New logic:**
  ```
  Find most recent S-3/S-3A or dilution_type="atm" within 2 years
  Count dilutive filings AFTER shelf date (evidence of selling)
  Calculate shelf age in months

  Score matrix:
    Age <6mo:  no selling → 100 (fully loaded, peak risk)
               selling    → 90  (actively diluting)

    Age 6-12mo: no selling → 70 (aging unused)
                selling    → 80 (mid-life program in use)

    Age 12-24mo: no selling → 25 (old, likely expired)
                 selling    → 60 (still in use, may be near exhaustion)

    No S-3 in 2 years → 0
  ```

- **Key insight from user:**
  - Fresh S-3 with NO sales is HIGHER risk than one with sales
  - "The gun has more ammo" - full capacity available, no dilution priced in yet
  - Old shelf with heavy sales = capacity likely exhausted = lower risk

- **Implementation:**
  - New function: `_calc_atm_score(filings: list[SecFiling]) -> tuple[float, bool]`
  - Returns `(decay_score, is_active_bool)` instead of binary
  - `atm_program_active` remains True if any S-3/ATM exists within 2 years (for red dot indicator)

## Important Architectural Decisions

### Tooltip Approach
- **Decision:** CSS-only, no library
- **Rationale:** Project has zero UI component libraries beyond Recharts. Adding Radix/Floating UI would be overkill for static text tooltips. Tailwind `group-hover` is sufficient and matches existing patterns.
- **Name collision fix:** Recharts exports `Tooltip`, so imported ours as `MetricTooltip` in CompanyDetail.tsx

### Metric Definitions Centralization
- **Decision:** Single `metricDefinitions.ts` file instead of inline strings
- **Rationale:** Prevents duplication across Screener, CompanyDetail, Config. Becomes single source of truth. Backend has this knowledge implicitly in scoring.py; frontend file makes it explicit.

### Config Implications as Pure Functions
- **Decision:** Client-side computation, no backend API needed
- **Rationale:** Impact messages are deterministic based on old/new values. No state to store. Simpler than backend endpoint or storing message templates in DB.

### ATM Decay Complexity
- **Decision:** Hybrid approach (decay scoring + agent transparency)
- **Rationale:** Decay function gives directional accuracy without parsing utilization from filing text (which would require NLP). Tooltip is honest about limitation ("Cannot detect full exhaustion"). AI agent has filing context to dig deeper when needed.

## Caveats & Known Limitations

1. **ATM exhaustion detection:** Cannot detect whether shelf capacity is fully used. Score decays based on age + activity, but an old shelf with heavy sales might still have capacity left. Tooltip directs users to ask AI agent for details.

2. **Filing classification accuracy:** Offering Freq metric depends on EDGAR parsing. Edge cases may be missed/misclassified. Caveat shown in tooltip.

3. **FCF burn quarters:** Only counts negative FCF quarters in average. Profitable quarters excluded. Could bias burn rate upward if company is inconsistently profitable. Caveat shown in tooltip.

4. **Config implications are approximations:** Messages are written for typical scenarios. Edge cases (e.g., setting a ceiling below current minimum) may have unintuitive messages.

## Testing Checklist (All Passed)

- [x] Backend imports clean: `python -c "from backend.services.scoring import score_company, _calc_atm_score"`
- [x] Frontend compiles: `npx tsc --noEmit`
- [x] Screener tooltip: Hover "Share CAGR" header shows calculation + time period
- [x] Screener tooltip: Hover "ATM" header mentions decay scoring + caveat
- [x] CompanyDetail tooltip: Hover ⓘ on ScoreCard shows detailed explanation
- [x] Pipeline explainer: Toggle expands to show 4 steps
- [x] Config threshold: Move slider shows "Impact:" message
- [x] Config weight: Move slider shows weight-specific impact
- [x] Config save: Impact messages disappear after save

## Files Changed (Commit 7aa7067)

### New Files (4)
1. `monitor/frontend/src/data/metricDefinitions.ts` - 183 lines
2. `monitor/frontend/src/components/Tooltip.tsx` - 102 lines
3. `monitor/frontend/src/components/PipelineExplainer.tsx` - 96 lines
4. `monitor/frontend/src/data/configImplications.ts` - 126 lines

### Modified Files (4)
1. `monitor/backend/services/scoring.py` - Added `_calc_atm_score()` function (40 lines), replaced binary logic
2. `monitor/frontend/src/pages/Screener.tsx` - Added PipelineExplainer + tooltips to 6 headers
3. `monitor/frontend/src/pages/CompanyDetail.tsx` - Added info icon tooltips to 6 ScoreCards
4. `monitor/frontend/src/pages/Config.tsx` - Added conditional impact messages below sliders

### Total Impact
- 587 insertions, 16 deletions
- 8 files changed
- 0 TypeScript errors, 0 Python errors

## Pattern to Reuse

**When adding more tooltips:**
```tsx
import Tooltip, { MetricTooltipContent } from "../components/Tooltip";
import { METRICS } from "../data/metricDefinitions";

<Tooltip
  position="bottom"
  content={
    <MetricTooltipContent
      shortDesc={METRICS.your_metric.shortDesc}
      calculation={METRICS.your_metric.calculation}
      timePeriod={METRICS.your_metric.timePeriod}
      scoreInterpretation={METRICS.your_metric.scoreInterpretation}
      caveat={METRICS.your_metric.caveat}
    />
  }
>
  <span>Your Label</span>
</Tooltip>
```

**When adding more config implications:**
```typescript
// In configImplications.ts, add new case to switch:
case "your_new_threshold":
  return higher
    ? "Explanation when value increases"
    : "Explanation when value decreases";
```

## Related Memory Files
- `MEMORY.md` - Main project context
- `fts5-notes-search.md` - Previous session on FTS5 implementation (if it exists)
