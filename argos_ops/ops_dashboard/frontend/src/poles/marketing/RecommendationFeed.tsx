// Flux des recommandations éditoriales : synthèse du MarketingAgent à partir de
// la mémoire Veille (cross-pôle) + propre. Une reco par famille de signal, triée
// du plus grave au moins grave, avec l'angle et les canaux suggérés. Read-only —
// le fondateur s'en sert pour décider quoi drafter (via les skills writers).

import type { MarketingChannel, MarketingRecommendation } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { SEVERITY_BAR, SEVERITY_LABEL, SEVERITY_TONE, channelLabel } from "./lib.ts";

export interface RecommendationFeedProps {
  recommendations: MarketingRecommendation[];
  channels: MarketingChannel[];
}

export function RecommendationFeed({ recommendations, channels }: RecommendationFeedProps) {
  if (recommendations.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucune recommandation — la Veille n'a remonté aucun sujet éditorialisable.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {recommendations.map((rec) => (
        <li
          key={rec.kind}
          className="flex gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5"
        >
          <span
            className={`mt-0.5 w-1 shrink-0 rounded-full ${SEVERITY_BAR[rec.severity] ?? "bg-argos-info"}`}
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={SEVERITY_TONE[rec.severity]}>{SEVERITY_LABEL[rec.severity]}</Badge>
              <span className="font-mono text-xs font-medium text-argos-fg">{rec.angle}</span>
              <Badge tone="neutral">{rec.kind}</Badge>
              <span className="font-mono text-[10px] text-argos-fg-disabled">
                {rec.count} signal(aux)
              </span>
            </div>
            <p className="mt-1 line-clamp-2 font-mono text-[11px] leading-snug text-argos-fg-secondary">
              {rec.topic}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
                canaux →
              </span>
              {rec.channels.map((c) => (
                <Badge key={c} tone="info">
                  {channelLabel(channels, c)}
                </Badge>
              ))}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
