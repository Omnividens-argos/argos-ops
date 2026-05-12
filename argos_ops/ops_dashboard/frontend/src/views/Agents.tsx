import { useCallback, useEffect, useState } from "react";
import type { AgentRunRow, AgentSummary } from "../api";
import { fetchAgentRuns, fetchAgents } from "../api";
import { usePolling } from "../hooks/usePolling";
import { formatAbsoluteTime, formatDuration, formatRelativeTime, statusBgColor, statusColor } from "../lib/format";

// Page Agents — table dense de tous les agents avec un drawer latéral qui
// s'ouvre au clic pour afficher les 50 derniers runs de l'agent sélectionné.
// Read-only en P16.A (pas de toggle/run-now/reset — arrivent en P16.B).

export function Agents() {
  const { data: agents, error } = usePolling(useCallback((s) => fetchAgents(s), []));
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="p-6">
      <div className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-argos-surface-2/60 border-b border-argos-border-subtle">
              <Th>Agent</Th>
              <Th>Dernier statut</Th>
              <Th>Dernière exécution</Th>
              <Th>Durée</Th>
              <Th>Output</Th>
              <Th>Breaker</Th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent) => (
              <AgentRow key={agent.name} agent={agent} onSelect={() => setSelected(agent.name)} selected={selected === agent.name} />
            ))}
            {agents === null && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-argos-fg-tertiary">
                  Chargement…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {error && (
        <div className="mt-4 border border-argos-danger/30 bg-argos-danger/10 rounded-md p-3 text-sm text-argos-danger font-mono">
          Erreur API : {error.message}
        </div>
      )}

      {selected && <RunsDrawer agentName={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left px-4 py-2.5 font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary font-medium">
      {children}
    </th>
  );
}

function AgentRow({
  agent,
  onSelect,
  selected,
}: {
  agent: AgentSummary;
  onSelect: () => void;
  selected: boolean;
}) {
  return (
    <tr
      onClick={onSelect}
      className={`border-b border-argos-border-subtle/60 hover:bg-argos-surface-2/40 cursor-pointer transition-colors ${
        selected ? "bg-argos-surface-2/60" : ""
      }`}
    >
      <td className="px-4 py-3 font-medium text-argos-fg">{agent.name}</td>
      <td className="px-4 py-3">
        <span
          className={`inline-flex items-center gap-1.5 font-mono text-xs ${statusColor(agent.last_run_status)}`}
        >
          <span
            className={`size-1.5 rounded-full ${
              agent.last_run_status === "success"
                ? "bg-argos-healthy"
                : agent.last_run_status === "failed"
                  ? "bg-argos-danger"
                  : agent.last_run_status === "killed_by_breaker"
                    ? "bg-argos-warning"
                    : "bg-argos-fg-disabled"
            }`}
          />
          {agent.last_run_status ?? "jamais"}
        </span>
      </td>
      <td className="px-4 py-3 font-mono text-xs text-argos-fg-secondary">
        {formatRelativeTime(agent.last_run_at)}
      </td>
      <td className="px-4 py-3 font-mono text-xs text-argos-fg-secondary">
        {formatDuration(agent.last_run_duration_seconds)}
      </td>
      <td className="px-4 py-3 font-mono text-[11px] text-argos-fg-tertiary truncate max-w-[420px]">
        {agent.last_run_output_summary ?? "—"}
      </td>
      <td className="px-4 py-3">
        {agent.breaker_tripped ? (
          <span className="font-mono text-[11px] text-argos-danger">tripped</span>
        ) : (
          <span className="font-mono text-[11px] text-argos-fg-tertiary">—</span>
        )}
      </td>
    </tr>
  );
}

function RunsDrawer({ agentName, onClose }: { agentName: string; onClose: () => void }) {
  const [runs, setRuns] = useState<AgentRunRow[] | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchAgentRuns(agentName, 50, controller.signal)
      .then(setRuns)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(e);
      });
    return () => controller.abort();
  }, [agentName]);

  // Fermeture sur Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-20 flex">
      <div className="flex-1 bg-argos-bg/60" onClick={onClose} />
      <aside className="w-[640px] max-w-full bg-argos-surface border-l border-argos-border-subtle flex flex-col">
        <div className="px-5 py-4 border-b border-argos-border-subtle flex items-center justify-between">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
              Logs agent
            </div>
            <div className="text-base font-semibold text-argos-fg">{agentName}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs text-argos-fg-secondary hover:text-argos-fg px-2 py-1 rounded border border-argos-border-subtle hover:bg-argos-surface-2"
          >
            Esc
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {error && (
            <div className="text-sm text-argos-danger font-mono">{error.message}</div>
          )}
          {runs === null && !error && (
            <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
          )}
          {runs?.length === 0 && (
            <div className="text-sm text-argos-fg-tertiary">Aucun run enregistré.</div>
          )}
          {runs?.map((run) => <RunCard key={run.id} run={run} />)}
        </div>
      </aside>
    </div>
  );
}

function RunCard({ run }: { run: AgentRunRow }) {
  return (
    <div className={`rounded-md border px-3 py-2.5 ${statusBgColor(run.status)}`}>
      <div className="flex items-center justify-between text-xs">
        <div className={`font-mono ${statusColor(run.status)}`}>
          #{run.id} · {run.status ?? "?"}
        </div>
        <div className="font-mono text-argos-fg-tertiary">
          {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
        </div>
      </div>
      {run.output_summary && (
        <div className="mt-1.5 font-mono text-[11px] text-argos-fg-secondary break-words">
          {run.output_summary}
        </div>
      )}
      {run.error && (
        <div className="mt-1.5 font-mono text-[11px] text-argos-danger break-words">
          {run.error}
        </div>
      )}
    </div>
  );
}
