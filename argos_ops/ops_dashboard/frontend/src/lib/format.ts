// Helpers de formatage pour l'UI dense — timestamps, durées, statuts.
// Centralisé ici pour cohérence cross-views (Overview / Agents / Runs).

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const diffSeconds = (Date.now() - date.getTime()) / 1000;
  if (diffSeconds < 60) return `il y a ${Math.floor(diffSeconds)}s`;
  if (diffSeconds < 3600) return `il y a ${Math.floor(diffSeconds / 60)}min`;
  if (diffSeconds < 86400) return `il y a ${Math.floor(diffSeconds / 3600)}h`;
  const days = Math.floor(diffSeconds / 86400);
  return `il y a ${days}j`;
}

export function formatAbsoluteTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)} ms`;
  if (seconds < 60) return `${seconds.toFixed(2)} s`;
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}

export function formatEur(amount: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function statusColor(status: string | null): string {
  switch (status) {
    case "success":
      return "text-argos-healthy";
    case "failed":
      return "text-argos-danger";
    case "killed_by_breaker":
      return "text-argos-warning";
    default:
      return "text-argos-fg-tertiary";
  }
}

export function statusBgColor(status: string | null): string {
  switch (status) {
    case "success":
      return "bg-argos-healthy/10 border-argos-healthy/30";
    case "failed":
      return "bg-argos-danger/10 border-argos-danger/30";
    case "killed_by_breaker":
      return "bg-argos-warning/10 border-argos-warning/30";
    default:
      return "bg-argos-surface-2/40 border-argos-border-subtle";
  }
}
