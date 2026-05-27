import { useCallback, useEffect, useState } from "react";
import type { AgentConfig, AgentSummary } from "../api";
import { fetchAgentConfig, fetchAgents, patchAgentConfig } from "../api";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { Badge, Button, Flash, Toggle } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import {
  AGENT_CATEGORIES,
  type CatalogAgent,
  type CatalogCategory,
  categoryCounts,
  totalCounts,
} from "../lib/agentCatalog";
import { formatDuration, formatRelativeTime } from "../lib/format";

// Vue Agents — catalogue 12 services × 79 bots empilés avec headers sticky.
// Click sur une card ou « Détails » → remonte `onOpenBot(name)` au niveau App,
// qui affiche la page BotDetail. L'ancien drawer interne a été retiré.
// Catalogue : `lib/agentCatalog.ts`. Révision 2026-05-23.

type StatusFilter = "all" | "active" | "roadmap";

interface AgentsProps {
  onOpenBot: (name: string) => void;
  onOpenService?: (id: string) => void;
}

export function Agents({ onOpenBot, onOpenService }: AgentsProps) {
  const fetcher = useCallback((s?: AbortSignal) => fetchAgents(s), []);
  const { data: agents, error } = usePolling(fetcher);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; msg: string } | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");
  const [bumpKey, setBumpKey] = useState(0);

  // Cache des configs par agent (toggle/pause needs config.enabled, paused_until).
  const [configs, setConfigs] = useState<Record<string, AgentConfig>>({});

  useEffect(() => {
    let active = true;
    const fetchAll = async () => {
      const liveAgents = (agents ?? []).map((a) => a.name);
      if (liveAgents.length === 0) return;
      try {
        const results = await Promise.all(
          liveAgents.map((n) => fetchAgentConfig(n).catch(() => null)),
        );
        if (!active) return;
        const next: Record<string, AgentConfig> = {};
        liveAgents.forEach((name, i) => {
          const cfg = results[i];
          if (cfg) next[name] = cfg;
        });
        setConfigs(next);
      } catch {
        // silencieux — le polling agents reste prioritaire
      }
    };
    fetchAll();
    return () => {
      active = false;
    };
  }, [agents, bumpKey]);

  const refetch = () => setBumpKey((k) => k + 1);

  const normalizedQuery = query.trim().toLowerCase();

  const visibleCategories = (
    activeCategory === "all"
      ? AGENT_CATEGORIES
      : AGENT_CATEGORIES.filter((c) => c.id === activeCategory)
  )
    .map((cat) => ({
      ...cat,
      agents: cat.agents
        .filter((a) => statusFilter === "all" || a.status === statusFilter)
        .filter((a) => {
          if (normalizedQuery === "") return true;
          const hay = `${a.displayName} ${a.shortLabel} ${a.description}`.toLowerCase();
          return hay.includes(normalizedQuery);
        })
        .sort((a, b) => (a.status === b.status ? 0 : a.status === "active" ? -1 : 1)),
    }))
    .filter((cat) => cat.agents.length > 0);

  const totals = totalCounts();

  return (
    <div className="p-6 space-y-5">
      {flash && (
        <Flash variant={flash.variant} message={flash.msg} onDismiss={() => setFlash(null)} />
      )}

      <FleetCounter totals={totals} />

      <SearchBar value={query} onChange={setQuery} />

      <CategoryFilter
        activeCategory={activeCategory}
        onChange={setActiveCategory}
      />

      <StatusFilterBar value={statusFilter} onChange={setStatusFilter} />

      <div className="space-y-6">
        {visibleCategories.length === 0 && (
          <EmptyState
            tone="neutral"
            title="Aucun bot ne correspond"
            body={
              normalizedQuery
                ? `Rien ne match « ${normalizedQuery} ». Essaie un autre terme ou élargis les filtres.`
                : "Élargis les filtres ci-dessus pour voir plus de bots."
            }
            compact
          />
        )}
        {visibleCategories.map((cat) => (
          <CategorySection
            key={cat.id}
            category={cat}
            agentsData={agents ?? []}
            configs={configs}
            onOpenBot={onOpenBot}
            onOpenService={onOpenService}
            onFlash={setFlash}
            onMutated={refetch}
          />
        ))}
      </div>

      {error && (
        <Flash variant="error" message={`Erreur API : ${error.message}`} />
      )}
    </div>
  );
}

// =============================================================================
// Compteur global de la flotte (X actifs · Y roadmap · Z bots au plan).
// =============================================================================
function FleetCounter({
  totals,
}: {
  totals: { active: number; roadmap: number; total: number };
}) {
  return (
    <div className="flex items-baseline gap-3 flex-wrap">
      <h1 className="text-base font-semibold text-argos-fg">Flotte Argos Ops</h1>
      <span className="font-mono text-[11px] text-argos-fg-tertiary">
        <span className="text-argos-healthy">{totals.active} actifs</span>
        {" · "}
        <span>{totals.roadmap} roadmap</span>
        {" · "}
        <span>{totals.total} bots au plan</span>
      </span>
    </div>
  );
}

