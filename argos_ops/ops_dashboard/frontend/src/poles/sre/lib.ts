// Helpers partagés de l'onglet SRE (archi v2, S8).

import type { SreSeverity } from "../api.ts";

/** Affichage compact AAAA-MM-JJ HH:MM (sans dépendance externe). */
export function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Durée en ms → lisible (ms / s / min). */
export function fmtDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${(ms / 60_000).toFixed(1)} min`;
}

/** Âge en heures → lisible (min / h / j). */
export function fmtAge(hours: number | null): string {
  if (hours === null) return "jamais";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} j`;
}

export type BadgeTone = "neutral" | "healthy" | "info" | "warning" | "danger";

/** Tonalité de badge d'une sévérité SRE (vert/jaune/rouge). */
export function severityTone(sev: SreSeverity | null): BadgeTone {
  if (sev === "red") return "danger";
  if (sev === "yellow") return "warning";
  if (sev === "green") return "healthy";
  return "neutral";
}

/** Classe de pastille (point coloré) d'une sévérité. */
export function severityDot(sev: SreSeverity): string {
  if (sev === "red") return "bg-argos-danger";
  if (sev === "yellow") return "bg-argos-warning";
  return "bg-argos-healthy";
}

/** Libellé FR d'une sévérité. */
export function severityLabel(sev: SreSeverity): string {
  return { green: "vert", yellow: "jaune", red: "rouge" }[sev];
}

/** Tonalité d'un verdict d'orchestrateur (launch vs skip). */
export function verdictTone(verdict: string): BadgeTone {
  if (verdict === "launch") return "healthy";
  if (verdict === "skipped_frozen" || verdict === "skipped_breaker") return "danger";
  return "neutral";
}

/** Statut d'un run → tonalité. */
export function runStatusTone(status: string): BadgeTone {
  if (status === "failed") return "danger";
  if (status === "skipped") return "neutral";
  return "healthy";
}
