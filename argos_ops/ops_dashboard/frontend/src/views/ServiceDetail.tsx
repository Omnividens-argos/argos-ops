import { ArrowLeft, Inbox, History } from "lucide-react";
import { useCallback, useMemo } from "react";
import type { AgentRunRow, AgentSummary } from "../api";
import { fetchAgents, fetchInboxDrafts, fetchRuns } from "../api";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { Badge, Flash } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import {
  AGENT_CATEGORIES,
  type CatalogAgent,
  categoryCounts,
} from "../lib/agentCatalog";
import {
  formatAbsoluteTime,
  formatDuration,
  formatRelativeTime,
  statusBgColor,
  statusColor,
} from "../lib/format";

// ServiceDetail — page focalisée par pôle (Direction, Finance, Sales…).
//
// Reproduit la pyramide d'attention :
//   1. Hero — icône + titre + description + counts
//   2. Bots du service — liste compacte avec status live
//   3. Drafts produits par les bots de ce service — extrait Inbox
//   4. Activité récente — runs des bots de ce service
//
// La sidebar reste sur « Catalogue » quand on est ici (sous-vue overlay).

interface ServiceDetailProps {
  serviceId: string;
  onBack: () => void;
  onOpenBot: (name: string) => void;
  onOpenInbox: () => void;
}

export function ServiceDetail({
  serviceId,
  onBack,
  onOpenBot,
  onOpenInbox,
}: ServiceDetailProps) {
  const category = AGENT_CATEGORIES.find((c) => c.id === serviceId);
  const agents = usePolling(useCallback((s) => fetchAgents(s), []));
  const drafts = usePolling(useCallback((s) => fetchInboxDrafts(s), []), 30000);

  // Bots de ce service.
  const serviceBotsNames = useMemo(() => {
    if (!category) return new Set<string>();
    return new Set(
      category.agents
        .filter((a) => a.status === "active" && a.name)
        .map((a) => a.name as string),
    );
  }, [category]);

  // Runs récents (200 derniers de la flotte) → on filtre côté client pour
  // ne garder que ceux des bots de ce service. Une seule requête vs N=count.
  const runs = usePolling(
    useCallback((s?: AbortSignal) => fetchRuns(200, s), []),
    10000,
  );
  const serviceRuns = useMemo(() => {
    if (runs.data === null) return null;
    return runs.data
      .filter((r) => serviceBotsNames.has(r.agent_name))
      .slice(0, 20);
  }, [runs.data, serviceBotsNames]);

  // Drafts produits par les bots de ce service.
  const serviceDrafts = useMemo(() => {
    if (drafts.data === null) return [];
    return drafts.data.filter((d) => d.agent_name && serviceBotsNames.has(d.agent_name));
  }, [drafts.data, serviceBotsNames]);

  if (!category) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg transition-colors mb-4"
        >
          <ArrowLeft size={12} strokeWidth={2} />
          Retour au catalogue
        </button>
        <EmptyState
          tone="error"
          title="Service inconnu"
          body={`Aucune catégorie « ${serviceId} » dans le catalogue. Vérifie l'URL ou repasse par le catalogue.`}
        />
      </div>
    );
  }

  const counts = categoryCounts(category.id);
  const Icon = category.icon;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg transition-colors"
      >
        <ArrowLeft size={12} strokeWidth={2} />
        Retour au catalogue
      </button>

      {/* Hero */}
      <header className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <div className="flex items-start gap-4">
          <div className="size-12 rounded-md bg-argos-surface-2 flex items-center justify-center text-argos-fg-secondary shrink-0">
            <Icon size={22} strokeWidth={1.5} />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold text-argos-fg mb-1">{category.title}</h1>
            <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
              {category.description}
            </p>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <Badge tone="healthy">{counts.active} actif{counts.active > 1 ? "s" : ""}</Badge>
              <Badge tone="neutral">{counts.roadmap} roadmap</Badge>
              <Badge tone="info">{serviceDrafts.length} draft{serviceDrafts.length > 1 ? "s" : ""} en attente</Badge>
            </div>
          </div>
        </div>
      </header>

      {agents.error && (
        <Flash variant="error" message={`Erreur agents : ${agents.error.message}`} />
      )}

      {/* Bots du service */}
      <BotsSection
        category={category.agents}
        liveAgents={agents.data ?? []}
        onOpenBot={onOpenBot}
      />

      {/* Drafts produits */}
      {serviceDrafts.length > 0 && (
        <DraftsSection
          count={serviceDrafts.length}
          previews={serviceDrafts.slice(0, 5)}
          onOpenInbox={onOpenInbox}
        />
      )}

      {/* Activité récente */}
      <RunsSection runs={serviceRuns} />
    </div>
  );
}

// =============================================================================
// Bots du service
// =============================================================================
function BotsSection({
  category,
  liveAgents,
  onOpenBot,
}: {
  category: CatalogAgent[];
  liveAgents: AgentSummary[];
  onOpenBot: (name: string) => void;
}) {
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
        Bots du service
      </h2>
      <ul className="space-y-1.5">
        {category.map((agent) => (
          <BotRow
            key={agent.displayName}
            agent={agent}
            live={
              agent.name
                ? liveAgents.find((a) => a.name === agent.name) ?? null
                : null
            }
            onOpen={() => agent.name && onOpenBot(agent.name)}
          />
        ))}
      </ul>
    </section>
  );
}

