// Helpers purs du pôle Vente (front) — miroir de argos_ops/poles/vente/*.
// Formatage €/%/dates + tons de badges (catégorie inbox, priorité ticket, bande
// santé, stade pipe). Aucune dépendance hors types.

type Tone = "neutral" | "info" | "healthy" | "warning" | "danger";

// --- Catégories inbox ---------------------------------------------------------
export const CATEGORY_TONE: Record<string, Tone> = {
  lead_chaud: "healthy",
  question_tech: "info",
  sav: "warning",
  partenariat: "info",
  recrutement: "neutral",
  presse: "info",
  spam: "danger",
  autre: "neutral",
};

export const CATEGORY_LABEL: Record<string, string> = {
  lead_chaud: "lead chaud",
  question_tech: "question tech",
  sav: "SAV",
  partenariat: "partenariat",
  recrutement: "recrutement",
  presse: "presse",
  spam: "spam",
  autre: "autre",
};

// --- Priorité ticket ----------------------------------------------------------
export const PRIORITY_TONE: Record<string, Tone> = {
  P0: "danger",
  P1: "warning",
  P2: "neutral",
};

// --- Bande santé --------------------------------------------------------------
export const BAND_TONE: Record<string, Tone> = {
  green: "healthy",
  yellow: "warning",
  red: "danger",
};

// --- Stade pipe ---------------------------------------------------------------
export const STAGE_LABEL: Record<string, string> = {
  discovery: "Découverte",
  demo_scheduled: "Démo calée",
  demo_done: "Démo faite",
  proposal_sent: "Devis envoyé",
  contract_sent: "Contrat envoyé",
  won: "Gagné",
  lost: "Perdu",
};

export function stageLabel(stage: string): string {
  return STAGE_LABEL[stage] ?? stage;
}

// Ton du score de risque deal (0-100) : ≥60 danger, ≥35 warning, sinon info.
export function riskTone(score: number): Tone {
  if (score >= 60) return "danger";
  if (score >= 35) return "warning";
  return "info";
}

// --- Formatage ----------------------------------------------------------------
export function eur(x: number): string {
  return `${x.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €`;
}

export function pct(x: number, digits = 0): string {
  return `${(x * 100).toFixed(digits)}%`;
}

export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function dateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${shortDate(iso)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
