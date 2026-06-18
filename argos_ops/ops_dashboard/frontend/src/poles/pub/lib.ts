// Helpers purs du pôle Pub (front) — miroir de argos_ops/poles/pub/*. Sévérité,
// statut de créa, libellés d'action, plateformes, formatage €/%. Aucune dépendance.

import type { AdPlatform, CreativeStatus, Severity } from "../api.ts";
import type { AlertTone } from "../components/index.ts";

// --- Sévérité (aligné sur optimizer.severity_rank côté Python) ---------------
export const SEVERITY_TONE: Record<Severity, AlertTone> = {
  info: "info",
  warning: "warning",
  critical: "danger",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  info: "info",
  warning: "à surveiller",
  critical: "critique",
};

export const SEVERITY_BAR: Record<Severity, string> = {
  info: "bg-argos-info",
  warning: "bg-argos-warning",
  critical: "bg-argos-danger",
};

// --- Statut de créa ----------------------------------------------------------
export const CREATIVE_STATUS_TONE: Record<
  CreativeStatus,
  "neutral" | "info" | "healthy" | "warning" | "danger"
> = {
  draft: "warning",
  validated: "info",
  live: "healthy",
  rejected: "danger",
};

export const CREATIVE_STATUS_LABEL: Record<CreativeStatus, string> = {
  draft: "à valider",
  validated: "validée",
  live: "en ligne",
  rejected: "rejetée",
};

// --- Actions de recommandation -----------------------------------------------
export const ACTION_LABEL: Record<string, string> = {
  pause: "Mettre en pause",
  drop_keyword: "Couper le mot-clé",
  new_creative: "Tester une nouvelle créa",
  diagnose_lp: "Auditer la landing page",
  scale: "Scaler",
  new_campaign: "Nouvelle campagne",
};

export function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? action;
}

// --- Plateformes -------------------------------------------------------------
export function platformLabel(platforms: AdPlatform[], id: string): string {
  return platforms.find((p) => p.id === id)?.label ?? id;
}

export function platformById(platforms: AdPlatform[], id: string): AdPlatform | undefined {
  return platforms.find((p) => p.id === id);
}

// --- Formatage ---------------------------------------------------------------
export function eur(x: number): string {
  return `${x.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €`;
}

export function eurSigned(x: number): string {
  const sign = x > 0 ? "+" : "";
  return `${sign}${eur(x)}`;
}

export function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
