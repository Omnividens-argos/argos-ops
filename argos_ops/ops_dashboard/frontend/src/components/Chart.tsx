import { useId } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { CHART_COLORS } from "./tones.ts";
import { EmptyState } from "./EmptyState.tsx";
import { SkeletonBlock } from "./Skeleton.tsx";

export interface Series {
  key: string;
  name: string;
  color?: string;
}

export interface ChartProps {
  data: Record<string, number | string>[];
  series: Series[];
  xKey: string;
  height?: number;
  loading?: boolean;
  emptyTitle?: string;
}

const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const GRID_STROKE = "rgb(var(--color-border))";
const AXIS_TICK = { fill: "rgb(var(--color-fg-tertiary))", fontSize: 11 };
const TOOLTIP_CONTENT_STYLE = {
  background: "rgb(var(--color-surface))",
  border: "1px solid rgb(var(--color-border))",
  borderRadius: "0.375rem",
  color: "rgb(var(--color-fg))",
  fontSize: 12,
};
const TOOLTIP_LABEL_STYLE = { color: "rgb(var(--color-fg-secondary))" };
const LEGEND_STYLE = { fontSize: 12, color: "rgb(var(--color-fg-secondary))" };

function colorFor(series: Series, index: number): string {
  return series.color ?? CHART_COLORS[index % CHART_COLORS.length];
}

interface ChartFrameProps {
  loading?: boolean;
  empty: boolean;
  emptyTitle?: string;
  children: React.ReactElement;
  height: number;
}

function ChartFrame({
  loading,
  empty,
  emptyTitle,
  children,
  height,
}: ChartFrameProps) {
  if (loading) {
    return <SkeletonBlock height="h-48" />;
  }
  if (empty) {
    return (
      <EmptyState
        tone="neutral"
        title={emptyTitle ?? "Pas de données"}
        compact
      />
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      {children}
    </ResponsiveContainer>
  );
}

export function TimeSeriesChart({
  data,
  series,
  xKey,
  height,
  loading,
  emptyTitle,
  area,
}: ChartProps & { area?: boolean }) {
  const resolvedHeight = height ?? 240;
  const empty = data.length === 0;

  if (loading || empty) {
    return (
      <ChartFrame
        loading={loading}
        empty={empty}
        emptyTitle={emptyTitle}
        height={resolvedHeight}
      >
        <div />
      </ChartFrame>
    );
  }

  if (area) {
    return (
      <ChartFrame
        loading={loading}
        empty={empty}
        emptyTitle={emptyTitle}
        height={resolvedHeight}
      >
        <AreaChart data={data}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
          <XAxis dataKey={xKey} tick={AXIS_TICK} />
          <YAxis tick={AXIS_TICK} />
          <Tooltip
            contentStyle={TOOLTIP_CONTENT_STYLE}
            labelStyle={TOOLTIP_LABEL_STYLE}
          />
          <Legend wrapperStyle={LEGEND_STYLE} />
          {series.map((s, i) => {
            const c = colorFor(s, i);
            return (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={c}
                fill={c}
                fillOpacity={0.18}
                isAnimationActive={!prefersReducedMotion}
              />
            );
          })}
        </AreaChart>
      </ChartFrame>
    );
  }

  return (
    <ChartFrame
      loading={loading}
      empty={empty}
      emptyTitle={emptyTitle}
      height={resolvedHeight}
    >
      <LineChart data={data}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tick={AXIS_TICK} />
        <YAxis tick={AXIS_TICK} />
        <Tooltip
          contentStyle={TOOLTIP_CONTENT_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
        />
        <Legend wrapperStyle={LEGEND_STYLE} />
        {series.map((s, i) => {
          const c = colorFor(s, i);
          return (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={c}
              strokeWidth={2}
              dot={false}
              isAnimationActive={!prefersReducedMotion}
            />
          );
        })}
      </LineChart>
    </ChartFrame>
  );
}

export function CategoryBarChart({
  data,
  series,
  xKey,
  height,
  loading,
  emptyTitle,
}: ChartProps) {
  const resolvedHeight = height ?? 240;
  const empty = data.length === 0;

  if (loading || empty) {
    return (
      <ChartFrame
        loading={loading}
        empty={empty}
        emptyTitle={emptyTitle}
        height={resolvedHeight}
      >
        <div />
      </ChartFrame>
    );
  }

  return (
    <ChartFrame
      loading={loading}
      empty={empty}
      emptyTitle={emptyTitle}
      height={resolvedHeight}
    >
      <BarChart data={data}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tick={AXIS_TICK} />
        <YAxis tick={AXIS_TICK} />
        <Tooltip
          cursor={{ fill: "rgb(var(--color-surface-2))", fillOpacity: 0.5 }}
          contentStyle={TOOLTIP_CONTENT_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
        />
        <Legend wrapperStyle={LEGEND_STYLE} />
        {series.map((s, i) => {
          const c = colorFor(s, i);
          return (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={c}
              radius={[4, 4, 0, 0]}
              isAnimationActive={!prefersReducedMotion}
            />
          );
        })}
      </BarChart>
    </ChartFrame>
  );
}

type GaugeTone = "healthy" | "warning" | "danger";

export interface GaugeChartProps {
  value: number;
  max: number;
  label?: string;
  bands?: { upTo: number; tone: GaugeTone }[];
  height?: number;
}

const GAUGE_FILL_CLASS: Record<GaugeTone, string> = {
  healthy: "bg-argos-healthy",
  warning: "bg-argos-warning",
  danger: "bg-argos-danger",
};

function resolveGaugeTone(
  value: number,
  max: number,
  bands?: { upTo: number; tone: GaugeTone }[],
): GaugeTone {
  if (bands && bands.length > 0) {
    const sorted = [...bands].sort((a, b) => a.upTo - b.upTo);
    const match = sorted.find((b) => value <= b.upTo);
    if (match) {
      return match.tone;
    }
    return sorted[sorted.length - 1].tone;
  }
  const ratio = max > 0 ? value / max : 0;
  if (ratio < 0.5) {
    return "healthy";
  }
  if (ratio < 0.8) {
    return "warning";
  }
  return "danger";
}

export function GaugeChart({
  value,
  max,
  label,
  bands,
  height,
}: GaugeChartProps) {
  const labelId = useId();
  const safeMax = max > 0 ? max : 1;
  const ratio = Math.min(1, Math.max(0, value / safeMax));
  const tone = resolveGaugeTone(value, max, bands);
  const fillClass = GAUGE_FILL_CLASS[tone];
  const trackHeight = height ?? 12;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        {label ? (
          <span
            id={labelId}
            className="text-sm text-argos-fg-secondary"
          >
            {label}
          </span>
        ) : null}
        <span className="ml-auto font-mono text-sm tabular-nums text-argos-fg">
          {value}
          <span className="text-argos-fg-tertiary"> / {max}</span>
        </span>
      </div>
      <div
        role="meter"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
        aria-labelledby={label ? labelId : undefined}
        className="w-full overflow-hidden rounded-full bg-argos-surface-2"
        style={{ height: trackHeight }}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${fillClass}`}
          style={{
            width: `${ratio * 100}%`,
            transitionDuration: prefersReducedMotion ? "0ms" : undefined,
          }}
        />
      </div>
    </div>
  );
}
