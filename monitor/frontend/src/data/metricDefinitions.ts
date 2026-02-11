export interface MetricDefinition {
  label: string;
  shortDesc: string;
  detailedDesc: string;
  calculation: string;
  timePeriod: string;
  scoreInterpretation: string;
  defaultWeight: string;
  caveat?: string;
}

export const METRICS: Record<string, MetricDefinition> = {
  share_cagr: {
    label: "Share CAGR",
    shortDesc: "3-year annualized share growth rate",
    detailedDesc:
      "Measures how fast the company is issuing new shares, diluting existing shareholders. " +
      "Takes the oldest and newest diluted share counts from quarterly filings and computes " +
      "compound annual growth rate. Only counts positive growth (net issuance). " +
      "A high CAGR means the share count is growing quickly, which directly erodes per-share value.",
    calculation:
      "CAGR = (newest_shares / oldest_shares) ^ (4 / num_quarters) - 1. " +
      "Score = (CAGR / ceiling) \u00d7 100, capped at 100. Default ceiling: 50%.",
    timePeriod: "12 quarters (~3 years) of diluted shares outstanding",
    scoreInterpretation: "Higher score = faster share issuance = more dilution",
    defaultWeight: "25% of composite score",
  },

  fcf_burn: {
    label: "FCF Burn",
    shortDesc: "Annual cash burn rate relative to market cap",
    detailedDesc:
      "Companies burning cash faster relative to their market cap are more likely to raise capital " +
      "through dilutive offerings (secondary offerings, convertible debt, ATM programs). " +
      "This metric takes the mean of negative free cash flow quarters from the trailing 4 quarters, " +
      "annualizes it, and divides by market cap to get a burn rate. " +
      "Absurd outliers (e.g. bad data from the source API) are automatically excluded using IQR-based detection.",
    calculation:
      "Burn rate = avg(trailing 4Q negative FCF) \u00d7 4 / market cap. " +
      "Score = |burn_rate| / ceiling \u00d7 100, capped at 100. Default ceiling: 70%.",
    timePeriod: "Trailing 4 quarters (with IQR outlier filtering)",
    scoreInterpretation: "Higher score = burning cash faster relative to size",
    defaultWeight: "20% of composite score",
    caveat: "Only counts quarters with negative FCF; profitable quarters are excluded from the average. Statistical outliers are filtered to prevent bad source data from skewing results.",
  },

  sbc_revenue: {
    label: "SBC / Revenue",
    shortDesc: "Stock-based compensation as a fraction of revenue",
    detailedDesc:
      "Stock-based compensation (SBC) is a non-cash expense where companies pay employees with equity " +
      "instead of cash. High SBC relative to revenue means the company is heavily relying on equity " +
      "to fund operations, diluting shareholders in the process. " +
      "If SBC exists but revenue is zero or negative, the score automatically maxes at 100 " +
      "(worst case: diluting shareholders with no revenue to show for it).",
    calculation:
      "Ratio = sum(trailing 4Q SBC) / sum(trailing 4Q revenue). " +
      "Score = ratio / ceiling \u00d7 100, capped at 100. Default ceiling: 60%. " +
      "Special case: SBC > 0 and revenue \u2264 0 \u2192 score = 100.",
    timePeriod: "Trailing 4 quarters",
    scoreInterpretation: "Higher score = paying more in stock relative to revenue",
    defaultWeight: "15% of composite score",
  },

  offering_freq: {
    label: "Offering Frequency",
    shortDesc: "Count of dilutive SEC filings in 3 years",
    detailedDesc:
      "Counts SEC filings classified as dilutive events over the past 3 years. These include " +
      "ATM program registrations, registered direct offerings, follow-on offerings, " +
      "convertible debt issuances, and PIPE (Private Investment in Public Equity) deals. " +
      "A high count signals a habitual diluter \u2014 a company that repeatedly taps equity markets " +
      "to fund operations.",
    calculation:
      "Count of filings where is_dilution_event = true in the last 3 years. " +
      "Score = count / ceiling \u00d7 100, capped at 100. Default ceiling: 7 filings.",
    timePeriod: "3 years from today",
    scoreInterpretation: "Higher score = more frequent dilutive offerings",
    defaultWeight: "20% of composite score",
    caveat: "Accuracy depends on SEC filing classification. Some edge cases may be missed or misclassified.",
  },

  cash_runway: {
    label: "Cash Runway",
    shortDesc: "Months of cash remaining at current burn rate",
    detailedDesc:
      "Estimates how long the company can survive on its current cash balance at its current " +
      "cash burn rate. Companies with short runways face pressure to raise capital \u2014 often " +
      "through dilutive offerings \u2014 to keep operating. " +
      "The score is inverse: shorter runway = higher score. " +
      "If the company isn't burning cash (all quarters have positive FCF), this metric returns null.",
    calculation:
      "Runway = latest_cash / abs(avg trailing 4Q FCF burn) \u00d7 3 months. " +
      "Score = (max_months - runway) / max_months \u00d7 100, min 0. Default max: 24 months.",
    timePeriod: "Latest quarter cash balance; trailing 4 quarters for average burn rate (with IQR outlier filtering)",
    scoreInterpretation: "Higher score = less cash runway = higher urgency to raise capital",
    defaultWeight: "10% of composite score",
  },

  atm_active: {
    label: "ATM Active",
    shortDesc: "At-The-Market shelf registration risk",
    detailedDesc:
      "An ATM (At-The-Market) program is a shelf registration (S-3 filing) that gives a company " +
      "pre-approval to sell shares directly into the open market over time. Unlike a one-time " +
      "offering, an ATM lets them drip-sell shares whenever they want \u2014 silently diluting shareholders. " +
      "The score accounts for shelf age and selling activity: a fresh shelf with no sales is " +
      "peak risk (fully loaded, no dilution priced in yet), while an old shelf with heavy " +
      "selling is lower risk (capacity likely used up).",
    calculation:
      "Finds most recent S-3/S-3A or ATM filing within 2 years. " +
      "Checks for dilutive filings after the shelf date (evidence of selling). " +
      "Score decays based on age: <6mo no sales=100, <6mo selling=90, " +
      "6-12mo no sales=70, 6-12mo selling=80, 12-24mo no sales=25, 12-24mo selling=60. " +
      "No shelf in 2 years = 0.",
    timePeriod: "2 years (S-3 shelf registrations are valid for 3 years from filing)",
    scoreInterpretation: "Higher score = greater ATM dilution risk",
    defaultWeight: "10% of composite score",
    caveat:
      "Cannot detect whether ATM capacity is fully exhausted. " +
      "Ask the AI agent to check filing details for a specific company.",
  },
};
