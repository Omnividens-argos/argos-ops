// Composant partagé « carte alerte » — surface une alerte d'un pôle (watcher
// SRE, baisse MRR, SLA breach, etc.). Réutilisé par chaque onglet pôle.
// En S0 : rendu + état vide ; les sessions pôle passent de vraies alertes.

export type AlertTone = "info" | "healthy" | "warning" | "danger";

export interface AlertCardProps {
  tone: AlertTone;
  title: string;
  detail?: string;
  /** Horodatage lisible (optionnel). */
  time?: string;
}

const TONE_STYLES: Record<AlertTone, { bar: string; title: string; bg: string }> = {
  info: { bar: "bg-argos-info", title: "text-argos-info", bg: "bg-argos-info/5" },
  healthy: { bar: "bg-argos-healthy", title: "text-argos-healthy", bg: "bg-argos-healthy/5" },
  warning: { bar: "bg-argos-warning", title: "text-argos-warning", bg: "bg-argos-warning/5" },
  danger: { bar: "bg-argos-danger", title: "text-argos-danger", bg: "bg-argos-danger/5" },
};

export function AlertCard({ tone, title, detail, time }: AlertCardProps) {
  const s = TONE_STYLES[tone];
  return (
    <div
      className={`flex gap-3 rounded-md border border-argos-border-subtle ${s.bg} px-3 py-2.5`}
    >
      <span className={`mt-0.5 w-1 shrink-0 rounded-full ${s.bar}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className={`font-mono text-xs font-medium ${s.title}`}>{title}</span>
          {time && <span className="font-mono text-[10px] text-argos-fg-tertiary">{time}</span>}
        </div>
        {detail && (
          <p className="mt-0.5 font-mono text-[11px] leading-snug text-argos-fg-secondary">
            {detail}
          </p>
        )}
      </div>
    </div>
  );
}

/** État vide réutilisable (aucune alerte = tout vert). */
export function AlertCardEmpty() {
  return (
    <AlertCard
      tone="healthy"
      title="Aucune alerte"
      detail="Tout est vert pour ce pôle — rien ne requiert d'attention."
    />
  );
}
