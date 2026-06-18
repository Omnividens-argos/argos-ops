// Carte des menaces : breaches / CVE / dark web croisés avec le carnet client.
// Cartes colorées par sévérité (rouge = critique, ambre = à surveiller).

import { ShieldAlert } from "lucide-react";
import type { MemoryFact } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { kindLabel, recordSeverity, SEVERITY_TONE, shortDate } from "./lib.ts";

const CARD_ACCENT: Record<string, string> = {
  info: "border-l-argos-info",
  warning: "border-l-argos-warning",
  critical: "border-l-argos-danger",
};

export function ThreatBoard({ facts }: { facts: MemoryFact[] }) {
  if (facts.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 font-mono text-[11px] text-argos-fg-tertiary">
        <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
        Aucune menace croisée avec le carnet client sur ce filtre.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {facts.map((fact) => {
        const sev = recordSeverity(fact);
        return (
          <div
            key={fact.id}
            className={`flex flex-col gap-1.5 rounded-md border border-l-2 border-argos-border-subtle bg-argos-surface px-3 py-2.5 ${CARD_ACCENT[sev] ?? CARD_ACCENT.info}`}
          >
            <div className="flex items-center justify-between gap-2">
              <Badge tone={SEVERITY_TONE[sev]}>{kindLabel(fact.kind)}</Badge>
              <span className="font-mono text-[10px] text-argos-fg-tertiary">
                {shortDate(fact.created_at)}
              </span>
            </div>
            <p className="font-mono text-[11px] leading-snug text-argos-fg">{fact.body}</p>
            {fact.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {fact.tags.map((t) => (
                  <span
                    key={t}
                    className="font-mono text-[9px] uppercase tracking-widest text-argos-fg-disabled"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
