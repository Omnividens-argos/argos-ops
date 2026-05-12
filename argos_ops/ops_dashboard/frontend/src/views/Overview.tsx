import { useCallback, useMemo } from "react";
import type { AgentRunRow, AgentSummary } from "../api";
import { fetchAgents, fetchKPIs, fetchRuns } from "../api";
import { Heatmap } from "../components/Heatmap";
import { Sparkline } from "../components/Sparkline";
import { StatusPill } from "../components/StatusPill";
import { Badge } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatEur, formatRelativeTime } from "../lib/format";

// Overview enrichie — Today briefing + KPI cards avec sparklines + Heatmap
// 12h + état flotte. Source : docs/UI_DECISIONS.md § 5 (révision 2026-05-12).

export function Overview() {
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));
  const agents = usePolling(useCallback((s) => fetchAgents(s), []));
  const runs = usePolling(useCallback((s) => fetchRuns(200, s), []));

  // Agrégations dérivées des runs (sparklines, heatmap, briefing texte).
  const aggregates = useMemo(() => computeAggregates(runs.data ?? []), [runs.data]);

  return (
    <div className="p-6 space-y-5 theme-transition">
      {/* Today briefing — phrases factuelles générées depuis runs + agents. */}
      <TodayBriefing
        agents={agents.data ?? []}
        runsToday={aggregates.runsToday}
        runsFailedToday={aggregates.failedToday}
      />

      {/* KPIs business avec sparklines. */}
      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          KPIs business
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          <KpiCard
            label="MRR"
            value={kpis.data ? formatEur(kpis.data.mrr_eur) : "—"}
            trend={[]}
          />
          <KpiCard
            label="ARR"
            value={kpis.data ? formatEur(kpis.data.arr_eur) : "—"}
            trend={[]}
          />
          <KpiCard
            label="Active subs"
            value={kpis.data ? `${kpis.data.active_subscriptions}` : "—"}
            trend={[]}
          />
          <KpiCard
            label="Leads 24h"
            value={kpis.data ? `${kpis.data.leads_last_24h}` : "—"}
            trend={[]}
          />
          <KpiCard
            label="Tickets ouverts"
            value={kpis.data ? `${kpis.data.open_tickets}` : "—"}
            trend={[]}
          />
          <KpiCard
            label="Breakers actifs"
            value={kpis.data ? `${kpis.data.tripped_breakers}` : "—"}
            trend={[]}
            alert={kpis.data ? kpis.data.tripped_breakers > 0 : false}
          />
        </div>
      </section>

      {/* Activité 12h — heatmap horizontale */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
            Activité 12 dernières heures
          </h2>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {aggregates.runsLast12h} runs · {aggregates.failedLast12h} échec(s)
          </span>
        </div>
        <Heatmap cells={aggregates.heatmapCells} />
        <div className="flex items-center justify-between mt-1.5 font-mono text-[10px] text-argos-fg-tertiary">
          <span>-12h</span>
          <span>-6h</span>
          <span>maintenant</span>
        </div>
      </section>

      {/* Sparkline runs 7j */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
            Activité 7 derniers jours
          </h2>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {aggregates.runsLast7d} runs au total
          </span>
        </div>
        <Sparkline
          values={aggregates.dailyCounts}
          width={520}
          height={48}
          colorClass="text-argos-info"
        />
      </section>

      {/* État flotte agents — cards compactes par catégorie d'état */}
      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          État des agents
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-3">
          {(agents.data ?? []).map((agent) => (
            <AgentMiniCard key={agent.name} agent={agent} />
          ))}
          {agents.data === null && (
            <div className="text-sm text-argos-fg-tertiary col-span-full">Chargement…</div>
          )}
        </div>
      </section>

      {/* Coût Pro Max placeholder */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
            Consommation Claude Code Pro Max (D-017)
          </h2>
          <Badge tone="neutral">Tracking P19</Badge>
        </div>
        <div className="w-full h-2 rounded-full bg-argos-surface-2 overflow-hidden">
          <div className="h-full w-0 bg-argos-info" aria-label="0% consumed (no tracking yet)" />
        </div>
        <p className="font-mono text-[10px] text-argos-fg-tertiary mt-2">
          La consommation Claude Pro Max sera mesurée à partir de P19 (maintenance).
          Pour l'instant, garde un œil sur ton interface Claude pour le quota mensuel.
        </p>
      </section>
    </div>
  );
}

// =============================================================================
// Today briefing — texte naturel généré depuis l'état actuel
// =============================================================================
function TodayBriefing({
  agents,
  runsToday,
  runsFailedToday,
}: {
  agents: AgentSummary[];
  runsToday: number;
  runsFailedToday: number;
}) {
  const trippedAgents = agents.filter((a) => a.breaker_tripped);
  const successAgents = agents.filter((a) => a.last_run_status === "success");
  const failedAgents = agents.filter((a) => a.last_run_status === "failed");
  const neverRun = agents.filter((a) => a.last_run_status === null);

  const lines: string[] = [];
  lines.push(`${runsToday} run${runsToday !== 1 ? "s" : ""} aujourd'hui · ${runsFailedToday} échec${runsFailedToday !== 1 ? "s" : ""}.`);
  if (trippedAgents.length > 0) {
    lines.push(`⚠ ${trippedAgents.length} agent${trippedAgents.length > 1 ? "s" : ""} bloqué${trippedAgents.length > 1 ? "s" : ""} par un breaker — voir vue Breakers.`);
  }
  if (failedAgents.length > 0) {
    lines.push(`⚠ ${failedAgents.length} agent${failedAgents.length > 1 ? "s" : ""} en erreur sur le dernier run.`);
  }
  if (successAgents.length > 0 && trippedAgents.length === 0 && failedAgents.length === 0) {
    lines.push(`${successAgents.length} agent${successAgents.length > 1 ? "s tournent" : " tourne"} normalement.`);
  }
  if (neverRun.length > 0) {
    lines.push(`${neverRun.length} agent${neverRun.length > 1 ? "s n'ont" : " n'a"} jamais été exécuté${neverRun.length > 1 ? "s" : ""}.`);
  }

  const allGood = trippedAgents.length === 0 && failedAgents.length === 0;
  return (
    <section
      className={`rounded-md border p-4 ${
        allGood
          ? "border-argos-healthy/30 bg-argos-healthy/5"
          : "border-argos-warning/30 bg-argos-warning/5"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
          Aujourd'hui en bref
        </h2>
      </div>
      <ul className="space-y-1">
        {lines.map((line, idx) => (
          <li key={idx} className="text-sm text-argos-fg">
            {line}
          </li>
        ))}
      </ul>
    </section>
  );
}

// =============================================================================
// Card KPI avec sparkline placeholder
// =============================================================================
interface KpiCardProps {
  label: string;
  value: string;
  trend: number[];
  alert?: boolean;
}

function KpiCard({ label, value, trend, alert }: KpiCardProps) {
  return (
    <div
      className={`rounded-md border bg-argos-surface px-4 py-3 ${
        alert ? "border-argos-danger/40 bg-argos-danger/5" : "border-argos-border-subtle"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {label}
        </div>
        {trend.length > 0 && (
          <Sparkline values={trend} width={48} height={16} colorClass="text-argos-info" />
        )}
      </div>
      <div
        className={`mt-1 text-xl font-mono font-medium ${
          alert ? "text-argos-danger" : "text-argos-fg"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

// =============================================================================
// Agent mini card — état flotte compact
// =============================================================================
function AgentMiniCard({ agent }: { agent: AgentSummary }) {
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="font-semibold text-argos-fg">{agent.name}</div>
        <StatusPill
          status={agent.last_run_status}
          breakerTripped={agent.breaker_tripped}
        />
      </div>
      <div className="font-mono text-[11px] text-argos-fg-tertiary">
        {formatRelativeTime(agent.last_run_at)}
      </div>
      {agent.breaker_tripped && agent.breaker_reason && (
        <div className="mt-2 font-mono text-[11px] text-argos-danger line-clamp-2">
          {agent.breaker_reason}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Agrégations dérivées des runs (sparklines, heatmap, briefing)
// =============================================================================
interface Aggregates {
  runsToday: number;
  failedToday: number;
  runsLast12h: number;
  failedLast12h: number;
  runsLast7d: number;
  heatmapCells: { label: string; count: number; failed: number }[];
  dailyCounts: number[];
}

function computeAggregates(runs: AgentRunRow[]): Aggregates {
  const now = new Date();
  const midnight = new Date(now);
  midnight.setHours(0, 0, 0, 0);

  // 1. Today
  const today = runs.filter((r) => new Date(r.started_at) >= midnight);
  const runsToday = today.length;
  const failedToday = today.filter((r) => r.status === "failed").length;

  // 2. Last 12h heatmap (12 cellules, 1h chacune, de -12h à now)
  const heatmapCells: { label: string; count: number; failed: number }[] = [];
  for (let i = 11; i >= 0; i--) {
    const cellEnd = new Date(now.getTime() - i * 60 * 60 * 1000);
    const cellStart = new Date(cellEnd.getTime() - 60 * 60 * 1000);
    const inCell = runs.filter((r) => {
      const t = new Date(r.started_at);
      return t >= cellStart && t < cellEnd;
    });
    heatmapCells.push({
      label: `${cellStart.getHours()}h-${cellEnd.getHours()}h`,
      count: inCell.length,
      failed: inCell.filter((r) => r.status === "failed").length,
    });
  }
  const runsLast12h = heatmapCells.reduce((s, c) => s + c.count, 0);
  const failedLast12h = heatmapCells.reduce((s, c) => s + c.failed, 0);

  // 3. Last 7 days sparkline (7 valeurs, count runs par jour)
  const dailyCounts: number[] = [];
  for (let i = 6; i >= 0; i--) {
    const dayStart = new Date(midnight);
    dayStart.setDate(dayStart.getDate() - i);
    const dayEnd = new Date(dayStart);
    dayEnd.setDate(dayEnd.getDate() + 1);
    const inDay = runs.filter((r) => {
      const t = new Date(r.started_at);
      return t >= dayStart && t < dayEnd;
    });
    dailyCounts.push(inDay.length);
  }
  const runsLast7d = dailyCounts.reduce((s, c) => s + c, 0);

  return {
    runsToday,
    failedToday,
    runsLast12h,
    failedLast12h,
    runsLast7d,
    heatmapCells,
    dailyCounts,
  };
}
