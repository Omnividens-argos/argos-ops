import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { AgentConfig, AgentSummary } from "../api";
import {
  fetchAgentConfig,
  fetchAgents,
  patchAgentConfig,
  runAgentNow,
} from "../api";
import { StatusPill } from "../components/StatusPill";
import { Badge, Button, Flash, Toggle } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import {
  AGENT_CATEGORIES,
  type CatalogAgent,
  type CatalogCategory,
  categoryCounts,
} from "../lib/agentCatalog";
import { formatDuration, formatRelativeTime } from "../lib/format";

// Vue Agents — 6 catégories empilées avec headers sticky + cards agent
// inline. Slots roadmap visibles mais désaturés. Décision 2026-05-12 (option a).
// Click sur une card → page dédiée (P16.C, via ``onOpenAgent``).

interface Props {
  /** Navigation vers la page dédiée d'un agent (P16.C). */
  onOpenAgent: (key: string) => void;
}

type FlashState = { variant: "success" | "error"; msg: string } | null;

export function Agents({ onOpenAgent }: Props) {
  const fetcher = useCallback((s?: AbortSignal) => fetchAgents(s), []);
  const { data: agents, error } = usePolling(fetcher);
  const [flash, setFlash] = useState<FlashState>(null);
  const [activeCategory, setActiveCategory] = useState<string | "all">("all");
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

  const visibleCategories =
    activeCategory === "all"
      ? AGENT_CATEGORIES
      : AGENT_CATEGORIES.filter((c) => c.id === activeCategory);

  return (
    <div className="p-6 space-y-5">
      {flash && (
        <Flash variant={flash.variant} message={flash.msg} onDismiss={() => setFlash(null)} />
      )}

      <CategoryFilter
        activeCategory={activeCategory}
        onChange={setActiveCategory}
      />

      <div className="space-y-6">
        {visibleCategories.map((cat) => (
          <CategorySection
            key={cat.id}
            category={cat}
            agentsData={agents ?? []}
            configs={configs}
            onOpenAgent={onOpenAgent}
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
// Filtre catégorie
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
        Filtrer
      </span>
      <ChipFilter
        label="Toutes"
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
  onOpenAgent: (key: string) => void;
  onFlash: (flash: FlashState) => void;
  onMutated: () => void;
}

function CategorySection({
  category,
  agentsData,
  configs,
  onOpenAgent,
  onFlash,
  onMutated,
}: CategorySectionProps) {
  const counts = categoryCounts(category.id);
  const Icon = category.icon;

  return (
    <section>
      <header className="sticky top-0 z-10 bg-argos-bg/90 backdrop-blur-sm border-l-2 border-argos-info py-2.5 pl-3 pr-3 mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Icon size={16} strokeWidth={2} className="text-argos-fg-secondary" />
          <h2 className="text-sm font-semibold text-argos-fg">{category.title}</h2>
          <span className="font-mono text-[11px] text-argos-fg-tertiary">
            {counts.active} actif{counts.active > 1 ? "s" : ""} · {counts.roadmap} roadmap
          </span>
        </div>
        <span className="font-mono text-[10px] text-argos-fg-tertiary hidden md:inline">
          {category.description}
        </span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {category.agents.map((agent) => (
          <AgentCard
            key={agent.displayName}
            agent={agent}
            liveData={agent.name ? agentsData.find((a) => a.name === agent.name) ?? null : null}
            config={agent.name ? configs[agent.name] ?? null : null}
            onOpenAgent={onOpenAgent}
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
  onOpenAgent: (key: string) => void;
  onFlash: (flash: FlashState) => void;
  onMutated: () => void;
}

function AgentCard({
  agent,
  liveData,
  config,
  onOpenAgent,
  onFlash,
  onMutated,
}: AgentCardProps) {
  const cardKey = agent.name ?? agent.displayName;

  // Slot roadmap : card désaturée, cliquable pour ouvrir la preview.
  if (agent.status === "roadmap") {
    return (
      <button
        type="button"
        onClick={() => onOpenAgent(cardKey)}
        className="text-left rounded-md border border-dashed border-argos-border-subtle bg-argos-surface/40 p-4 opacity-70 hover:opacity-100 hover:border-argos-border transition-all"
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-semibold text-argos-fg-secondary">
            {agent.displayName}
          </span>
          <Badge tone="neutral">Roadmap</Badge>
        </div>
        <div className="font-mono text-[11px] text-argos-fg-tertiary mb-2">
          {agent.shortLabel}
        </div>
        <p className="text-xs text-argos-fg-tertiary leading-relaxed mb-2">
          {agent.description}
        </p>
        {agent.roadmapRef && (
          <div className="font-mono text-[10px] text-argos-fg-disabled">
            {agent.roadmapRef}
          </div>
        )}
      </button>
    );
  }

  const enabled = config?.enabled ?? true;
  const paused = Boolean(
    config?.paused_until && new Date(config.paused_until).getTime() > Date.now(),
  );
  const breakerTripped = liveData?.breaker_tripped ?? false;
  const runnable = agent.runnable ?? false;
  const outboundConfirmation = agent.outboundConfirmation ?? false;
  const [pending, setPending] = useState<string | null>(null);
  const [confirmRun, setConfirmRun] = useState(false);

  const handleToggle = async () => {
    if (!agent.name) return;
    setPending("toggle");
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
      setPending(null);
    }
  };

  const handlePause = async (minutes: number | "clear") => {
    if (!agent.name) return;
    setPending("pause");
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
      setPending(null);
    }
  };

  const handleRunNow = async () => {
    if (!agent.name) return;
    if (outboundConfirmation && !confirmRun) {
      setConfirmRun(true);
      return;
    }
    setConfirmRun(false);
    setPending("run");
    try {
      const result = await runAgentNow(agent.name);
      onFlash({
        variant: result.status === "success" ? "success" : "error",
        msg: `${agent.name} → ${result.status}${
          result.output_summary ? ` · ${result.output_summary}` : ""
        }${result.error ? ` · ${result.error}` : ""}`,
      });
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `${agent.name} run : ${(e as Error).message}` });
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="relative rounded-md border bg-argos-surface p-4 border-argos-border-subtle hover:border-argos-border transition-colors">
      <div className="flex items-start justify-between mb-2">
        <button
          type="button"
          className="text-left flex-1 min-w-0 cursor-pointer hover:text-argos-info transition-colors"
          onClick={() => onOpenAgent(cardKey)}
          title="Ouvrir la page dédiée"
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-argos-fg truncate">
              {agent.displayName}
            </span>
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            {agent.shortLabel}
          </div>
        </button>
        <Toggle
          enabled={enabled}
          onChange={handleToggle}
          disabled={pending !== null || !agent.name}
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
        {runnable && (
          <Button
            size="sm"
            variant="primary"
            onClick={handleRunNow}
            disabled={pending !== null || breakerTripped}
            title={
              breakerTripped
                ? "Breaker tripped — reset avant de relancer"
                : "Déclencher un run manuel (respecte breaker / disabled / paused)"
            }
          >
            <span className="inline-flex items-center gap-1">
              <RefreshCw size={10} className={pending === "run" ? "animate-spin" : ""} />
              {pending === "run" ? "…" : "Run now"}
            </span>
          </Button>
        )}
        {paused ? (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => handlePause("clear")}
            disabled={pending !== null}
          >
            Reprendre
          </Button>
        ) : (
          <>
            <Button
              size="sm"
              onClick={() => handlePause(60)}
              disabled={pending !== null || !enabled}
            >
              Pause 1h
            </Button>
            <Button
              size="sm"
              onClick={() => handlePause(24 * 60)}
              disabled={pending !== null || !enabled}
            >
              24h
            </Button>
          </>
        )}
        <Button size="sm" variant="ghost" onClick={() => onOpenAgent(cardKey)}>
          Détails →
        </Button>
      </div>

      {/* Confirmation modale Run now pour les agents sortants */}
      {confirmRun && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-30 flex items-center justify-center bg-argos-bg/60 backdrop-blur-[2px]"
          onClick={() => setConfirmRun(false)}
        >
          <div
            className="bg-argos-surface border border-argos-warning/40 rounded-md p-5 max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-mono text-[10px] uppercase tracking-widest text-argos-warning mb-1">
              Confirmation
            </div>
            <h3 className="text-base font-semibold text-argos-fg mb-2">
              Lancer {agent.name} maintenant ?
            </h3>
            <p className="text-xs text-argos-fg-secondary mb-4">
              Cet agent peut envoyer du sortant (emails / relances Stripe).
              Vérifie son dernier run avant de confirmer — son idempotence
              évite les doublons, mais c'est plus sûr de regarder.
            </p>
            <div className="flex items-center gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setConfirmRun(false)}>
                Annuler
              </Button>
              <Button variant="primary" size="sm" onClick={handleRunNow}>
                Confirmer le run
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
