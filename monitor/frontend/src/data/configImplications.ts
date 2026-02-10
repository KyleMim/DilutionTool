const EPSILON = 0.001;

function changed(a: number, b: number): boolean {
  return Math.abs(a - b) > EPSILON;
}

function pct(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

export function getThresholdImplication(
  key: string,
  oldVal: number,
  newVal: number
): string | null {
  if (!changed(oldVal, newVal)) return null;

  const higher = newVal > oldVal;

  switch (key) {
    case "share_cagr_min":
      return higher
        ? `Companies with less than ${pct(newVal)} annual share growth over 3 years won't qualify as candidates during screening. This narrows the pool \u2014 only more aggressive diluters will be tracked.`
        : `Companies with as little as ${pct(newVal)} annual share growth will now qualify. This widens the screening pool \u2014 more companies with moderate dilution will be included.`;

    case "fcf_negative_quarters":
      return higher
        ? `Companies must now have at least ${newVal} quarters of negative free cash flow (out of 8 screened) to qualify. Fewer cash-burning companies will be flagged.`
        : `Companies with just ${newVal} quarter${newVal === 1 ? "" : "s"} of negative FCF will now qualify. This widens the pool significantly \u2014 many more cash-burning companies will be flagged.`;

    case "share_cagr_ceiling":
      return higher
        ? `Share CAGR sub-score now maxes out at ${pct(newVal)} annual growth instead of ${pct(oldVal)}. The scoring is more lenient \u2014 companies need higher growth rates to reach a score of 100.`
        : `Share CAGR sub-score now maxes out at ${pct(newVal)} instead of ${pct(oldVal)}. Companies with moderate share growth will receive proportionally higher scores on this metric.`;

    case "fcf_burn_ceiling":
      return higher
        ? `FCF Burn sub-score maxes out at a ${pct(newVal)} burn rate instead of ${pct(oldVal)}. Companies need to be burning cash faster (relative to market cap) to score 100.`
        : `FCF Burn sub-score maxes out at ${pct(newVal)} instead of ${pct(oldVal)}. Companies with moderate burn rates will score higher on this metric.`;

    case "sbc_revenue_ceiling":
      return higher
        ? `SBC/Revenue sub-score maxes out at a ${pct(newVal)} ratio instead of ${pct(oldVal)}. Companies need higher stock compensation relative to revenue to score 100.`
        : `SBC/Revenue sub-score maxes out at ${pct(newVal)} instead of ${pct(oldVal)}. Companies with moderate SBC will score higher on this metric.`;

    case "offering_freq_ceiling":
      return higher
        ? `Offering Frequency sub-score maxes out at ${newVal} filings instead of ${oldVal}. More filings are needed to reach a score of 100 \u2014 less sensitive to occasional offerings.`
        : `Offering Frequency sub-score maxes out at ${newVal} filing${newVal === 1 ? "" : "s"} instead of ${oldVal}. Fewer filings needed to score 100 \u2014 more sensitive to dilutive activity.`;

    case "cash_runway_max_months":
      return higher
        ? `Companies with up to ${newVal} months of cash will now receive some runway risk score. Previously only companies under ${oldVal} months were affected. This captures more companies with moderate cash positions.`
        : `Only companies with less than ${newVal} months of cash will score on this metric (was ${oldVal}). This focuses the runway metric on companies in more immediate danger of running out of cash.`;

    case "critical_percentile":
      return higher
        ? `Only the top ${100 - newVal}% of scores will be Critical (was top ${100 - oldVal}%). Fewer companies flagged as critical.`
        : `The top ${100 - newVal}% of scores will now be Critical (was top ${100 - oldVal}%). More companies flagged for immediate attention.`;

    case "watchlist_percentile":
      return higher
        ? `Only the top ${100 - newVal}% of scores will make Watchlist (was top ${100 - oldVal}%). Fewer companies on the watchlist.`
        : `The top ${100 - newVal}% of scores will now make Watchlist (was top ${100 - oldVal}%). More companies flagged for active monitoring.`;

    default:
      return null;
  }
}

export function getWeightImplication(
  key: string,
  label: string,
  oldVal: number,
  newVal: number
): string | null {
  if (!changed(oldVal, newVal)) return null;

  const oldPct = (oldVal * 100).toFixed(0);
  const newPct = (newVal * 100).toFixed(0);
  const higher = newVal > oldVal;

  if (newVal === 0) {
    return `${label} is now excluded from the composite score entirely. This metric will have no effect on company rankings.`;
  }

  return higher
    ? `${label} now accounts for ${newPct}% of the composite score (up from ${oldPct}%). Companies scoring high on this metric will rank significantly higher overall.`
    : `${label} now accounts for ${newPct}% of the composite score (down from ${oldPct}%). This metric will have less influence on overall rankings.`;
}