// =============================================================================
// Search bar (recherche globale catalogue)
// =============================================================================
function SearchBar({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary shrink-0">
        Chercher
      </span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="ex. finance, kb, churn, lead…"
        className="flex-1 bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60 max-w-md"
      />
      {value !== "" && (
        <button
          type="button"
          onClick={() => onChange("")}
          className="font-mono text-[10px] text-argos-fg-tertiary hover:text-argos-fg transition-colors"
        >
          effacer
        </button>
      )}
    </div>
  );
}

// =============================================================================
// Filtre statut (Actifs / Roadmap / Tous).
// =============================================================================
function StatusFilterBar({
  value,
  onChange,
}: {
  value: StatusFilter;
  onChange: (next: StatusFilter) => void;
}) {
  const opts: { id: StatusFilter; label: string }[] = [
    { id: "all", label: "Tous" },
    { id: "active", label: "Actifs uniquement" },
    { id: "roadmap", label: "Roadmap uniquement" },
  ];
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        Statut
      </span>
      {opts.map((o) => (
        <ChipFilter
          key={o.id}
          label={o.label}
          active={value === o.id}
          onClick={() => onChange(o.id)}
        />
      ))}
    </div>
  );
}

// =============================================================================
// Filtre catégorie (chips multi-select simplifié — un seul à la fois ou Toutes)
// =============================================================================
function CategoryFilter({
  activeCategory,
  onChange,
}: {
  activeCategory: string | "all";
  onChange: (id: string | "all") => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        Service
      </span>
      <ChipFilter
        label="Tous"
        active={activeCategory === "all"}
        onClick={() => onChange("all")}
      />
      {AGENT_CATEGORIES.map((cat) => {
        const counts = categoryCounts(cat.id);
        return (
          <ChipFilter
            key={cat.id}
            label={`${cat.title} · ${counts.active}/${counts.active + counts.roadmap}`}
            active={activeCategory === cat.id}
            onClick={() => onChange(cat.id)}
          />
        );
      })}
    </div>
  );
}

