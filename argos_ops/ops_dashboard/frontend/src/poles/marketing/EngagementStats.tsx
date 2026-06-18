// Stats d'engagement social par canal (fenêtre 7j) — miroir de
// social_analytics. Barre de CTR par canal + drapeau « signal faible »
// (CTR < 1% ou ER < 2%, même règle que le script Python).

import type { MarketingEngagement } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { pct } from "./lib.ts";

export interface EngagementStatsProps {
  engagement: MarketingEngagement[];
}

export function EngagementStats({ engagement }: EngagementStatsProps) {
  if (engagement.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucune mesure d'engagement dans la fenêtre 7j (data/social/engagement.yaml).
      </div>
    );
  }
  // Échelle relative pour les barres : CTR max observé (min 2% pour lisibilité).
  const maxCtr = Math.max(0.02, ...engagement.map((e) => e.ctr));

  return (
    <div className="flex flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
      {engagement.map((e) => (
        <div key={e.channel} className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-medium text-argos-fg">{e.channel}</span>
              {e.weak && <Badge tone="warning">signal faible</Badge>}
            </div>
            <span className="font-mono text-[11px] text-argos-fg-secondary">
              {e.posts} post(s) · {e.impressions} imp · CTR {pct(e.ctr)} · ER{" "}
              {pct(e.engagement_rate)}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-argos-surface-2">
            <div
              className={`h-full rounded-full ${e.weak ? "bg-argos-warning" : "bg-argos-healthy"}`}
              style={{ width: `${Math.min(100, (e.ctr / maxCtr) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
