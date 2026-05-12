import { useCallback } from "react";
import type { AgentSummary } from "../api";
import { fetchAgents, fetchKPIs } from "../api";
import { usePolling } from "../hooks/usePolling";
import { formatEur, formatRelativeTime, statusColor } from "../lib/format";

// Page Overview — 6 KPIs cards en haut + grille d'état des 4 agents en dessous.
// Conçue pour être l'écran de démarrage matin du fondateur : tout ce qui dérive
// doit attirer l'œil en moins de 2 secondes.

export function Overview() {
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));
  const agents = usePolling(useCallback((s) => fetchAgents(s), []));

  return (
    <div className="p-6 space-y-6">
      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          KPIs business
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
          <KpiCard label="MRR" value={kpis.data ? formatEur(kpis.data.mrr_eur) : "—"} mono />
          <KpiCard label="ARR" value={kpis.data ? formatEur(kpis.data.arr_eur) : "—"} mono />
          <KpiCard
            label="Active subs"
            value={kpis.data ? `${kpis.data.active_subscriptions}` : "—"}
            mono
          />
          <KpiCard
            label="Leads 24h"
            value={kpis.data ? `${kpis.data.leads_last_24h}` : "—"}
            mono
          />
          <KpiCard
            label="Tickets ouverts"
            value={kpis.data ? `${kpis.data.open_tickets}` : "—"}
            mono
          />
          <KpiCard
            label="Breakers actifs"
            value={kpis.data ? `${kpis.data.tripped_breakers}` : "—"}
            mono
            alert={kpis.data ? kpis.data.tripped_breakers > 0 : false}
          />
        </div>
      </section>

      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          Agents — état temps réel
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

      {(kpis.error || agents.error) && (
        <div className="border border-argos-danger/30 bg-argos-danger/10 rounded-md p-3 text-sm text-argos-danger font-mono">
          Erreur API : {(kpis.error ?? agents.error)?.message}
        </div>
      )}
    </div>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  mono?: boolean;
  alert?: boolean;
}

function KpiCard({ label, value, mono, alert }: KpiCardProps) {
  return (
    <div
      className={`rounded-md border bg-argos-surface px-4 py-3 ${
        alert ? "border-argos-danger/40 bg-argos-danger/5" : "border-argos-border-subtle"
      }`}
    >
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </div>
      <div
        className={`mt-1 text-xl ${mono ? "font-mono font-medium" : "font-semibold"} ${
          alert ? "text-argos-danger" : "text-argos-fg"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function AgentMiniCard({ agent }: { agent: AgentSummary }) {
  const status = agent.last_run_status;
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="font-semibold text-argos-fg">{agent.name}</div>
        <div
          className={`size-2 rounded-full ${
            status === "success"
              ? "bg-argos-healthy"
              : status === "failed"
                ? "bg-argos-danger"
                : status === "killed_by_breaker"
                  ? "bg-argos-warning"
                  : "bg-argos-fg-disabled"
          }`}
        />
      </div>
      <div className={`font-mono text-xs ${statusColor(status)}`}>
        {status ?? "jamais exécuté"}
      </div>
      <div className="font-mono text-[11px] text-argos-fg-tertiary mt-1">
        {formatRelativeTime(agent.last_run_at)}
      </div>
      {agent.breaker_tripped && (
        <div className="mt-2 font-mono text-[11px] text-argos-danger">
          Breaker · {agent.breaker_reason}
        </div>
      )}
    </div>
  );
}
