// Helpers partagés de l'onglet Mémoire (archi v2, S7).

/** Affichage compact AAAA-MM-JJ HH:MM (sans dépendance externe). */
export function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Affichage date seule AAAA-MM-JJ. */
export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Tonalité d'un motif de suppression / d'anomalie. */
export function severityTone(severity: string): "warning" | "danger" | "neutral" {
  if (severity === "warning") return "warning";
  if (severity === "critical" || severity === "danger") return "danger";
  return "neutral";
}