function ChipFilter({
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
      className={`font-mono text-[11px] px-2.5 py-1 rounded-md border transition-colors ${
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
// Section catégorie — header sticky + grid de cards
// =============================================================================
interface CategorySectionProps {
  category: CatalogCategory;
  agentsData: AgentSummary[];
  configs: Record<string, AgentConfig>;
  onOpenBot: (name: string) => void;
  onOpenService?: (id: string) => void;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function CategorySection({
  category,
  agentsData,
  configs,
  onOpenBot,
  onOpenService,
  onFlash,
  onMutated,
}: CategorySectionProps) {
  const counts = categoryCounts(category.id);
  const Icon = category.icon;

  const headerInner = (
    <>
      <div className="flex items-center gap-2.5">
        <Icon size={16} strokeWidth={2} className="text-argos-fg-secondary" />
        <h2 className="text-sm font-semibold text-argos-fg">{category.title}</h2>
        <span className="font-mono text-[11px] text-argos-fg-tertiary">
          {counts.active} actif{counts.active > 1 ? "s" : ""} · {counts.roadmap} roadmap
        </span>
        {onOpenService && (
          <span className="font-mono text-[10px] text-argos-info opacity-0 group-hover:opacity-100 transition-opacity">
            Voir le service →
          </span>
        )}
      </div>
      <span className="font-mono text-[10px] text-argos-fg-tertiary hidden md:inline">
        {category.description}
      </span>
    </>
  );

  return (
    <section>
      {onOpenService ? (
        <button
          type="button"
          onClick={() => onOpenService(category.id)}
          className="group sticky top-0 z-10 bg-argos-bg/90 backdrop-blur-sm border-l-2 border-argos-info py-2.5 pl-3 pr-3 mb-3 flex items-center justify-between w-full text-left hover:bg-argos-bg/95 transition-colors"
          title={`Ouvrir la page service « ${category.title} »`}
        >
          {headerInner}
        </button>
      ) : (
        <header className="sticky top-0 z-10 bg-argos-bg/90 backdrop-blur-sm border-l-2 border-argos-info py-2.5 pl-3 pr-3 mb-3 flex items-center justify-between">
          {headerInner}
        </header>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {category.agents.map((agent) => (
          <AgentCard
            key={agent.displayName}
            agent={agent}
            liveData={agent.name ? agentsData.find((a) => a.name === agent.name) ?? null : null}
            config={agent.name ? configs[agent.name] ?? null : null}
            onOpenBot={onOpenBot}
            onFlash={onFlash}
            onMutated={onMutated}
          />
        ))}
      </div>
    </section>
  );
}

// =============================================================================
// Card agent (actif ou roadmap)
// =============================================================================
interface AgentCardProps {
  agent: CatalogAgent;
  liveData: AgentSummary | null;
  config: AgentConfig | null;
  onOpenBot: (name: string) => void;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function AgentCard({
  agent,
  liveData,
  config,
  onOpenBot,
  onFlash,
  onMutated,
}: AgentCardProps) {
  // Slot roadmap : card désaturée, pas d'actions.
  if (agent.status === "roadmap") {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface/60 p-4">
        <div className="flex items-center justify-between mb-1 gap-2">
          <span className="text-sm font-semibold text-argos-fg-secondary truncate">
            {agent.displayName}
          </span>
          <Badge tone="neutral">Roadmap</Badge>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
          {agent.shortLabel}
        </div>
        <p className="text-xs text-argos-fg-secondary leading-relaxed mb-2">
          {agent.description}
        </p>
        {agent.roadmapRef && (
          <div className="font-mono text-[10px] text-argos-fg-tertiary">
            {agent.roadmapRef}
          </div>
        )}
      </div>
    );
  }

  // Slot actif.
  const enabled = config?.enabled ?? true;
  const paused = Boolean(
    config?.paused_until && new Date(config.paused_until).getTime() > Date.now(),
  );
  const breakerTripped = liveData?.breaker_tripped ?? false;
  const [pending, setPending] = useState(false);

  const handleToggle = async () => {
    if (!agent.name) return;
    setPending(true);
    try {
      const next = !enabled;
      await patchAgentConfig(agent.name, { enabled: next });
      onFlash({
        variant: "success",
        msg: `${agent.name} : ${next ? "réactivé" : "désactivé"}`,
      });
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `${agent.name} toggle : ${(e as Error).message}` });
    } finally {
      setPending(false);
    }
  };

  const handlePause = async (minutes: number | "clear") => {
    if (!agent.name) return;
    setPending(true);
    try {
      if (minutes === "clear") {
        await patchAgentConfig(agent.name, { clear_paused: true });
        onFlash({ variant: "success", msg: `${agent.name} : pause levée` });
      } else {
        const until = new Date(Date.now() + minutes * 60 * 1000).toISOString();
        await patchAgentConfig(agent.name, { paused_until: until });
        onFlash({
          variant: "success",
          msg: `${agent.name} : pause ${minutes === 60 ? "1h" : "24h"} active`,
        });
      }
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `${agent.name} pause : ${(e as Error).message}` });
    } finally {
      setPending(false);
    }
  };

  const open = () => {
    if (agent.name) onOpenBot(agent.name);
  };

  return (
    <div className="rounded-md border bg-argos-surface p-4 transition-colors border-argos-border-subtle hover:border-argos-border">
      <div className="flex items-start justify-between mb-2 gap-2">
        <button
          type="button"
          onClick={open}
          className="text-left flex-1 min-w-0 group"
        >
          <div className="text-sm font-semibold text-argos-fg truncate group-hover:underline decoration-dotted underline-offset-2">
            {agent.displayName}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            {agent.shortLabel}
          </div>
        </button>
        <Toggle
          enabled={enabled}
          onChange={handleToggle}
          disabled={pending || !agent.name}
          label={`Activer / désactiver ${agent.displayName}`}
        />
      </div>

      <div className="mb-3">
        <StatusPill
          status={liveData?.last_run_status ?? null}
          disabled={!enabled}
          paused={paused}
          breakerTripped={breakerTripped}
        />
      </div>

      <div className="font-mono text-[11px] text-argos-fg-tertiary mb-3">
        Dernier run : {formatRelativeTime(liveData?.last_run_at ?? null)}
        {liveData?.last_run_duration_seconds !== null &&
          liveData?.last_run_duration_seconds !== undefined && (
            <span> · {formatDuration(liveData.last_run_duration_seconds)}</span>
          )}
      </div>

      {liveData?.last_run_output_summary && (
        <div className="font-mono text-[10px] text-argos-fg-secondary mb-3 line-clamp-2 break-words">
          {liveData.last_run_output_summary}
        </div>
      )}

      <div className="flex items-center gap-1.5 flex-wrap">
        {paused ? (
          <Button size="sm" variant="primary" onClick={() => handlePause("clear")} disabled={pending}>
            Reprendre
          </Button>
        ) : (
          <>
            <Button size="sm" onClick={() => handlePause(60)} disabled={pending || !enabled}>
              Pause 1h
            </Button>
            <Button
              size="sm"
              onClick={() => handlePause(24 * 60)}
              disabled={pending || !enabled}
            >
              24h
            </Button>
          </>
        )}
        <Button size="sm" variant="ghost" onClick={open}>
          Détails →
        </Button>
      </div>
    </div>
  );
}
