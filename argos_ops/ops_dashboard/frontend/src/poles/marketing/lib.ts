// Helpers purs du pôle Marketing (front) — miroir de argos_ops/poles/marketing/*.
// Sévérité, statut de draft, canaux, dates. Aucune dépendance externe.

import type { DraftStatus, MarketingChannel, Severity } from "../api.ts";
import type { AlertTone } from "../components/index.ts";

// --- Sévérité (aligné sur editorial.record_severity côté Python) -------------
const SEVERITY_RANK: Record<Severity, number> = { info: 0, warning: 1, critical: 2 };
export function severityRank(s: Severity): number {
  return SEVERITY_RANK[s] ?? 0;
}

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

// --- Statut de draft ---------------------------------------------------------
export const STATUS_TONE: Record<DraftStatus, "neutral" | "info" | "healthy" | "warning" | "danger"> =
  {
    draft: "warning",
    validated: "info",
    published: "healthy",
    rejected: "danger",
  };

export const STATUS_LABEL: Record<DraftStatus, string> = {
  draft: "à valider",
  validated: "validé",
  published: "publié",
  rejected: "rejeté",
};

// --- Canaux ------------------------------------------------------------------
export function channelLabel(channels: MarketingChannel[], id: string): string {
  return channels.find((c) => c.id === id)?.label ?? id;
}

export function channelById(
  channels: MarketingChannel[],
  id: string,
): MarketingChannel | undefined {
  return channels.find((c) => c.id === id);
}

// --- Dates -------------------------------------------------------------------
const DAY_MS = 24 * 3600 * 1000;

export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Clé de jour AAAA-MM-JJ (local) pour regrouper les drafts par date. */
export function dayKey(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Les `count` jours à partir d'aujourd'hui (minuit local). */
export function upcomingDays(count: number, now: number = Date.now()): Date[] {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  return Array.from({ length: count }, (_, i) => new Date(start.getTime() + i * DAY_MS));
}

/** Libellé court de jour : « lun. 17/06 ». */
export function dayLabel(d: Date): string {
  const wd = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."][d.getDay()];
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${wd} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
}

/** ISO 8601 pour planifier un draft à 09:00 (heure locale) le jour donné. */
export function scheduleAt(day: Date, hour = 9): string {
  const d = new Date(day);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

export function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

// Slug kebab-case (parité avec drafts.slugify côté Python : translittère les
// accents). Utilisé pour dériver le slug d'une nouvelle fiche KB.
export function slugify(text: string): string {
  const ascii = text.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  const kebab = ascii
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return kebab || "fiche";
}
