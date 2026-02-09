interface ScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

export default function ScoreBadge({ score, size = "md" }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center justify-center rounded bg-border/50 text-muted font-mono text-xs px-2 py-0.5">
        N/A
      </span>
    );
  }

  const color =
    score >= 75
      ? "bg-danger/20 text-danger border-danger/30"
      : score >= 50
        ? "bg-warning/20 text-warning border-warning/30"
        : score >= 25
          ? "bg-accent/20 text-accent border-accent/30"
          : "bg-success/20 text-success border-success/30";

  const sizeClasses =
    size === "lg"
      ? "text-2xl px-3 py-1.5 min-w-[4rem]"
      : size === "md"
        ? "text-sm px-2 py-0.5 min-w-[3rem]"
        : "text-xs px-1.5 py-0.5 min-w-[2.5rem]";

  return (
    <span
      className={`inline-flex items-center justify-center rounded border font-mono font-semibold ${color} ${sizeClasses}`}
    >
      {score.toFixed(1)}
    </span>
  );
}
