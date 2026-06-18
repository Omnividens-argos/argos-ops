// Helpers purs du pôle Direction (front) — miroir de argos_ops/poles/direction/*.
// Formatage €/% /dates + tons de badges (santé pôle, statut OKR, sévérité plan/bug).
// Aucune dépendance hors types.

type Tone = "neutral" | "info" | "healthy" | "warning" | "danger";

// --- Formatage € -------------------------------------------------------------
export function eur(x: number | null): string {
  if (x === null) return "—";
  return `${x.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €`;
}

// --- Formatage % -------------------------------------------------------------
export function pct(x: number | null): string {
  if (x === null) return "—";
  return `${x.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

// --- Mois (runway) -----------------------------------------------------------
export function months(x: number | null): string {
  return x === null ? "∞" : `${x.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} m`;
}

// --- Ratio OKR (0..1) -> pourcentage --------------------------------------------
// Convention partagée avec le backend (argos_ops.agents.okr_tracker) : progress_pct
// et expected_pct sont des RATIOS dans [0,1]. On les affiche en multipliant par 100.
export function okrRatioToPct(ratio: number): number {
  return Math.round(ratio * 100);
}

// Largeur de barre bornée 0..100 à partir d'un ratio OKR (0..1).
export function okrBarWidth(ratio: number): number {
  return Math.min(100, Math.max(0, ratio * 100));
}

// --- Santé d'un pôle ---------------------------------------------------------
export const HEALTH_TONE: Record<string, Tone> = {
  critical: "danger",
  warning: "warning",
  healthy: "healthy",
  idle: "neutral",
};

// Icône (point coloré) d'une santé de pôle.
export function healthIcon(health: string): string {
  switch (health) {
    case "critical":
      return "●";
    case "warning":
      return "●";
    case "healthy":
      return "●";
    default:
      return "○";
  }
}

// --- Statut d'un key result OKR ----------------------------------------------
export const OKR_STATUS_TONE: Record<string, Tone> = {
  off_track: "danger",
  at_risk: "warning",
  on_track: "healthy",
  completed: "info",
};

// --- Sévérité (plan d'oversight, triage bugs) --------------------------------
export const SEVERITY_TONE: Record<string, Tone> = {
  critical: "danger",
  warning: "warning",
  info: "info",
  // sévérités bugs (P0/P1/P2)
  P0: "danger",
  P1: "warning",
  P2: "info",
};

// --- Libellés de type de doc généré ------------------------------------------
export const DOC_KIND_LABEL: Record<string, string> = {
  board: "Board pack",
  roadmap: "Roadmap",
  changelog: "Changelog",
  release_notes: "Release notes",
  other: "Doc",
};

// --- Dates -------------------------------------------------------------------
export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
