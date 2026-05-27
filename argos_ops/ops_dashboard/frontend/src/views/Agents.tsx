import { useCallback, useEffect, useState } from "react";
import type { AgentConfig, AgentRunRow, AgentSummary } from "../api";
import {
  fetchAgentConfig,
  fetchAgentRuns,
  fetchAgents,
  patchAgentConfig,
  runAgentNow,
} from "../api";
import { StatusPill } from "../components/StatusPill";
import { Badge, Button, Flash, Slider, TextInput, Toggle } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import {
  AGENT_CATEGORIES,
  type CatalogAgent,
  type CatalogCategory,
  categoryCounts,
  totalCounts,
} from "../lib/agentCatalog";
import {
  formatAbsoluteTime,
  formatDuration,
  formatRelativeTime,
  statusBgColor,
  statusColor,
} from "../lib/format";

// Vue Agents — 12 services empilés avec headers sticky + cards agent inline.
// Slots roadmap visibles mais désaturés. Catalogue : agentCatalog.ts.
// Révision 2026-05-23 : 12 services × 79 bots (cf. ARGOS_OPS_PLAN.md Annexe D).

type StatusFilter = "all" | "active" | "roadmap";

// Agents qu'on peut déclencher manuellement via "Run now" du drawer.
// Doit rester aligné avec ``argos_ops/ops_dashboard/app.py::RUNNABLE_AGENTS``.
// SupportBot et SEOBot sont interactifs (slash commands) — pas de bouton ici.
const RUNNABLE_AGENTS = new Set<string>([
  "DigestBuilder",
  "EmailBot",
  "FinanceBot",
  // Direction & Stratégie (P22.E).
  "StrategyBot",
  "OKRTracker",
  "BoardReporter",
  "DecisionLogger",
  // Finance & Trésorerie (P22.F).
  "InvoicePredictor",
  "ExpenseAuditor",
  "TaxBot",
  "ReconcileBot",
  "BurnRateMonitor",
  "VendorContractWatcher",
  // Sales / Commercial (P22.H).
  "OutboundBot",
  "LeadEnricher",
  "ProspectMiner",
  "IntentSignalsBot",
  "MeetingBooker",
  "DemoFollowupBot",
  "ProposalBot",
  "ContractGenerator",
  "DealRiskScorer",
  // Marketing & Growth (P22.I).
  "SEOBot",
  "ContentBot",
  "AdBot",
  "TrendSpotter",
  "NewsletterBot",
  "SocialAnalytics",
  "BacklinkOutreach",
  "KeywordRadar",
  "LandingOptimizer",
  "WebinarPromoter",
  "TestimonialHunter",
  "CaseStudyDrafter",
  // Customer Success & Support (P22.G).
  "SupportBot",
  "ReviewBot",
  "ChurnPredictor",
  "OnboardingBot",
  "HealthScoreBot",
  "KBUpdater",
  "NPSCollector",
  "UpsellSpotter",
  "EscalationRouter",
  // Produit & R&D (P22.J).
  "ChangelogBot",
  "ReleaseNotesBot",
  "FeedbackAggregator",
  "RoadmapPublisher",
  "BugTriageBot",
  // Tech / SRE / Sécurité IT (P22.C/D).
  "UptimeMonitor",
  "DependencyAuditor",
  "LogAnomalyDetector",
  "BackupVerifier",
  "SSLExpirer",
  "DNSGuard",
  "SecretRotator",
  "CIFlakeTracker",
  // Veille & Threat Intelligence (P22.D).
  "CompetitorWatcher",
  "BreachWatcher",
  "RegulatoryWatcher",
  "CVEMonitor",
  "DarkWebMonitor",
  "BountyRadar",
  // Juridique & Compliance (P22.K).
  "RGPDAuditor",
  "AIActComplianceBot",
  "BloctelGuard",
  "ContractDeadlineBot",
  "IncidentLogger",
  // Communication (P22.L) — EmailBot deja en tete (P5).
  "ReplyBot",
  "PressMonitor",
  "PressReleaseDrafter",
  "MediaListBuilder",
  "CrisisCommBot",
  "SpokespersonPrep",
  "BrandGuardBot",
  // Documentation (P22.M) — DiagramGenerator/ADRWriter exclus (input slug requis).
  "DocLinter",
]);

