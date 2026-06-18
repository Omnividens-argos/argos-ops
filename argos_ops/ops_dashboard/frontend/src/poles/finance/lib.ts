// Helpers purs du pôle Finance (front) — miroir de argos_ops/poles/finance/*.
// Formatage €/% /dates + tons de badges (dunning, sévérité burn, statut contrat,
// risque AI Act, échéance fiscale). Aucune dépendance hors types.

type Tone = "neutral" | "info" | "healthy" | "warning" | "danger";

// --- Formatage € -------------------------------------------------------------
export function eur(x: number): string {
  return `${x.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €`;
}

export function eur2(x: number): string {
  return `${x.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function signedEur(x: number): string {
  return `${x >= 0 ? "+" : ""}${eur2(x)}`;
}

export function months(x: number | null): string {
  return x === null ? "∞" : `${x.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} m`;
}

// --- Dunning -----------------------------------------------------------------
export const DUNNING_TONE: Record<string, Tone> = {
  "J+3": "warning",
  "J+7": "warning",
  "J+15": "danger",
  none: "neutral",
};

// --- Sévérité burn -----------------------------------------------------------
export const BURN_TONE: Record<string, Tone> = {
  ok: "healthy",
  warn: "warning",
  alert: "danger",
};

// --- Statut contrat (fournisseur + client) -----------------------------------
export const CONTRACT_TONE: Record<string, Tone> = {
  ok: "healthy",
  approaching: "info",
  warn: "info",
  urgent: "warning",
  missed: "danger",
  expired: "danger",
};

// --- Risque AI Act -----------------------------------------------------------
export const AI_ACT_TONE: Record<string, Tone> = {
  minimal: "healthy",
  limited: "info",
  high: "warning",
  prohibited: "danger",
  unclassified: "warning",
};

// --- Échéance fiscale --------------------------------------------------------
export const FISCAL_LABEL: Record<string, string> = {
  tva_ca3: "TVA CA3",
  is_acompte: "Acompte IS",
  cfe: "CFE",
  liasse: "Liasse",
};

// Ton d'une échéance selon sa proximité (jours).
export function deadlineTone(days: number): Tone {
  if (days <= 7) return "danger";
  if (days <= 30) return "warning";
  return "neutral";
}

// Catégorie de dépense → ton (revenue vert, sortie neutre).
export function flowTone(direction: string): Tone {
  return direction === "in" ? "healthy" : "neutral";
}

// --- Dates -------------------------------------------------------------------
export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const DOC_KIND_LABEL: Record<string, string> = {
  ca3: "CA3 (TVA)",
  forecast: "Forecast",
  proposal: "Devis",
  contract: "Contrat",
  upload: "Uploadé",
  other: "Doc",
};
