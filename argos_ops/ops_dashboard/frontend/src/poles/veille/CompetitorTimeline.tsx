// Timeline concurrents : les diffs de pages pricing/features détectés par
// CompetitorWatcher, du plus récent au plus ancien (un point = un changement).

import type { MemoryFact } from "../api.ts";
import { shortDate } from "./lib.ts";

export function CompetitorTimeline({ facts }: { facts: MemoryFact[] }) {
  const sorted = [...facts].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  if (sorted.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucun mouvement concurrent sur ce filtre.
      </div>
    );
  }
  return (
    <ol className="relative ml-1 flex flex-col gap-3 border-l border-argos-border-subtle pl-4">
      {sorted.map((fact) => (
        <li key={fact.id} className="relative">
          <span
            className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-argos-info ring-2 ring-argos-bg"
            aria-hidden
          />
          <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            {shortDate(fact.created_at)}
          </div>
          <p className="font-mono text-[11px] leading-snug text-argos-fg">{fact.body}</p>
        </li>
      ))}
    </ol>
  );
}
