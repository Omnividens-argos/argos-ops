import { useCallback, useState } from "react";
import { fetchRuns } from "../api";
import { usePolling } from "../hooks/usePolling";
import { formatAbsoluteTime, formatDuration, statusColor } from "../lib/format";

// Page Runs — historique global toutes agents confondues, tri descendant
// par started_at. Filtre simple par statut côté client. Pagination réelle
// arrivera en P16.B avec offset Query côté backend.

const LIMITS = [25, 50, 100, 200] as const;

export function Runs() {
  const [limit, setLimit] = useState<(typeof LIMITS)[number]>(50);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetcher = useCallback((s?: AbortSignal) => fetchRuns(limit, s), [limit]);
  const { data, error, lastRefreshedAt } = usePolling(fetcher);

  const filtered = (data ?? []).filter((r) => statusFilter === "all" || r.status === statusFilter);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
          Historique des runs ({filtered.length} affichés)
        </h2>
        <div className="flex items-center gap-2">
          <FilterSelect
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: "all", label: "Tous statuts" },
              { value: "success", label: "Success" },
              { value: "failed", label: "Failed" },
              { value: "killed_by_breaker", label: "Killed by breaker" },
            ]}
          />
          <FilterSelect
            value={String(limit)}
            onChange={(v) => setLimit(Number(v) as (typeof LIMITS)[number])}
            options={LIMITS.map((l) => ({ value: String(l), label: `${l} derniers` }))}
          />
        </div>
      </div>

      <div className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-argos-surface-2/60 border-b border-argos-border-subtle">
              <Th>#</Th>
              <Th>Agent</Th>
              <Th>Command</Th>
              <Th>Statut</Th>
              <Th>Démarré</Th>
              <Th>Durée</Th>
              <Th>Output / erreur</Th>
            </tr>
          </thead>
          <tbody>
            {data === null && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-argos-fg-tertiary">
                  Chargement…
                </td>
              </tr>
            )}
            {data !== null && filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-argos-fg-tertiary">
                  Aucun run ne correspond au filtre.
                </td>
              </tr>
            )}
            {filtered.map((run) => (
              <tr
                key={run.id}
                className="border-b border-argos-border-subtle/60 hover:bg-argos-surface-2/40"
              >
                <td className="px-4 py-2.5 font-mono text-[11px] text-argos-fg-tertiary">
                  {run.id}
                </td>
                <td className="px-4 py-2.5 text-argos-fg font-medium">{run.agent_name}</td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-argos-fg-secondary">
                  {run.command ?? "—"}
                </td>
                <td className="px-4 py-2.5">
                  <span className={`font-mono text-xs ${statusColor(run.status)}`}>
                    {run.status ?? "?"}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-argos-fg-secondary">
                  {formatAbsoluteTime(run.started_at)}
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-argos-fg-secondary">
                  {formatDuration(run.duration_seconds)}
                </td>
                <td className="px-4 py-2.5 font-mono text-[11px] truncate max-w-[480px]">
                  {run.error ? (
                    <span className="text-argos-danger">{run.error}</span>
                  ) : (
                    <span className="text-argos-fg-tertiary">{run.output_summary ?? "—"}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && (
        <div className="mt-4 border border-argos-danger/30 bg-argos-danger/10 rounded-md p-3 text-sm text-argos-danger font-mono">
          Erreur API : {error.message}
        </div>
      )}

      {lastRefreshedAt && (
        <div className="mt-3 font-mono text-[10px] text-argos-fg-tertiary text-right">
          Refreshed {formatAbsoluteTime(lastRefreshedAt.toISOString())}
        </div>
      )}
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

function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-argos-surface border border-argos-border-subtle rounded-md px-2.5 py-1 font-mono text-xs text-argos-fg hover:bg-argos-surface-2 focus:outline-none focus:border-argos-border"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
