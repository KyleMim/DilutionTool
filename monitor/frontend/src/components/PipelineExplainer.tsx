import { useState } from "react";
import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "Screen",
    detail:
      "Any public company with 3-year share CAGR >5% OR 4+ quarters of negative FCF qualifies as a candidate.",
  },
  {
    title: "Enrich",
    detail:
      "Qualified candidates enriched with 12 quarters of fundamentals (shares, FCF, SBC, revenue, cash) + SEC filings (ATM, offerings, convertibles).",
  },
  {
    title: "Score & Rank",
    detail:
      "After enrichment, scored using 6 weighted metrics. Tiered by percentile rank: top 10% = Critical, next 40% = Watchlist, bottom 50% = Monitoring.",
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
          <span className="text-gray-300">Method:</span>{" "}
          Composite score (0–100) from 6 weighted metrics. Ranked by percentile: top 10% Critical, next 40% Watchlist, bottom 50% Monitoring.
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