export function Agents() {
  const fetcher = useCallback((s?: AbortSignal) => fetchAgents(s), []);
  const { data: agents, error } = usePolling(fetcher);
  const [selected, setSelected] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; msg: string } | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
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

  const visibleCategories = (
    activeCategory === "all"
      ? AGENT_CATEGORIES
      : AGENT_CATEGORIES.filter((c) => c.id === activeCategory)
  )
    .map((cat) => ({
      ...cat,
      agents: cat.agents
        .filter((a) => statusFilter === "all" || a.status === statusFilter)
        // actifs d'abord, puis roadmap (ordre catalog respecté par ailleurs)
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

      <CategoryFilter
        activeCategory={activeCategory}
        onChange={setActiveCategory}
      />

      <StatusFilterBar value={statusFilter} onChange={setStatusFilter} />

      <div className="space-y-6">
        {visibleCategories.length === 0 && (
          <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface/40 p-6 text-center text-sm text-argos-fg-tertiary">
            Aucun bot ne correspond à ces filtres.
          </div>
        )}
        {visibleCategories.map((cat) => (
          <CategorySection
            key={cat.id}
            category={cat}
            agentsData={agents ?? []}
            configs={configs}
            onSelect={setSelected}
            selected={selected}
            onFlash={setFlash}
            onMutated={refetch}
          />
        ))}
      </div>

      {error && (
        <Flash variant="error" message={`Erreur API : ${error.message}`} />
      )}

      {selected && (
        <AgentDrawer
          agentName={selected}
          onClose={() => setSelected(null)}
          onFlash={setFlash}
          onMutated={refetch}
        />
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
  onSelect: (name: string) => void;
  selected: string | null;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function CategorySection({
  category,
  agentsData,
  configs,
  onSelect,
  selected,
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
            onSelect={() => agent.name && onSelect(agent.name)}
            selected={agent.name === selected}
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
  onSelect: () => void;
  selected: boolean;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function AgentCard({ agent, liveData, config, onSelect, selected, onFlash, onMutated }: AgentCardProps) {
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

  // Slot actif sans data API (jamais exécuté, ex : SupportBot interactif).
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

  return (
    <div
      className={`rounded-md border bg-argos-surface p-4 transition-colors ${
        selected
          ? "border-argos-info/50 ring-1 ring-argos-info/20"
          : "border-argos-border-subtle hover:border-argos-border"
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="cursor-pointer flex-1 min-w-0" onClick={onSelect}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-argos-fg truncate">
              {agent.displayName}
            </span>
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            {agent.shortLabel}
          </div>
        </div>
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
        <Button size="sm" variant="ghost" onClick={onSelect}>
          Détails
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// Drawer agent : Config + Logs (inchangé depuis session 2, simplifié)
// =============================================================================
interface DrawerProps {
  agentName: string;
  onClose: () => void;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function AgentDrawer({ agentName, onClose, onFlash, onMutated }: DrawerProps) {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [runs, setRuns] = useState<AgentRunRow[] | null>(null);
  const [running, setRunning] = useState(false);

  const refetchRuns = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const next = await fetchAgentRuns(agentName, 50, signal);
        setRuns(next);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        console.warn(e);
      }
    },
    [agentName],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchAgentConfig(agentName, controller.signal)
      .then(setConfig)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        console.warn(e);
      });
    refetchRuns(controller.signal);
    return () => controller.abort();
  }, [agentName, refetchRuns]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const result = await runAgentNow(agentName);
      // Le verdict final est dans result.status — le wrapper run_agent peut
      // renvoyer skipped_* si l'agent était disabled/paused/over-quota.
      const variant = result.status === "success" ? "success" : "error";
      const msg =
        result.status === "success"
          ? `${agentName} : run OK${result.output_summary ? ` — ${result.output_summary.slice(0, 80)}` : ""}`
          : `${agentName} : ${result.status}${result.error ? ` — ${result.error.slice(0, 100)}` : ""}`;
      onFlash({ variant, msg });
      await refetchRuns();
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `${agentName} Run now : ${(e as Error).message}` });
    } finally {
      setRunning(false);
    }
  };

  const isRunnable = RUNNABLE_AGENTS.has(agentName);

  return (
    <div className="fixed inset-0 z-20 flex">
      <div className="flex-1 bg-argos-bg/60 backdrop-blur-[2px]" onClick={onClose} />
      <aside className="w-[720px] max-w-full bg-argos-surface border-l border-argos-border-subtle flex flex-col">
        <div className="px-5 py-4 border-b border-argos-border-subtle flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
              Détails agent
            </div>
            <div className="text-base font-semibold text-argos-fg truncate">{agentName}</div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isRunnable && (
              <Button
                size="sm"
                variant="primary"
                onClick={handleRunNow}
                disabled={running}
                title="Déclenche un run immédiat (respecte breaker/disabled/paused/daily_limit)"
              >
                {running ? "Run…" : "Run now"}
              </Button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="font-mono text-xs text-argos-fg-secondary hover:text-argos-fg px-2 py-1 rounded border border-argos-border-subtle hover:bg-argos-surface-2"
            >
              Esc
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <section>
            <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
              Config runtime
            </h3>
            {config === null && (
              <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
            )}
            {config && (
              <ConfigForm
                config={config}
                onSaved={(next) => {
                  setConfig(next);
                  onMutated();
                  onFlash({ variant: "success", msg: `${agentName} : config sauvegardée` });
                }}
                onError={(e) =>
                  onFlash({ variant: "error", msg: `${agentName} config : ${e.message}` })
                }
              />
            )}
          </section>

          <section>
            <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
              50 derniers runs
            </h3>
            {runs === null && (
              <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
            )}
            {runs?.length === 0 && (
              <div className="text-sm text-argos-fg-tertiary">Aucun run enregistré.</div>
            )}
            <div className="space-y-2">
              {runs?.map((run) => <RunCard key={run.id} run={run} />)}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

interface ConfigFormProps {
  config: AgentConfig;
  onSaved: (next: AgentConfig) => void;
  onError: (err: Error) => void;
}

function ConfigForm({ config, onSaved, onError }: ConfigFormProps) {
  const [intensity, setIntensity] = useState(config.intensity_level);
  const [dailyLimit, setDailyLimit] = useState(
    config.daily_limit === null ? "" : String(config.daily_limit),
  );
  const [tier1, setTier1] = useState(config.tier1_threshold);
  const [notes, setNotes] = useState(config.notes ?? "");
  const [saving, setSaving] = useState(false);

  const dirty =
    intensity !== config.intensity_level ||
    String(config.daily_limit ?? "") !== dailyLimit ||
    tier1 !== config.tier1_threshold ||
    (config.notes ?? "") !== notes;

  const handleSave = async () => {
    setSaving(true);
    try {
      const patched = await patchAgentConfig(config.agent_name, {
        intensity_level: intensity,
        daily_limit: dailyLimit === "" ? null : Number(dailyLimit),
        tier1_threshold: tier1,
        notes: notes || null,
      });
      onSaved(patched);
    } catch (e) {
      onError(e as Error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Intensity level
          </label>
          <span className="font-mono text-xs text-argos-fg">{intensity} / 10</span>
        </div>
        <Slider value={intensity} onValueChange={setIntensity} />
        <p className="mt-1 font-mono text-[10px] text-argos-fg-tertiary">
          1 = éco · 5 = défaut · 10 = max gourmand (scale interne aux agents)
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <TextInput
          label="Daily limit (vide = illimité)"
          type="number"
          min="0"
          value={dailyLimit}
          onChange={(e) => setDailyLimit(e.target.value)}
          placeholder="ex. 50"
        />
        <TextInput
          label="Tier 1 threshold (0-100)"
          type="number"
          min="0"
          max="100"
          value={String(tier1)}
          onChange={(e) => setTier1(Number(e.target.value))}
        />
      </div>

      <TextInput
        label="Notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="raison d'un état exceptionnel, contexte…"
      />

      <div className="flex items-center gap-2 pt-1 flex-wrap">
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          {saving ? "Sauvegarde…" : "Sauvegarder"}
        </Button>
        {config.paused_until && (
          <Badge tone="warning">
            Paused until {formatAbsoluteTime(config.paused_until)}
          </Badge>
        )}
        <Badge tone={config.enabled ? "healthy" : "danger"}>
          {config.enabled ? "enabled" : "disabled"}
        </Badge>
      </div>
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
