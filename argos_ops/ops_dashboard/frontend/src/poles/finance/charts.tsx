// Mini-graphes du pôle Finance — composants SVG/div purs, zéro dépendance npm
// (pas de recharts : on reste local-first et léger). Couleurs via les classes
// Tailwind argos-* (listées en clair pour que le JIT les génère).

type Tone = "neutral" | "info" | "healthy" | "warning" | "danger";

const TONE_BG: Record<Tone, string> = {
  neutral: "bg-argos-fg-tertiary/40",
  info: "bg-argos-info/70",
  healthy: "bg-argos-healthy/70",
  warning: "bg-argos-warning/70",
  danger: "bg-argos-danger/70",
};

export interface BarDatum {
  label: string;
  value: number;
  tone?: Tone;
  /** Clé React stable et unique (le label seul peut se répéter — ex. mois sur 2 ans). */
  id?: string;
}

// --- Barres verticales (valeurs >= 0) : forecast, burn vs revenue -------------
export function BarChart({
  data,
  format,
  height = 132,
}: {
  data: BarDatum[];
  format: (v: number) => string;
  height?: number;
}) {
  const max = Math.max(1, ...data.map((d) => Math.abs(d.value)));
  const barArea = height - 34;
  return (
    <div className="flex items-end gap-4" style={{ height }}>
      {data.map((d) => (
        <div key={d.id ?? d.label} className="flex flex-1 flex-col items-center justify-end gap-1">
          <span className="font-mono text-[10px] text-argos-fg-secondary">{format(d.value)}</span>
          <div className="flex w-full items-end justify-center" style={{ height: barArea }}>
            <div
              className={`w-full max-w-[3.5rem] rounded-t ${TONE_BG[d.tone ?? "info"]}`}
              style={{ height: `${Math.max(2, (Math.abs(d.value) / max) * 100)}%` }}
            />
          </div>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

// --- Barres divergentes (positif vert / négatif rouge) : net par mois ---------
export function DivergingBars({
  data,
  format,
  height = 132,
}: {
  data: BarDatum[];
  format: (v: number) => string;
  height?: number;
}) {
  const maxAbs = Math.max(1, ...data.map((d) => Math.abs(d.value)));
  const half = (height - 26) / 2;
  return (
    <div className="flex items-stretch gap-3" style={{ height }}>
      {data.map((d) => {
        const positive = d.value >= 0;
        const h = (Math.abs(d.value) / maxAbs) * half;
        return (
          <div key={d.id ?? d.label} className="flex flex-1 flex-col items-center">
            <div className="flex w-full flex-1 items-end justify-center">
              {positive && (
                <div
                  className={`w-full max-w-[3rem] rounded-t ${TONE_BG.healthy}`}
                  style={{ height: Math.max(2, h) }}
                />
              )}
            </div>
            <div className="h-px w-full bg-argos-border-subtle" />
            <div className="flex w-full flex-1 items-start justify-center">
              {!positive && (
                <div
                  className={`w-full max-w-[3rem] rounded-b ${TONE_BG.danger}`}
                  style={{ height: Math.max(2, h) }}
                />
              )}
            </div>
            <span className="mt-0.5 font-mono text-[9px] text-argos-fg-tertiary">{d.label}</span>
            <span className="font-mono text-[9px] text-argos-fg-secondary">{format(d.value)}</span>
          </div>
        );
      })}
    </div>
  );
}

// --- Jauge horizontale (runway) ----------------------------------------------
export function Gauge({
  value,
  max,
  alert,
  warn,
  label,
  caption,
}: {
  value: number | null;
  max: number;
  alert: number;
  warn: number;
  label: string;
  caption?: string;
}) {
  const v = value ?? max;
  const pct = Math.min(100, Math.max(0, (v / max) * 100));
  const tone: Tone =
    value === null ? "healthy" : v < alert ? "danger" : v < warn ? "warning" : "healthy";
  const alertPct = Math.min(100, (alert / max) * 100);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {label}
        </span>
        <span className="font-mono text-sm text-argos-fg">
          {value === null ? "∞" : `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} m`}
        </span>
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-argos-surface-2">
        <div className={`h-full rounded-full ${TONE_BG[tone]}`} style={{ width: `${pct}%` }} />
        <div
          className="absolute top-0 h-full w-px bg-argos-danger/60"
          style={{ left: `${alertPct}%` }}
          title={`seuil d'alerte ${alert} mois`}
        />
      </div>
      {caption && <span className="font-mono text-[10px] text-argos-fg-tertiary">{caption}</span>}
    </div>
  );
}
