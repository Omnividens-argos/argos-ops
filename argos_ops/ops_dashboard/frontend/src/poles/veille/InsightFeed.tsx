// Flux d'insights de veille : la synthèse du VeilleAgent (un insight par famille
// de signal), triée du plus grave au moins grave, avec bouton « pousser vers … ».

import type { InsightOut } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { PushControl } from "./PushControl.tsx";
import { SEVERITY_LABEL, SEVERITY_TONE } from "./lib.ts";

const SEVERITY_BAR: Record<string, string> = {
  info: "bg-argos-info",
  warning: "bg-argos-warning",
  critical: "bg-argos-danger",
};

export interface InsightFeedProps {
  insights: InsightOut[];
  pushed: Set<string>; // clés `${recordId}:${pole}`
  busy: string | null;
  onPush: (recordId: string, targetPole: string) => void;
}

export function InsightFeed({ insights, pushed, busy, onPush }: InsightFeedProps) {
  if (insights.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucun insight pour ce filtre.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {insights.map((insight) => {
        const primaryId = insight.record_ids[0] ?? "";
        const pushedPoles = new Set(
          insight.suggested_poles.filter((p) => pushed.has(`${primaryId}:${p}`)),
        );
        const busyPole =
          busy && busy.startsWith(`${primaryId}:`) ? busy.split(":")[1] ?? null : null;
        return (
          <li
            key={insight.kind}
            className="flex gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5"
          >
            <span
              className={`mt-0.5 w-1 shrink-0 rounded-full ${SEVERITY_BAR[insight.severity] ?? "bg-argos-info"}`}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={SEVERITY_TONE[insight.severity]}>
                  {SEVERITY_LABEL[insight.severity]}
                </Badge>
                <span className="font-mono text-xs font-medium text-argos-fg">{insight.title}</span>
                <Badge tone="neutral">{insight.theme}</Badge>
              </div>
              <p className="mt-1 font-mono text-[11px] leading-snug text-argos-fg-secondary">
                {insight.summary}
              </p>
              <div className="mt-2">
                <PushControl
                  poles={insight.suggested_poles}
                  pushedPoles={pushedPoles}
                  busyPole={busyPole}
                  onPush={(pole) => onPush(primaryId, pole)}
                />
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
