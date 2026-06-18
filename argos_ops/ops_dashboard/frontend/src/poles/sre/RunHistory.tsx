// Historique des runs SRE (archi v2, S8) — lit le runlog (filtrable par script),
// du plus récent au plus ancien. Statut + sévérité + durée + résumé + erreur.

import { useEffect, useState } from "react";
import { type SreRun, fetchSreRuns } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { fmtDateTime, fmtDuration, runStatusTone, severityTone } from "./lib.ts";

export function RunHistory({ scripts, recent }: { scripts: string[]; recent: SreRun[] }) {
  const [filter, setFilter] = useState<string>("");
  const [runs, setRuns] = useState<SreRun[]>(recent);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchSreRuns({ script: filter || undefined, limit: 200 }, controller.signal)
      .then(setRuns)
      .catch(() => {
        /* garde l'affichage courant en cas d'abort */
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [filter]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Script
        </label>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border border-argos-border-subtle bg-argos-bg px-2 py-1 font-mono text-xs text-argos-fg"
        >
          <option value="">tous</option>
          {scripts.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        {loading && <span className="font-mono text-[10px] text-argos-fg-disabled">…</span>}
      </div>

      {runs.length === 0 ? (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Aucun run journalisé.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-argos-border-subtle">
          <table className="w-full border-collapse font-mono text-[11px]">
            <thead>
              <tr className="border-b border-argos-border-subtle bg-argos-surface text-argos-fg-tertiary">
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-left">Script</th>
                <th className="px-3 py-2 text-left">Statut</th>
                <th className="px-3 py-2 text-left">Constat</th>
                <th className="px-3 py-2 text-right">Durée</th>
                <th className="px-3 py-2 text-left">Résumé</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r, i) => (
                <tr
                  key={`${r.script}-${r.at}-${i}`}
                  className="border-b border-argos-border-subtle/50 hover:bg-argos-surface-2"
                >
                  <td className="px-3 py-2 text-argos-fg-tertiary">{fmtDateTime(r.at)}</td>
                  <td className="px-3 py-2 text-argos-fg">{r.script}</td>
                  <td className="px-3 py-2">
                    <Badge tone={runStatusTone(r.status)}>{r.status}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <Badge tone={severityTone(r.severity)}>{r.severity}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right text-argos-fg-tertiary">
                    {fmtDuration(r.duration_ms)}
                  </td>
                  <td className="px-3 py-2 text-argos-fg-secondary">
                    <span className="line-clamp-1">{r.error ? r.error : r.summary}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
