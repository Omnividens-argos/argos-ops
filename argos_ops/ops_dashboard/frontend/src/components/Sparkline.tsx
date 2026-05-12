// Sparkline SVG natif — pas de Recharts/visx pour ces micros viz.
// Source : docs/UI_DECISIONS.md § 5 (révision 2026-05-12).

interface Props {
  values: number[];
  width?: number;
  height?: number;
  /** Couleur de la courbe (Tailwind class, ex: "text-argos-info"). */
  colorClass?: string;
  /** Affiche un point sur la dernière valeur. */
  showLastPoint?: boolean;
}

export function Sparkline({
  values,
  width = 80,
  height = 24,
  colorClass = "text-argos-info",
  showLastPoint = true,
}: Props) {
  if (values.length === 0) {
    return (
      <div
        className="font-mono text-[10px] text-argos-fg-disabled"
        style={{ width, height, lineHeight: `${height}px` }}
      >
        —
      </div>
    );
  }

  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = max - min || 1;
  const pad = 2;
  const stepX = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;

  const points = values
    .map((v, i) => {
      const x = pad + i * stepX;
      const y = height - pad - ((v - min) / range) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastX = pad + (values.length - 1) * stepX;
  const lastY =
    height - pad - ((values[values.length - 1]! - min) / range) * (height - pad * 2);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={colorClass}
      role="img"
      aria-label={`Tendance ${values.length} points, min ${min}, max ${max}`}
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {showLastPoint && (
        <circle cx={lastX} cy={lastY} r={2} fill="currentColor" />
      )}
    </svg>
  );
}
