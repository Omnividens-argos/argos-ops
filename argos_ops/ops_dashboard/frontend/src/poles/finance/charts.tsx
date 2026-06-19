// Mini-graphes du pôle Finance — rendus avec Recharts (v3, déjà installé), en
// gardant strictement les mêmes exports et signatures de props (FinancePage.tsx
// n'a pas besoin de changer). Couleurs via les tokens argos rgb(var(--…)) pour
// rester theme-aware (light/dark), grille/ticks alignés sur le kit Chart.tsx.
import { useId } from "react";
import {
  ResponsiveContainer,
  BarChart as RBarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";

type Tone = "neutral" | "info" | "healthy" | "warning" | "danger";

// Couleurs de remplissage par tone — tokens CSS theme-aware quand ils existent.
const TONE_FILL: Record<Tone, string> = {
  neutral: "rgb(var(--color-fg-tertiary))",
  info: "rgb(var(--color-info))",
  healthy: "rgb(var(--color-healthy))",
  warning: "rgb(var(--color-warning))",
  danger: "rgb(var(--color-danger))",
};

const GRID_STROKE = "rgb(var(--color-border))";
const AXIS_TICK = { fill: "rgb(var(--color-fg-tertiary))", fontSize: 10 };
const TOOLTIP_CONTENT_STYLE = {
  background: "rgb(var(--color-surface))",
  border: "1px solid rgb(var(--color-border))",
  borderRadius: "0.375rem",
  color: "rgb(var(--color-fg))",
  fontSize: 12,
};
const TOOLTIP_LABEL_STYLE = { color: "rgb(var(--color-fg-secondary))" };
const TOOLTIP_CURSOR = { fill: "rgb(var(--color-surface-2))", fillOpacity: 0.5 };

const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart
        data={data}
        margin={{ top: 16, right: 8, bottom: 0, left: 8 }}
        barCategoryGap="20%"
      >
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="label"
          tick={AXIS_TICK}
          tickLine={false}
          axisLine={{ stroke: GRID_STROKE }}
        />
        <YAxis hide />
        <Tooltip
          cursor={TOOLTIP_CURSOR}
          contentStyle={TOOLTIP_CONTENT_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
          formatter={(v) => format(Number(v))}
        />
        <Bar
          dataKey={(d: BarDatum) => Math.abs(d.value)}
          name="valeur"
          radius={[3, 3, 0, 0]}
          maxBarSize={56}
          isAnimationActive={!prefersReducedMotion}
          label={{
            position: "top",
            formatter: (v) => format(Number(v)),
            fill: "rgb(var(--color-fg-secondary))",
            fontSize: 10,
            fontFamily: "var(--font-mono, monospace)",
          }}
        >
          {data.map((d) => (
            <Cell key={d.id ?? d.label} fill={TONE_FILL[d.tone ?? "info"]} fillOpacity={0.7} />
          ))}
        </Bar>
      </RBarChart>
    </ResponsiveContainer>
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
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart
        data={data}
        margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
        barCategoryGap="20%"
        stackOffset="sign"
      >
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ ...AXIS_TICK, fontSize: 9 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis hide />
        <ReferenceLine y={0} stroke="rgb(var(--color-border))" />
        <Tooltip
          cursor={TOOLTIP_CURSOR}
          contentStyle={TOOLTIP_CONTENT_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
          formatter={(v) => format(Number(v))}
        />
        <Bar
          dataKey="value"
          name="net"
          radius={[2, 2, 2, 2]}
          maxBarSize={48}
          isAnimationActive={!prefersReducedMotion}
        >
          {data.map((d) => (
            <Cell
              key={d.id ?? d.label}
              fill={d.value >= 0 ? TONE_FILL.healthy : TONE_FILL.danger}
              fillOpacity={0.7}
            />
          ))}
        </Bar>
      </RBarChart>
    </ResponsiveContainer>
  );
}

// --- Jauge horizontale (runway) — meter accessible, rendu div (pas un graphe) -
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
  const labelId = useId();
  const v = value ?? max;
  const pct = Math.min(100, Math.max(0, (v / max) * 100));
  const tone: Tone =
    value === null ? "healthy" : v < alert ? "danger" : v < warn ? "warning" : "healthy";
  const alertPct = Math.min(100, (alert / max) * 100);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span
          id={labelId}
          className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary"
        >
          {label}
        </span>
        <span className="font-mono text-sm tabular-nums text-argos-fg">
          {value === null ? "∞" : `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} m`}
        </span>
      </div>
      <div
        role="meter"
        aria-valuenow={value ?? max}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-labelledby={labelId}
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-argos-surface-2"
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: `${pct}%`,
            backgroundColor: TONE_FILL[tone],
            transitionDuration: prefersReducedMotion ? "0ms" : undefined,
          }}
        />
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
