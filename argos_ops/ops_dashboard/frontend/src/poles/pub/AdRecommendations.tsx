// Recommandations chiffrées de l'optimiseur (€/semaine), triées par gravité.
// Bouton « appliquer » (shadow) par reco ; une action augmentatrice de dépense
// est désactivée si le breaker est armé. Miroir de pub/optimizer.recommend.

import type { AdPlatform, AdRecommendation } from "../api.ts";
import { Badge, Button } from "../../components/ui.tsx";
import {
  SEVERITY_BAR,
  SEVERITY_LABEL,
  SEVERITY_TONE,
  actionLabel,
  eurSigned,
  platformLabel,
} from "./lib.ts";

export interface AdRecommendationsProps {
  recommendations: AdRecommendation[];
  platforms: AdPlatform[];
  busyId: string | null;
  onApply: (rec: AdRecommendation) => void;
}

export function AdRecommendations({
  recommendations,
  platforms,
  busyId,
  onApply,
}: AdRecommendationsProps) {
  if (recommendations.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucune recommandation — l'optimiseur n'a rien à proposer (data/poles/pub/campaigns/).
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {recommendations.map((rec) => {
        const deltaTone =
          rec.eur_delta_week < 0
            ? "text-argos-healthy"
            : rec.eur_delta_week > 0
              ? "text-argos-warning"
              : "text-argos-fg-tertiary";
        return (
          <li
            key={rec.id}
            className="flex gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5"
          >
            <span
              className={`mt-0.5 w-1 shrink-0 rounded-full ${SEVERITY_BAR[rec.severity] ?? "bg-argos-info"}`}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={SEVERITY_TONE[rec.severity] ?? "info"}>
                  {SEVERITY_LABEL[rec.severity] ?? rec.severity}
                </Badge>
                <span className="font-mono text-xs font-medium text-argos-fg">
                  {actionLabel(rec.action)}
                </span>
                <Badge tone="neutral">{platformLabel(platforms, rec.platform)}</Badge>
                <span className="truncate font-mono text-[10px] text-argos-fg-disabled">
                  {rec.campaign}
                </span>
              </div>
              <p className="mt-1 font-mono text-[11px] leading-snug text-argos-fg-secondary">
                {rec.rationale}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-3 font-mono text-[10px] text-argos-fg-tertiary">
                {rec.eur_delta_week !== 0 && (
                  <span className={deltaTone}>{eurSigned(rec.eur_delta_week)}/sem</span>
                )}
                {rec.metrics.cpa > 0 && <span>CPA {rec.metrics.cpa.toFixed(0)} €</span>}
                {rec.metrics.ctr > 0 && <span>CTR {(rec.metrics.ctr * 100).toFixed(1)}%</span>}
              </div>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              {rec.applied ? (
                <Badge tone="healthy">appliquée</Badge>
              ) : (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={busyId === rec.id || rec.blocked_by_breaker}
                  onClick={() => onApply(rec)}
                  title={
                    rec.blocked_by_breaker
                      ? "Action augmentatrice de dépense — gelée tant que le breaker est armé"
                      : "Appliquer en shadow"
                  }
                >
                  appliquer
                </Button>
              )}
              {rec.blocked_by_breaker && !rec.applied && (
                <span className="font-mono text-[9px] text-argos-danger">gelé breaker</span>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
