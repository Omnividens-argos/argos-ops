// Tableau de statut temps réel des scripts SRE (archi v2, S8). Chaque ligne :
// pastille de santé, dernier constat, freshness, perf P50/P95, badges (dû /
// stale / gelé / breaker), et bouton « lancer » pour les scripts exécutables.

import { useState } from "react";
import { Play } from "lucide-react";
import { type SreScriptStatus, runSreScript } from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { fmtAge, fmtDateTime, fmtDuration, severityDot, severityTone } from "./lib.ts";

export function StatusBoard({
  scripts,
  onChanged,
}: {
  scripts: SreScriptStatus[];
  onChanged: () => void;
}) {
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function launch(script: string) {
    setRunning(script);
    setError(null);
    try {
      await runSreScript(script);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "échec du lancement");
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <Flash variant="error" message={error} onDismiss={() => setError(null)} />}
      <div className="overflow-x-auto rounded-md border border-argos-border-subtle">
        <table className="w-full border-collapse font-mono text-[11px]">
          <thead>
            <tr className="border-b border-argos-border-subtle bg-argos-surface text-argos-fg-tertiary">
              <th className="px-3 py-2 text-left">Script</th>
              <th className="px-3 py-2 text-left">Dernier constat</th>
              <th className="px-3 py-2 text-left">Dernier run</th>
              <th className="px-3 py-2 text-left">Prochain</th>
              <th className="px-3 py-2 text-right">P50 / P95</th>
              <th className="px-3 py-2 text-left">État</th>
              <th className="px-3 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {scripts.map((s) => (
              <tr
                key={s.script}
                className="border-b border-argos-border-subtle/50 hover:bg-argos-surface-2"
              >
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${severityDot(s.health)}`} />
                    <span className="text-argos-fg">{s.script}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-argos-fg-secondary">
                  {s.last_summary ? (
                    <span className="line-clamp-1">{s.last_summary}</span>
                  ) : (
                    <span className="text-argos-fg-disabled">jamais exécuté</span>
                  )}
                </td>
                <td className="px-3 py-2 text-argos-fg-tertiary">
                  {fmtDateTime(s.last_run_at)}
                  <span className="ml-1 text-argos-fg-disabled">({fmtAge(s.age_hours)})</span>
                </td>
                <td className="px-3 py-2 text-argos-fg-tertiary">{fmtDateTime(s.next_run_at)}</td>
                <td className="px-3 py-2 text-right text-argos-fg-tertiary">
                  {fmtDuration(s.p50_ms)} / {fmtDuration(s.p95_ms)}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {s.last_status && (
                      <Badge tone={severityTone(s.last_severity)}>{s.last_status}</Badge>
                    )}
                    {s.due && <Badge tone="info">dû</Badge>}
                    {s.stale && <Badge tone="warning">stale</Badge>}
                    {s.frozen && <Badge tone="neutral">gelé</Badge>}
                    {s.breaker_tripped && <Badge tone="danger">breaker</Badge>}
                  </div>
                </td>
                <td className="px-3 py-2 text-right">
                  {s.runnable && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={running !== null || s.frozen}
                      onClick={() => launch(s.script)}
                    >
                      <Play className="mr-1 inline h-3 w-3" aria-hidden />
                      {running === s.script ? "…" : "lancer"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="font-mono text-[10px] text-argos-fg-disabled">
        Lancer = exécution immédiate (réelle) du script ; un script gelé ne peut pas être lancé.
      </p>
    </div>
  );
}
