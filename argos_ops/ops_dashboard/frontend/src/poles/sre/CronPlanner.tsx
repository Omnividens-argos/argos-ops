// Planning cron + plan de l'orchestrateur (archi v2, S8). En haut : la cadence
// de chaque script (cron, dernier/prochain passage, dû, passages manqués). En
// bas : le verdict dry-run de l'orchestrateur (qui tournerait maintenant et pourquoi).

import type { SrePlan, SreScheduleEntry } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { fmtDateTime, verdictTone } from "./lib.ts";

export function CronPlanner({
  schedule,
  plan,
}: {
  schedule: SreScheduleEntry[];
  plan: SrePlan;
}) {
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Cadence cron de la flotte
        </h3>
        <div className="overflow-x-auto rounded-md border border-argos-border-subtle">
          <table className="w-full border-collapse font-mono text-[11px]">
            <thead>
              <tr className="border-b border-argos-border-subtle bg-argos-surface text-argos-fg-tertiary">
                <th className="px-3 py-2 text-left">Pôle / script</th>
                <th className="px-3 py-2 text-left">Cron</th>
                <th className="px-3 py-2 text-left">Dernier</th>
                <th className="px-3 py-2 text-left">Prochain</th>
                <th className="px-3 py-2 text-left">État</th>
              </tr>
            </thead>
            <tbody>
              {schedule.map((e) => (
                <tr
                  key={`${e.pole}/${e.script}`}
                  className="border-b border-argos-border-subtle/50 hover:bg-argos-surface-2"
                >
                  <td className="px-3 py-2 text-argos-fg">
                    <span className="text-argos-fg-disabled">{e.pole}/</span>
                    {e.script}
                  </td>
                  <td className="px-3 py-2 text-argos-fg-secondary">{e.schedule ?? "—"}</td>
                  <td className="px-3 py-2 text-argos-fg-tertiary">{fmtDateTime(e.last_run_at)}</td>
                  <td className="px-3 py-2 text-argos-fg-tertiary">{fmtDateTime(e.next_run_at)}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      {e.due && <Badge tone="info">dû</Badge>}
                      {e.missed >= 2 && <Badge tone="warning">{e.missed} manqués</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Plan de l'orchestrateur
          </h3>
          <Badge tone="neutral">{plan.dry_run ? "dry-run" : "live"}</Badge>
          <span className="font-mono text-[10px] text-argos-fg-disabled">{plan.summary}</span>
        </div>
        <div className="overflow-x-auto rounded-md border border-argos-border-subtle">
          <table className="w-full border-collapse font-mono text-[11px]">
            <thead>
              <tr className="border-b border-argos-border-subtle bg-argos-surface text-argos-fg-tertiary">
                <th className="px-3 py-2 text-left">Script</th>
                <th className="px-3 py-2 text-left">Verdict</th>
                <th className="px-3 py-2 text-left">Raison</th>
                <th className="px-3 py-2 text-right">Aujourd'hui</th>
              </tr>
            </thead>
            <tbody>
              {plan.decisions.map((d) => (
                <tr
                  key={d.script}
                  className="border-b border-argos-border-subtle/50 hover:bg-argos-surface-2"
                >
                  <td className="px-3 py-2 text-argos-fg">{d.script}</td>
                  <td className="px-3 py-2">
                    <Badge tone={verdictTone(d.verdict)}>{d.verdict.replace("skipped_", "")}</Badge>
                  </td>
                  <td className="px-3 py-2 text-argos-fg-secondary">{d.reason}</td>
                  <td className="px-3 py-2 text-right text-argos-fg-tertiary">
                    {d.runs_today}
                    {d.daily_limit ? `/${d.daily_limit}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="font-mono text-[10px] text-argos-fg-disabled">
          L'orchestrateur est déterministe (pas de LLM) : cadence cron + kill-switch + breakers +
          limite quotidienne. Mode dry-run par défaut — l'exécution réelle se fait en cron auto.
        </p>
      </section>
    </div>
  );
}
