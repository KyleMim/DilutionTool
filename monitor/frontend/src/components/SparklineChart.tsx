interface SparklineChartProps {
  data: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
}

export default function SparklineChart({
  data,
  width = 80,
  height = 24,
  color = "#ef4444",
}: SparklineChartProps) {
  const values = data.filter((v): v is number => v !== null && v !== undefined);
  if (values.length < 2) return <span className="text-muted text-xs">--</span>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
