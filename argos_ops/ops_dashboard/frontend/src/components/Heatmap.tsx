// Heatmap horizontale 12 cellules = 12 dernières heures d'activité.
// Source : docs/UI_DECISIONS.md § 5 (révision 2026-05-12).

interface HeatmapCell {
  label: string; // ex "14h-15h"
  count: number;
  failed?: number;
}

interface Props {
  cells: HeatmapCell[];
  height?: number;
}

export function Heatmap({ cells, height = 32 }: Props) {
  const maxCount = Math.max(...cells.map((c) => c.count), 1);

  return (
    <div
      className="flex gap-0.5 w-full"
      style={{ height }}
      role="img"
      aria-label={`Activité 12 dernières heures, max ${maxCount} runs/heure`}
    >
      {cells.map((cell, idx) => {
        const intensity =
          cell.count === 0 ? 0 : Math.max(0.15, Math.min(1, cell.count / maxCount));
        const hasFail = Boolean(cell.failed && cell.failed > 0);
        return (
          <div
            key={idx}
            title={`${cell.label} · ${cell.count} run${cell.count > 1 ? "s" : ""}${
              hasFail ? ` · ${cell.failed} échec${cell.failed! > 1 ? "s" : ""}` : ""
            }`}
            className={`flex-1 rounded-sm border ${
              cell.count === 0
                ? "bg-argos-surface-2 border-argos-border-subtle"
                : hasFail
                  ? "border-argos-danger/30"
                  : "border-argos-info/30"
            }`}
            style={
              cell.count > 0
                ? {
                    backgroundColor: hasFail
                      ? `rgb(var(--color-danger) / ${intensity})`
                      : `rgb(var(--color-info) / ${intensity})`,
                  }
                : undefined
            }
          />
        );
      })}
    </div>
  );
}
