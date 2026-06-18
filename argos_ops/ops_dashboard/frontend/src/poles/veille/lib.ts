// Helpers purs du pôle Veille (front) — miroir de argos_ops/poles/veille/insights.py.
// Sévérité d'un fait, thème/label par kind, filtrage par date. Aucune dépendance.

import type { MemoryFact, Severity } from "../api.ts";
import type { AlertTone } from "../components/index.ts";

// kind -> { label affichable, thème lisible } (aligné sur _KIND_ROUTING Python).
export const KIND_META: Record<string, { label: string; theme: string }> = {
  trend: { label: "Tendance", theme: "marché" },
  competitor: { label: "Concurrent", theme: "concurrence" },
  regulatory: { label: "Réglementaire", theme: "réglementaire" },
  breach: { label: "Breach", theme: "menace" },
  cve: { label: "CVE", theme: "menace" },
  darkweb: { label: "Dark web", theme: "menace" },
  press: { label: "Presse", theme: "réputation" },
  seo_movement: { label: "SERP", theme: "seo" },
  intent_signal: { label: "Intent", theme: "intention d'achat" },
};

export function kindLabel(kind: string): string {
  return KIND_META[kind]?.label ?? kind;
}

export function kindTheme(kind: string): string {
  return KIND_META[kind]?.theme ?? "autre";
}

// Familles de menace surfacées dans la carte breaches/CVE.
export const THREAT_KINDS = new Set(["breach", "cve", "darkweb"]);

// Sévérité d'un fait — même règle que record_severity() côté Python :
// tag "critical" > flag important > info.
export function recordSeverity(fact: MemoryFact): Severity {
  if (fact.tags.includes("critical")) return "critical";
  if (fact.important) return "warning";
  return "info";
}

const SEVERITY_RANK: Record<Severity, number> = { info: 0, warning: 1, critical: 2 };
export function severityRank(s: Severity): number {
  return SEVERITY_RANK[s] ?? 0;
}

// Sévérité -> tonalité des composants partagés (AlertCard / Badge).
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

export type DateRange = "all" | "24h" | "7d" | "30d";

const RANGE_MS: Record<Exclude<DateRange, "all">, number> = {
  "24h": 24 * 3600 * 1000,
  "7d": 7 * 24 * 3600 * 1000,
  "30d": 30 * 24 * 3600 * 1000,
};

export function withinRange(iso: string, range: DateRange, now: number = Date.now()): boolean {
  if (range === "all") return true;
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return true;
  return now - ts <= RANGE_MS[range];
}

// Recherche plein-texte simple sur corps + tags + script.
export function matchesQuery(fact: MemoryFact, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    fact.body.toLowerCase().includes(q) ||
    fact.script.toLowerCase().includes(q) ||
    fact.tags.some((t) => t.toLowerCase().includes(q))
  );
}

// Horodatage compact AAAA-MM-JJ HH:MM (sans dépendance externe).
export function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
