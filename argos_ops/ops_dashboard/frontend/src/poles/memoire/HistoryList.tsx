// Historique append-only des passages du cleaner (archi v2, S7) — la trace
// d'audit de l'unique pôle autorisé à supprimer un fait.

import type { MemoireHistoryEntry } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { fmtDateTime } from "./lib.ts";

export function HistoryList({ history }: { history: MemoireHistoryEntry[] }) {
  if (history.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucun passage du cleaner pour l'instant.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {history.map((e, i) => (
        <li
          key={`${e.at}-${i}`}
          className="flex flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">
              {fmtDateTime(e.at)}
            </span>
            <Badge tone="info">{e.pole}</Badge>
            <Badge tone="neutral">{e.actor}</Badge>
            <Badge tone="danger">{e.n_deleted} supprimé(s)</Badge>
            {e.n_refused > 0 && <Badge tone="warning">{e.n_refused} refusé(s)</Badge>}
          </div>
          {(e.deleted.length > 0 || e.refused.length > 0) && (
            <div className="flex flex-col gap-0.5 font-mono text-[10px] text-argos-fg-disabled">
              {e.deleted.map((d) => (
                <span key={`d-${d.script}/${d.record_id}`}>
                  ✗ {d.script}/{d.record_id} ({d.kind}) — {d.reason}
                </span>
              ))}
              {e.refused.map((r) => (
                <span key={`r-${r.script}/${r.record_id}`} className="text-argos-warning">
                  ⊘ {r.script}/{r.record_id} ({r.kind}) — {r.reason}
                </span>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