function BotRow({
  agent,
  live,
  onOpen,
}: {
  agent: CatalogAgent;
  live: AgentSummary | null;
  onOpen: () => void;
}) {
  const isRoadmap = agent.status === "roadmap";
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        disabled={isRoadmap}
        className={`w-full text-left rounded-md border px-3 py-2 flex items-center gap-3 transition-colors ${
          isRoadmap
            ? "border-dashed border-argos-border-subtle bg-argos-surface/40 cursor-default"
            : "border-argos-border-subtle bg-argos-surface hover:border-argos-border"
        }`}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={`text-sm font-semibold truncate ${
                isRoadmap ? "text-argos-fg-secondary" : "text-argos-fg"
              }`}
            >
              {agent.displayName}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary truncate">
              {agent.shortLabel}
            </span>
            {isRoadmap && <Badge tone="neutral">Roadmap</Badge>}
          </div>
          <p className="font-mono text-[10px] text-argos-fg-tertiary mt-0.5 line-clamp-1">
            {agent.description}
          </p>
        </div>
        {!isRoadmap && (
          <div className="shrink-0 flex items-center gap-2">
            <StatusPill
              status={live?.last_run_status ?? null}
              breakerTripped={live?.breaker_tripped ?? false}
            />
            <span className="font-mono text-[10px] text-argos-fg-tertiary hidden sm:inline">
              {formatRelativeTime(live?.last_run_at ?? null)}
            </span>
          </div>
        )}
      </button>
    </li>
  );
}

// =============================================================================
// Drafts produits par ce service
// =============================================================================
function DraftsSection({
  count,
  previews,
  onOpenInbox,
}: {
  count: number;
  previews: import("../api").InboxDraft[];
  onOpenInbox: () => void;
}) {
  return (
    <section className="rounded-md border border-argos-info/30 bg-argos-info/5 p-5">
      <div className="flex items-baseline justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Inbox size={14} strokeWidth={2} className="text-argos-info" />
          <h2 className="text-sm font-semibold text-argos-fg">Drafts produits par ce service</h2>
          <Badge tone="info">{count} en attente</Badge>
        </div>
        <button
          type="button"
          onClick={onOpenInbox}
          className="font-mono text-[11px] text-argos-info hover:underline"
        >
          Voir dans l'Inbox →
        </button>
      </div>
      <ul className="space-y-1.5">
        {previews.map((d) => (
          <li
            key={d.id}
            className="rounded-md bg-argos-surface px-3 py-2 border border-argos-border-subtle"
          >
            <div className="text-xs font-medium text-argos-fg truncate">{d.title}</div>
            <div className="font-mono text-[10px] text-argos-fg-tertiary mt-0.5">
              {formatRelativeTime(d.created_at)} · {d.file_path} · {d.agent_name ?? "—"}
            </div>
          </li>
        ))}
        {count > previews.length && (
          <li className="font-mono text-[10px] text-argos-fg-tertiary text-center pt-1">
            +{count - previews.length} de plus — voir Inbox
          </li>
        )}
      </ul>
    </section>
  );
}

// =============================================================================
// Activité récente (runs filtré sur les bots du service)
// =============================================================================
function RunsSection({ runs }: { runs: AgentRunRow[] | null }) {
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <div className="flex items-center gap-2 mb-3">
        <History size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
        <h2 className="text-sm font-semibold text-argos-fg">Activité récente</h2>
        <span className="font-mono text-[10px] text-argos-fg-tertiary">
          (20 derniers runs des bots de ce service)
        </span>
      </div>
      {runs === null && (
        <EmptyState tone="loading" title="Chargement…" compact />
      )}
      {runs?.length === 0 && (
        <EmptyState
          tone="neutral"
          title="Aucun run récent"
          body="Les bots de ce service n'ont pas tourné dans la fenêtre globale (200 derniers runs flotte). Ils s'exécuteront à leur prochain créneau cron."
          compact
        />
      )}
      <div className="space-y-2">
        {runs?.map((run) => <RunCard key={run.id} run={run} />)}
      </div>
    </section>
  );
}

function RunCard({ run }: { run: AgentRunRow }) {
  return (
    <div className={`rounded-md border px-3 py-2 ${statusBgColor(run.status)}`}>
      <div className="flex items-center justify-between text-xs gap-2">
        <div className={`font-mono ${statusColor(run.status)} truncate`}>
          {run.agent_name} · #{run.id} · {run.status ?? "?"}
        </div>
        <div className="font-mono text-argos-fg-tertiary shrink-0">
          {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
        </div>
      </div>
      {run.output_summary && (
        <div className="mt-1 font-mono text-[10px] text-argos-fg-secondary line-clamp-2 break-words">
          {run.output_summary}
        </div>
      )}
    </div>
  );
}

// Type-import only — avoid TS6133 (used implicitly via casting).
// (no-op needed, declared as named import in DraftsSection)
