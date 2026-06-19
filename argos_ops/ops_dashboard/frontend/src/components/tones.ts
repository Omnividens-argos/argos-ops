// Unified semantic-tone helper module for the Argos Ops cockpit.
// Pure TypeScript (no JSX). Maps a semantic Tone to Tailwind class strings
// using the dual light/dark design tokens. Use these helpers everywhere a
// component needs to color text / fills / borders by severity — never raw hex.

export type Tone = "neutral" | "healthy" | "info" | "warning" | "danger";

const TEXT: Record<Tone, string> = {
  neutral: "text-argos-fg-secondary",
  healthy: "text-argos-healthy",
  info: "text-argos-info",
  warning: "text-argos-warning",
  danger: "text-argos-danger",
};

const BG: Record<Tone, string> = {
  neutral: "bg-argos-surface-2",
  healthy: "bg-argos-healthy/15",
  info: "bg-argos-info/15",
  warning: "bg-argos-warning/15",
  danger: "bg-argos-danger/15",
};

const BORDER: Record<Tone, string> = {
  neutral: "border-argos-border",
  healthy: "border-argos-healthy/40",
  info: "border-argos-info/40",
  warning: "border-argos-warning/40",
  danger: "border-argos-danger/40",
};

/** Tailwind text-color class for the given tone. */
export function toneText(t: Tone): string {
  return TEXT[t];
}

/** Tailwind soft background-fill class for the given tone. */
export function toneBg(t: Tone): string {
  return BG[t];
}

/** Tailwind border-color class for the given tone. */
export function toneBorder(t: Tone): string {
  return BORDER[t];
}

/**
 * Categorical palette for charts. Index 0/2/3 mirror the info/healthy/warning
 * design tokens (CSS vars => theme-aware); the rest are fixed accents for
 * series that need additional, visually-distinct hues.
 */
export const CHART_COLORS: string[] = [
  "rgb(var(--color-info))",
  "#8b5cf6",
  "rgb(var(--color-healthy))",
  "rgb(var(--color-warning))",
  "#d946ef",
  "#06b6d4",
];
