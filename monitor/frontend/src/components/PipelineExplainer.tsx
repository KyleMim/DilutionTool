import { useState } from "react";
import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "Universe Pull",
    summary: "All US equities from FMP",
    detail:
      "Fetches the full list of US-listed equities from the Financial Modeling Prep API. Every company with a market cap greater than $0 is included as a starting point.",
  },
  {
    title: "Quick Screen",
    summary: "8Q fundamentals check",
    detail:
      "Each company's last 8 quarters of fundamentals are fetched and checked against qualification criteria. A company qualifies as a candidate if its 3-year share CAGR exceeds the minimum threshold (default 5%) OR it has enough quarters of negative free cash flow (default 4 of 8).",
  },
  {
    title: "Enrich",
    summary: "Full data + SEC filings",
    detail:
      "Qualified candidates get full data: 12 quarters of fundamentals from FMP (shares, FCF, SBC, revenue, cash) plus SEC filings from EDGAR. Filings are classified by dilution type: ATM programs, registered direct offerings, follow-on offerings, convertible debt, and PIPEs.",
  },
  {
    title: "Score & Rank",
    summary: "6 sub-scores \u2192 composite",
    detail:
      "Each candidate receives a composite dilution score (0\u2013100) computed as a weighted average of 6 sub-scores: Share CAGR (25%), FCF Burn (20%), Offering Frequency (20%), SBC/Revenue (15%), Cash Runway (10%), ATM Active (10%). Companies scoring above the watchlist threshold (default 25) are placed on the Watchlist; others go to Monitoring. Scores \u2265 75 are flagged Critical.",
  },
];

export default function PipelineExplainer() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-surface/50 border border-border/50 rounded-lg mb-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-muted hover:text-gray-200 transition-colors"
      >
        <svg
          className="w-3.5 h-3.5 text-accent flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
          />
        </svg>
        <span className="flex-1 text-left">
          <span className="text-gray-300">How we find companies:</span>{" "}
          {STEPS.map((s, i) => (
            <span key={i}>
              {i > 0 && (
                <span className="text-muted mx-1">{"\u2192"}</span>
              )}
              {s.title}
            </span>
          ))}
        </span>
        <svg
          className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-border/50">
          <div className="space-y-3">
            {STEPS.map((step, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-accent/20 text-accent text-xs font-medium flex items-center justify-center mt-0.5">
                  {i + 1}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-200">
                    {step.title}
                  </div>
                  <p className="text-xs text-muted mt-0.5 leading-relaxed">
                    {step.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-muted mt-3 pt-2 border-t border-border/30">
            Thresholds and weights can be adjusted on the{" "}
            <Link
              to="/config"
              className="text-accent hover:text-accent-hover"
            >
              Config page
            </Link>
            .
          </p>
        </div>
      )}
    </div>
  );
}
