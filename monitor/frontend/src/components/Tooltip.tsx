import type { ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  position?: "top" | "bottom";
  maxWidth?: string;
}

export default function Tooltip({
  content,
  children,
  position = "bottom",
  maxWidth = "max-w-xs",
}: TooltipProps) {
  const positionClasses =
    position === "top"
      ? "bottom-full left-1/2 -translate-x-1/2 mb-2"
      : "top-full left-1/2 -translate-x-1/2 mt-2";

  return (
    <span className="relative group/tooltip inline-flex items-center">
      {children}
      <span className="ml-1 inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-muted/40 text-muted group-hover/tooltip:text-accent group-hover/tooltip:border-accent/40 cursor-help text-[9px] leading-none font-medium select-none">
        i
      </span>
      <div
        className={`absolute z-50 ${positionClasses} ${maxWidth} bg-surface border border-border rounded-lg shadow-lg p-3 text-xs text-gray-300 leading-relaxed opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-opacity duration-150 pointer-events-none whitespace-normal`}
      >
        {content}
      </div>
    </span>
  );
}

/** Formatted tooltip content for a MetricDefinition */
export function MetricTooltipContent({
  shortDesc,
  calculation,
  timePeriod,
  scoreInterpretation,
  caveat,
}: {
  shortDesc: string;
  calculation: string;
  timePeriod: string;
  scoreInterpretation?: string;
  caveat?: string;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-gray-200 font-medium">{shortDesc}</p>
      <p>
        <span className="text-muted">Calculation: </span>
        {calculation}
      </p>
      <p>
        <span className="text-muted">Period: </span>
        {timePeriod}
      </p>
      {scoreInterpretation && (
        <p>
          <span className="text-muted">Interpretation: </span>
          {scoreInterpretation}
        </p>
      )}
      {caveat && (
        <p className="text-warning/80 italic">{caveat}</p>
      )}
    </div>
  );
}

/** Detailed tooltip for CompanyDetail ScoreCards */
export function DetailedMetricTooltipContent({
  detailedDesc,
  calculation,
  timePeriod,
  scoreInterpretation,
  defaultWeight,
  caveat,
}: {
  detailedDesc: string;
  calculation: string;
  timePeriod: string;
  scoreInterpretation: string;
  defaultWeight: string;
  caveat?: string;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-gray-200">{detailedDesc}</p>
      <div className="border-t border-border/50 pt-1.5 space-y-1">
        <p>
          <span className="text-muted">Calculation: </span>
          {calculation}
        </p>
        <p>
          <span className="text-muted">Period: </span>
          {timePeriod}
        </p>
        <p>
          <span className="text-muted">Score: </span>
          {scoreInterpretation}
        </p>
        <p>
          <span className="text-muted">Weight: </span>
          {defaultWeight}
        </p>
      </div>
      {caveat && (
        <p className="text-warning/80 italic border-t border-border/50 pt-1.5">
          {caveat}
        </p>
      )}
    </div>
  );
}
