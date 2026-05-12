import { Search } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import type { AgentRunRow, RunStatus } from "../api";
import { fetchRuns } from "../api";
import { Sparkline } from "../components/Sparkline";
import { StatusPill } from "../components/StatusPill";
import { Button } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { flattenActiveAgents } from "../lib/agentCatalog";
import { formatAbsoluteTime, formatDuration } from "../lib/format";

// Vue Runs — groupage par jour avec headers sticky + filtres barre top
// (recherche texte, multi-select agent, status chips) + toggle compact/détaillé.
// Source : docs/UI_DECISIONS.md § 6 (révision 2026-05-12).

const STATUS_OPTIONS: { value: RunStatus | "all"; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "success", label: "Success" },
  { value: "failed", label: "Failed" },
  { value: "killed_by_breaker", label: "Killed" },
  { value: "skipped_disabled", label: "Skipped disabled" },
  { value: "skipped_paused", label: "Skipped paused" },
  { value: "skipped_daily_limit", label: "Skipped quota" },
];

export function Runs() {
  const [limit, setLimit] = useState(100);
  const [statusFilter, setStatusFilter] = useState<RunStatus | "all">("all");
  const [agentFilter, setAgentFilter] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [compact, setCompact] = useState(true);

  const fetcher = useCallback((s?: AbortSignal) => fetchRuns(limit, s), [limit]);
  const { data, error, lastRefreshedAt } = usePolling(fetcher);

  const knownAgents = useMemo(() => flattenActiveAgents().map((a) => a.name), []);

  const filtered = useMemo(() => {
    let out = data ?? [];
    if (statusFilter !== "all") {
      out = out.filter((r) => r.status === statusFilter);
    }
    if (agentFilter.size > 0) {
      out = out.filter((r) => agentFilter.has(r.agent_name));
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          (r.output_summary ?? "").toLowerCase().includes(q) ||
          (r.error ?? "").toLowerCase().includes(q) ||
          r.agent_name.toLowerCase().includes(q),
      );
    }
    return out;
  }, [data, statusFilter, agentFilter, search]);

  // Group par jour (YYYY-MM-DD local).
  const grouped = useMemo(() => groupByDay(filtered), [filtered]);

  // Hourly counts for top sparkline (24h)
  const hourlyCounts = useMemo(() => computeHourlyCounts(filtered), [filtered]);

  const toggleAgent = (name: string) => {
    setAgentFilter((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const clearFilters = () => {
    setStatusFilter("all");
    setAgentFilter(new Set());
    setSearch("");
  };

  const hasFilters =
    statusFilter !== "all" || agentFilter.size > 0 || search.trim().length > 0;

  return (
    <div className="p-6 space-y-5">
      {/* Mini-graphe 24h en top */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
            Activité 24h (filtrée)
          </h2>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {filtered.length} runs · {limit} chargés
          </span>
        </div>
        <Sparkline
          values={hourlyCounts}
          width={520}
          height={36}
          colorClass="text-argos-info"
        />
      </section>

      {/* Barre filtres */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Search size={14} className="text-argos-fg-tertiary shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher dans output / erreur / agent…"
            className="flex-1 bg-transparent font-mono text-sm text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none"
          />
        </div>

        <div className="flex items-start gap-3 flex-wrap">
          <FilterGroup label="Statut">
            {STATUS_OPTIONS.map((opt) => (
              <Chip
                key={opt.value}
                label={opt.label}
                active={statusFilter === opt.value}
                onClick={() => setStatusFilter(opt.value)}
              />
            ))}
          </FilterGroup>

          <FilterGroup label="Agent">
            {knownAgents.map((name) => (
              <Chip
                key={name}
                label={name}
                active={agentFilter.has(name)}
                onClick={() => toggleAgent(name)}
              />
            ))}
          </FilterGroup>

          <FilterGroup label="Vue">
            <Chip label="Compact" active={compact} onClick={() => setCompact(true)} />
            <Chip label="Détaillé" active={!compact} onClick={() => setCompact(false)} />
          </FilterGroup>

          <FilterGroup label="Limite">
            {[50, 100, 200, 500].map((l) => (
              <Chip
                key={l}
                label={String(l)}
                active={limit === l}
                onClick={() => setLimit(l)}
              />
            ))}
          </FilterGroup>
        </div>

        {hasFilters && (
          <div className="pt-1">
            <Button size="sm" variant="ghost" onClick={clearFilters}>
              Effacer les filtres
            </Button>
          </div>
        )}
      </section>

      {/* Sections par jour */}
      <div className="space-y-5">
        {grouped.length === 0 && (
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-8 text-center font-mono text-xs text-argos-fg-tertiary">
            Aucun run ne correspond aux filtres.
          </div>
        )}
        {grouped.map((group) => (
          <DaySection key={group.dayKey} group={group} compact={compact} />
        ))}
      </div>

      {error && (
        <div className="rounded-md border border-argos-danger/30 bg-argos-danger/10 p-3 font-mono text-xs text-argos-danger">
          Erreur API : {error.message}
        </div>
      )}

      {lastRefreshedAt && (
        <div className="font-mono text-[10px] text-argos-fg-tertiary text-right">
          Refreshed {formatAbsoluteTime(lastRefreshedAt.toISOString())}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// FilterGroup + Chip
// =============================================================================
function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </span>
      {children}
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`font-mono text-[11px] px-2 py-0.5 rounded-md border transition-colors ${
        active
          ? "bg-argos-info/15 border-argos-info/40 text-argos-info"
          : "bg-argos-surface border-argos-border-subtle text-argos-fg-secondary hover:bg-argos-surface-2"
      }`}
    >
      {label}
    </button>
  );
}

// =============================================================================
// Day section
// =============================================================================
interface DayGroup {
  dayKey: string;
  dayLabel: string;
  runs: AgentRunRow[];
}

function DaySection({ group, compact }: { group: DayGroup; compact: boolean }) {
  const stats = useMemo(() => {
    const success = group.runs.filter((r) => r.status === "success").length;
    const failed = group.runs.filter((r) => r.status === "failed").length;
    const skipped = group.runs.filter((r) => r.status?.startsWith("skipped_")).length;
    return { success, failed, skipped };
  }, [group.runs]);

  return (
    <section>
      <header className="sticky top-0 z-10 bg-argos-bg/90 backdrop-blur-sm border-l-2 border-argos-info py-2 pl-3 pr-3 mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-argos-fg">{group.dayLabel}</h3>
          <span className="font-mono text-[11px] text-argos-fg-tertiary">
            {group.runs.length} runs
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px]">
          <span className="text-argos-healthy">✓ {stats.success}</span>
          <span className="text-argos-danger">✗ {stats.failed}</span>
          <span className="text-argos-info">⏸ {stats.skipped}</span>
        </div>
      </header>

      <div className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
        {compact ? (
          <CompactTable runs={group.runs} />
        ) : (
          <DetailedList runs={group.runs} />
        )}
      </div>
    </section>
  );
}

// =============================================================================
// Compact table
// =============================================================================
function CompactTable({ runs }: { runs: AgentRunRow[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="bg-argos-surface-2/60 border-b border-argos-border-subtle">
          <Th>#</Th>
          <Th>Agent</Th>
          <Th>Statut</Th>
          <Th>Démarré</Th>
          <Th>Durée</Th>
          <Th>Output / erreur</Th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr
            key={run.id}
            className="border-b border-argos-border-subtle/60 hover:bg-argos-surface-2/40"
          >
            <td className="px-4 py-2 font-mono text-[11px] text-argos-fg-tertiary">{run.id}</td>
            <td className="px-4 py-2 text-argos-fg font-medium">{run.agent_name}</td>
            <td className="px-4 py-2">
              <StatusPill status={run.status} />
            </td>
            <td className="px-4 py-2 font-mono text-[11px] text-argos-fg-secondary">
              {formatAbsoluteTime(run.started_at)}
            </td>
            <td className="px-4 py-2 font-mono text-[11px] text-argos-fg-secondary">
              {formatDuration(run.duration_seconds)}
            </td>
            <td className="px-4 py-2 font-mono text-[11px] truncate max-w-[420px]">
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
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left px-4 py-2 font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary font-medium">
      {children}
    </th>
  );
}

// =============================================================================
// Detailed list (output complet visible)
// =============================================================================
function DetailedList({ runs }: { runs: AgentRunRow[] }) {
  return (
    <ul className="divide-y divide-argos-border-subtle">
      {runs.map((run) => (
        <li key={run.id} className="p-4 hover:bg-argos-surface-2/40">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-argos-fg-tertiary">#{run.id}</span>
              <span className="text-argos-fg font-medium">{run.agent_name}</span>
              <StatusPill status={run.status} />
              {run.command && (
                <span className="font-mono text-[11px] text-argos-fg-tertiary">
                  {run.command}
                </span>
              )}
            </div>
            <div className="font-mono text-[11px] text-argos-fg-tertiary">
              {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
            </div>
          </div>
          {run.output_summary && (
            <pre className="font-mono text-[11px] text-argos-fg-secondary whitespace-pre-wrap break-words leading-relaxed">
              {run.output_summary}
            </pre>
          )}
          {run.error && (
            <pre className="mt-2 font-mono text-[11px] text-argos-danger whitespace-pre-wrap break-words leading-relaxed">
              {run.error}
            </pre>
          )}
        </li>
      ))}
    </ul>
  );
}

// =============================================================================
// Aggregations
// =============================================================================
function groupByDay(runs: AgentRunRow[]): DayGroup[] {
  const groups = new Map<string, AgentRunRow[]>();
  for (const run of runs) {
    const d = new Date(run.started_at);
    const dayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (!groups.has(dayKey)) groups.set(dayKey, []);
    groups.get(dayKey)!.push(run);
  }
  const today = new Date();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const yesterdayKey = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;

  return Array.from(groups.entries())
    .map(([dayKey, runs]) => ({
      dayKey,
      dayLabel:
        dayKey === todayKey
          ? "Aujourd'hui"
          : dayKey === yesterdayKey
            ? "Hier"
            : new Date(dayKey).toLocaleDateString("fr-FR", {
                weekday: "long",
                day: "numeric",
                month: "long",
              }),
      runs,
    }))
    .sort((a, b) => b.dayKey.localeCompare(a.dayKey));
}

function computeHourlyCounts(runs: AgentRunRow[]): number[] {
  const counts: number[] = new Array(24).fill(0);
  const now = new Date();
  for (const run of runs) {
    const t = new Date(run.started_at);
    const hoursAgo = Math.floor((now.getTime() - t.getTime()) / (60 * 60 * 1000));
    if (hoursAgo >= 0 && hoursAgo < 24) {
      counts[23 - hoursAgo]! += 1;
    }
  }
  return counts;
}
