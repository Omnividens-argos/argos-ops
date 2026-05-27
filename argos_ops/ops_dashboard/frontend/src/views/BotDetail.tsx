import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  FileCode,
  FileText,
  History,
  Inbox as InboxIcon,
  PauseCircle,
  Play,
  Puzzle,
  Settings,
  Shield,
  TimerReset,
  Workflow,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  AgentConfig,
  AgentPerfStats,
  AgentRunRow,
  AgentSummary,
  InboxDraft,
  YamlConfigResponse,
} from "../api";
import {
  fetchAgentConfig,
  fetchAgentPerf,
  fetchAgentRuns,
  fetchAgentYamlConfig,
  fetchAgents,
  fetchInboxDrafts,
  patchAgentConfig,
  patchAgentYamlConfig,
  runAgentNow,
} from "../api";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { Tooltip, TooltipIcon } from "../components/Tooltip";
import { YamlEditor } from "../components/YamlEditor";
import { SkeletonCard, SkeletonGrid, SkeletonList } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { Badge, Button, Flash, Slider, TextInput, Toggle } from "../components/ui";
import { useUserPrefs } from "../hooks/useUserPrefs";
import { usePolling } from "../hooks/usePolling";
import {
  AI_ACT_LABEL,
  type BotMetadata,
  lookupBot,
  lookupSkill,
} from "../lib/botMetadata";
import { AGENT_CATEGORIES, type CatalogAgent } from "../lib/agentCatalog";
import {
  formatAbsoluteTime,
  formatDuration,
  formatRelativeTime,
  statusBgColor,
  statusColor,
} from "../lib/format";

// BotDetail — page-level vue détaillée par bot. 10 sections empilées :
//   1. Hero / identité
//   2. État live (4 KPI cards : last run, stats 7j, erreurs récentes, breaker)
//   3. Configuration (mode débutant / expert)
//   4. Sources de données (YAML config externe, si applicable)
//   5. Skills & dépendances
//   6. Conformité (AI Act, PII, Bloctel)
//   7. Drafts produits (filtrés sur cet agent)
//   8. Historique runs
//   9. Documentation & code (deeplinks)
//
// Le mode débutant masque les contrôles avancés (intensity, daily limit,
// tier1 threshold). Le mode expert les déplie. Toggle global via UserPrefs.

interface BotDetailProps {
  botName: string;
  runnableAgents: ReadonlySet<string>;
  onBack: () => void;
  onOpenInbox: () => void;
}

export function BotDetail({
  botName,
  runnableAgents,
  onBack,
  onOpenInbox,
}: BotDetailProps) {
  const { mode } = useUserPrefs();
  const meta = lookupBot(botName);
  const catalogEntry = findInCatalog(botName);

  const agents = usePolling(useCallback((s) => fetchAgents(s), []));
  const live = agents.data?.find((a) => a.name === botName) ?? null;

  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [configError, setConfigError] = useState<Error | null>(null);

  const runsFetcher = useCallback(
    (s?: AbortSignal) => fetchAgentRuns(botName, 50, s),
    [botName],
  );
  const runs = usePolling(runsFetcher, 5000);

  const perfFetcher = useCallback(
    (s?: AbortSignal) => fetchAgentPerf(botName, 7, s),
    [botName],
  );
  const perf = usePolling(perfFetcher, 60000);

  const draftsFetcher = useCallback((s?: AbortSignal) => fetchInboxDrafts(s), []);
  const drafts = usePolling(draftsFetcher, 30000);
  const draftsForThisBot = useMemo(
    () => (drafts.data ?? []).filter((d) => d.agent_name === botName),
    [drafts.data, botName],
  );

  const toast = useToast();
  const [running, setRunning] = useState(false);

  // Charge initial de la config par bot.
  useEffect(() => {
    const controller = new AbortController();
    setConfig(null);
    setConfigError(null);
    fetchAgentConfig(botName, controller.signal)
      .then(setConfig)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setConfigError(e as Error);
      });
    return () => controller.abort();
  }, [botName]);

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const result = await runAgentNow(botName);
      if (result.status === "success") {
        toast.success(
          `Run OK${result.output_summary ? ` — ${result.output_summary.slice(0, 100)}` : ""}`,
        );
      } else {
        toast.error(
          `${result.status}${result.error ? ` — ${result.error.slice(0, 120)}` : ""}`,
        );
      }
    } catch (e) {
      toast.error(`Run now : ${(e as Error).message}`);
    } finally {
      setRunning(false);
    }
  };

  const handleToggle = async (next: boolean) => {
    if (!config) return;
    try {
      const patched = await patchAgentConfig(botName, { enabled: next });
      setConfig(patched);
      toast.success(next ? "Agent réactivé" : "Agent désactivé");
    } catch (e) {
      toast.error(`Toggle : ${(e as Error).message}`);
    }
  };

  const handlePause = async (minutes: number | "clear") => {
    try {
      if (minutes === "clear") {
        const patched = await patchAgentConfig(botName, { clear_paused: true });
        setConfig(patched);
        toast.success("Pause levée");
      } else {
        const until = new Date(Date.now() + minutes * 60 * 1000).toISOString();
        const patched = await patchAgentConfig(botName, { paused_until: until });
        setConfig(patched);
        toast.success(`Pause ${minutes === 60 ? "1 h" : "24 h"} active`);
      }
    } catch (e) {
      toast.error(`Pause : ${(e as Error).message}`);
    }
  };

  const isRunnable = runnableAgents.has(botName);
  const enabled = config?.enabled ?? true;
  const paused = Boolean(
    config?.paused_until && new Date(config.paused_until).getTime() > Date.now(),
  );

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      {/* === Back === */}
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg transition-colors"
      >
        <ArrowLeft size={12} strokeWidth={2} />
        Retour au catalogue
      </button>

      {/* === 1. Hero === */}
      <HeroSection
        botName={botName}
        catalog={catalogEntry}
        meta={meta}
        live={live}
        paused={paused}
        enabled={enabled}
        running={running}
        isRunnable={isRunnable}
        canControl={config !== null}
        onRunNow={handleRunNow}
        onToggle={handleToggle}
        onPause={handlePause}
      />

      {/* === 2. État live === */}
      <LiveStateSection perf={perf.data} live={live} />

      {/* === 3. Configuration === */}
      <ConfigSection
        config={config}
        configError={configError}
        mode={mode}
        onSaved={(next) => {
          setConfig(next);
          toast.success("Config sauvegardée");
        }}
        onError={(e) => toast.error(`Config : ${e.message}`)}
      />

      {/* === 4. Sources de données (YAML externe) === */}
      {meta.configFile && (
        <YamlConfigSection
          botName={botName}
          fallbackPath={meta.configFile}
          onSaved={() => toast.success("Fichier YAML sauvegardé")}
          onError={(msg) => toast.error(msg)}
        />
      )}

      {/* === 5. Skills & dépendances === */}
      <SkillsSection meta={meta} />

      {/* === 6. Conformité === */}
      <ComplianceSection meta={meta} />

      {/* === 7. Drafts produits === */}
      {draftsForThisBot.length > 0 && (
        <DraftsSection
          drafts={draftsForThisBot}
          onOpenInbox={onOpenInbox}
        />
      )}

      {/* === 8. Historique runs === */}
      <RunsSection runs={runs.data} />

      {/* === 9. Doc & code === */}
      <DocSection botName={botName} meta={meta} />
    </div>
  );
}

// =============================================================================
// 1. Hero
// =============================================================================
interface HeroProps {
  botName: string;
  catalog: { agent: CatalogAgent; category: string } | null;
  meta: BotMetadata;
  live: AgentSummary | null;
  paused: boolean;
  enabled: boolean;
  running: boolean;
  isRunnable: boolean;
  canControl: boolean;
  onRunNow: () => void;
  onToggle: (next: boolean) => void;
  onPause: (minutes: number | "clear") => void;
}

function HeroSection({
  botName,
  catalog,
  meta,
  live,
  paused,
  enabled,
  running,
  isRunnable,
  canControl,
  onRunNow,
  onToggle,
  onPause,
}: HeroProps) {
  return (
    <header className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h1 className="text-2xl font-semibold text-argos-fg">{botName}</h1>
            {catalog?.category && <Badge tone="neutral">{catalog.category}</Badge>}
            {paused && <Badge tone="warning">paused</Badge>}
            {!enabled && <Badge tone="danger">disabled</Badge>}
          </div>
          {catalog?.agent.shortLabel && (
            <div className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
              {catalog.agent.shortLabel}
            </div>
          )}
          <p className="mt-2 text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
            {catalog?.agent.description ?? "Agent autonome de la flotte Argos Ops."}
          </p>
          <div className="mt-2 flex items-center gap-3 flex-wrap font-mono text-[10px] text-argos-fg-tertiary">
            {meta.sprintRef && <span>{meta.sprintRef}</span>}
            {meta.schedule && <span>· cadence {meta.schedule}</span>}
          </div>
        </div>

        <div className="shrink-0 flex flex-col items-end gap-3">
          <div className="flex items-center gap-3">
            <StatusPill
              status={live?.last_run_status ?? null}
              breakerTripped={live?.breaker_tripped ?? false}
              paused={paused}
              disabled={!enabled}
            />
            <Toggle
              enabled={enabled}
              onChange={onToggle}
              disabled={!canControl}
              label={`Activer / désactiver ${botName}`}
            />
          </div>
          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            {isRunnable && (
              <Button
                variant="primary"
                size="sm"
                onClick={onRunNow}
                disabled={running}
              >
                <span className="inline-flex items-center gap-1.5">
                  <Play size={11} strokeWidth={2} />
                  {running ? "Run en cours…" : "Run now"}
                </span>
              </Button>
            )}
            {paused ? (
              <Button size="sm" variant="primary" onClick={() => onPause("clear")}>
                <span className="inline-flex items-center gap-1">
                  <TimerReset size={11} strokeWidth={2} />
                  Reprendre
                </span>
              </Button>
            ) : (
              <>
                <Button size="sm" onClick={() => onPause(60)} disabled={!enabled}>
                  <span className="inline-flex items-center gap-1">
                    <PauseCircle size={11} strokeWidth={2} />
                    1 h
                  </span>
                </Button>
                <Button size="sm" onClick={() => onPause(24 * 60)} disabled={!enabled}>
                  24 h
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
      {live?.last_run_output_summary && (
        <div className="mt-4 font-mono text-[11px] text-argos-fg-secondary border-t border-argos-border-subtle pt-3 break-words">
          <span className="text-argos-fg-tertiary">Dernier résultat :</span>{" "}
          {live.last_run_output_summary}
        </div>
      )}
    </header>
  );
}

// =============================================================================
// 2. État live (4 KPI cards)
// =============================================================================
function LiveStateSection({
  perf,
  live,
}: {
  perf: AgentPerfStats | null;
  live: AgentSummary | null;
}) {
  if (perf === null) {
    return (
      <section>
        <SectionHeader title="État live" subtitle="Snapshot des 7 derniers jours" />
        <SkeletonGrid count={4} cols="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" />
      </section>
    );
  }
  return (
    <section>
      <SectionHeader title="État live" subtitle="Snapshot des 7 derniers jours" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Runs 7 j"
          value={perf ? `${perf.total_runs}` : "—"}
          tone="neutral"
          sub={
            perf
              ? `${perf.success_count} ✓ · ${perf.failed_count} ✗ · ${perf.skipped_count} ⏸`
              : undefined
          }
        />
        <KpiCard
          label="Taux d'erreur"
          tooltipTerm="P95"
          value={perf ? formatPercent(perf.error_rate) : "—"}
          tone={
            !perf
              ? "neutral"
              : perf.error_rate >= 0.2
                ? "danger"
                : perf.error_rate >= 0.05
                  ? "warning"
                  : "healthy"
          }
          sub={
            perf && perf.total_runs === 0
              ? "Pas de run sur la fenêtre"
              : perf
                ? `${perf.failed_count} sur ${perf.total_runs}`
                : undefined
          }
        />
        <KpiCard
          label="Durée P95"
          tooltipTerm="P95"
          value={
            perf && perf.p95_duration_seconds !== null
              ? formatDuration(perf.p95_duration_seconds)
              : "—"
          }
          tone="neutral"
          sub={
            perf && perf.p50_duration_seconds !== null
              ? `P50 ${formatDuration(perf.p50_duration_seconds)}`
              : undefined
          }
        />
        <KpiCard
          label="Breaker"
          tooltipTerm="Breaker"
          value={live?.breaker_tripped ? "TRIPPED" : "OK"}
          tone={live?.breaker_tripped ? "danger" : "healthy"}
          sub={live?.breaker_tripped ? live.breaker_reason ?? "" : "système nominal"}
        />
      </div>
    </section>
  );
}

// =============================================================================
// 3. Configuration (débutant / expert)
// =============================================================================
function ConfigSection({
  config,
  configError,
  mode,
  onSaved,
  onError,
}: {
  config: AgentConfig | null;
  configError: Error | null;
  mode: "beginner" | "expert";
  onSaved: (next: AgentConfig) => void;
  onError: (e: Error) => void;
}) {
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Settings size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
          <h2 className="text-sm font-semibold text-argos-fg">Configuration</h2>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            (s'applique au prochain run)
          </span>
        </div>
        <Badge tone="neutral">
          Mode {mode === "beginner" ? "débutant" : "expert"}
        </Badge>
      </div>
      {configError && (
        <Flash
          variant="error"
          message={`Impossible de charger la config : ${configError.message}`}
        />
      )}
      {config === null && configError === null && (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}
      {config && <ConfigForm config={config} mode={mode} onSaved={onSaved} onError={onError} />}
    </section>
  );
}

interface ConfigFormProps {
  config: AgentConfig;
  mode: "beginner" | "expert";
  onSaved: (next: AgentConfig) => void;
  onError: (err: Error) => void;
}

function ConfigForm({ config, mode, onSaved, onError }: ConfigFormProps) {
  const [intensity, setIntensity] = useState(config.intensity_level);
  const [dailyLimit, setDailyLimit] = useState(
    config.daily_limit === null ? "" : String(config.daily_limit),
  );
  const [tier1, setTier1] = useState(config.tier1_threshold);
  const [notes, setNotes] = useState(config.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(mode === "expert");

  useEffect(() => {
    setIntensity(config.intensity_level);
    setDailyLimit(config.daily_limit === null ? "" : String(config.daily_limit));
    setTier1(config.tier1_threshold);
    setNotes(config.notes ?? "");
  }, [config]);

  // Sync de l'état affiché avec le mode global :
  //   - Mode expert → panneau toujours déplié (et figé ouvert)
  //   - Mode débutant → repli par défaut quand l'user revient en débutant,
  //     mais il garde la liberté de l'ouvrir à la main via le toggle
  useEffect(() => {
    setShowAdvanced(mode === "expert");
  }, [mode]);

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

  // En mode expert, le panneau est figé ouvert (pas de bouton replier — la
  // bascule passe par la sidebar). En mode débutant, l'user peut déplier
  // ET replier à la demande.
  const canCollapse = mode === "beginner";

  return (
    <div className="space-y-4">
      {/* Notes — visible en débutant ET expert */}
      <div>
        <TextInput
          label="Notes (contexte, raison d'un état exceptionnel)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="ex. désactivé temporairement pour debug X, ou intensité réduite pour budget Y."
        />
        <p className="mt-1 font-mono text-[10px] text-argos-fg-tertiary">
          Texte libre archivé avec la config. Sert à toi (et tes collègues
          futurs) à te souvenir pourquoi tu as touché à l'agent.
        </p>
      </div>

      {/* Toggle déplier / replier — visible uniquement en mode débutant.
          En expert le panneau est déjà ouvert (sidebar = source unique). */}
      {canCollapse && (
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="font-mono text-[11px] text-argos-info hover:underline"
        >
          {showAdvanced
            ? "− Replier les options avancées"
            : "+ Options avancées (intensité, plafond quotidien, seuil auto-validation)"}
        </button>
      )}

      {showAdvanced && (
        <div className="space-y-5 border-t border-argos-border-subtle pt-4">
          {/* ── Intensity ───────────────────────────────────────────── */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
                Niveau d'intensité (1 — 10)
              </label>
              <span className="font-mono text-xs text-argos-fg">
                {intensity} / 10
              </span>
            </div>
            <Slider value={intensity} onValueChange={setIntensity} />
            <p className="mt-2 text-xs text-argos-fg-secondary leading-relaxed">
              <span className="text-argos-fg">À quel point l'agent travaille « fort »</span> à chaque run. Concrètement :
              <span className="font-mono text-[11px] text-argos-fg-tertiary"> 1 = mode éco</span> (moins d'appels API, scope réduit, finit vite),
              <span className="font-mono text-[11px] text-argos-fg-tertiary"> 5 = défaut</span> (comportement de référence),
              <span className="font-mono text-[11px] text-argos-fg-tertiary"> 10 = max</span> (le bot creuse à fond — plus de tokens, plus long, parfois meilleur).
              Effet exact propre à chaque bot. <span className="text-argos-warning">Ne touche pas si tu n'as pas une raison précise.</span>
            </p>
          </div>

          {/* ── Daily limit ─────────────────────────────────────────── */}
          <div>
            <TextInput
              label="Plafond quotidien — laisser vide pour illimité"
              type="number"
              min="0"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(e.target.value)}
              placeholder="ex. 50"
            />
            <p className="mt-1 text-xs text-argos-fg-secondary leading-relaxed">
              <span className="text-argos-fg">Nombre maximum de runs autorisés sur 24 h glissantes</span>.
              Au-delà, l'agent renvoie <code className="font-mono text-[11px]">skipped_daily_limit</code> sans s'exécuter.
              Utile pour <span className="text-argos-fg-tertiary">capper un coût</span> (ex. OutboundBot à 30 envois/jour) ou <span className="text-argos-fg-tertiary">limiter un agent en mode test</span>.
              <span className="block font-mono text-[10px] text-argos-fg-tertiary mt-0.5">
                Vide = pas de plafond. 0 = bot bloqué tant que tu n'as pas mis une autre valeur.
              </span>
            </p>
          </div>

          {/* ── Tier 1 threshold ────────────────────────────────────── */}
          <div>
            <TextInput
              label="Seuil d'auto-validation (0 — 100)"
              type="number"
              min="0"
              max="100"
              value={String(tier1)}
              onChange={(e) => setTier1(Number(e.target.value))}
            />
            <p className="mt-1 text-xs text-argos-fg-secondary leading-relaxed">
              <span className="text-argos-fg">Score minimum donné par le juge IA</span> (<Tooltip term="Tier 1">claude-judge</Tooltip>) pour que le draft soit considéré « Tier 1 » et envoyé sans relecture humaine.
              En-dessous du seuil → escalade dans l'Inbox pour validation.
              <span className="block font-mono text-[10px] text-argos-fg-tertiary mt-0.5">
                Concerne uniquement les bots qui draftent (Email, Outbound, Content, etc.). Sans effet sur les watchers / monitors.
                <br />
                Pour Argos : <span className="text-argos-fg">70 par défaut</span>. Plus haut = plus strict (moins d'auto-envoi). Plus bas = plus laxiste.
              </span>
            </p>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1 flex-wrap">
        <Button variant="primary" onClick={handleSave} disabled={!dirty || saving}>
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
        <span className="font-mono text-[10px] text-argos-fg-tertiary">
          Last update {formatRelativeTime(config.updated_at)}
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// 4. Sources de données (YAML externe)
// =============================================================================
function YamlConfigSection({
  botName,
  fallbackPath,
  onSaved,
  onError,
}: {
  botName: string;
  fallbackPath: string;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [data, setData] = useState<YamlConfigResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setLoadError(null);
    fetchAgentYamlConfig(botName, controller.signal)
      .then(setData)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setLoadError((e as Error).message);
      });
    return () => controller.abort();
  }, [botName, reloadKey]);

  const canEdit = data ? data.relative_path.endsWith(".yaml") : true;

  const handleSave = async (next: string) => {
    setSaving(true);
    try {
      const patched = await patchAgentYamlConfig(botName, next);
      setData(patched);
      onSaved();
    } catch (e) {
      onError(`YAML : ${(e as Error).message}`);
      throw e;
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <SectionHeader
        title="Sources de données"
        subtitle={`Fichier de config externe — ${data?.relative_path ?? fallbackPath}`}
        icon={FileText}
      />
      {loadError && <Flash variant="error" message={loadError} />}
      {data === null && loadError === null && (
        <EmptyState tone="loading" title="Lecture du fichier…" compact />
      )}
      {data && (
        <YamlEditor
          serverContent={data.content}
          relativePath={data.relative_path}
          exists={data.exists}
          canEdit={canEdit}
          saving={saving}
          onSave={handleSave}
          onReload={() => setReloadKey((k) => k + 1)}
        />
      )}
      {data?.last_modified && (
        <p className="mt-2 font-mono text-[10px] text-argos-fg-tertiary">
          Dernière modif {formatRelativeTime(data.last_modified)}.
        </p>
      )}
    </section>
  );
}

// =============================================================================
// 5. Skills & dépendances
// =============================================================================
function SkillsSection({ meta }: { meta: BotMetadata }) {
  if (!meta.skills?.length && !meta.envVars?.length) return null;
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <SectionHeader
        title="Skills & dépendances"
        subtitle="Helpers Claude consommés + variables d'env requises"
        icon={Puzzle}
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
            Skills
          </h3>
          {(meta.skills ?? []).length === 0 ? (
            <div className="font-mono text-[11px] text-argos-fg-tertiary">
              Aucun skill externe — agent autonome.
            </div>
          ) : (
            <ul className="space-y-1.5">
              {(meta.skills ?? []).map((slug) => {
                const info = lookupSkill(slug);
                return (
                  <li
                    key={slug}
                    className="rounded-md border border-argos-border-subtle px-3 py-2 flex items-start gap-2"
                  >
                    <CheckCircle2
                      size={13}
                      strokeWidth={2}
                      className="text-argos-healthy shrink-0 mt-0.5"
                    />
                    <div className="min-w-0">
                      <div className="font-mono text-xs text-argos-fg">
                        {info?.label ?? slug}
                      </div>
                      {info?.description && (
                        <div className="font-mono text-[10px] text-argos-fg-tertiary leading-snug">
                          {info.description}
                        </div>
                      )}
                      {info?.location && (
                        <div className="font-mono text-[10px] text-argos-fg-tertiary mt-0.5">
                          {info.location}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div>
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
            Variables d'env requises
          </h3>
          {(meta.envVars ?? []).length === 0 ? (
            <div className="font-mono text-[11px] text-argos-fg-tertiary">
              Aucune variable d'env spécifique requise.
            </div>
          ) : (
            <ul className="space-y-1">
              {(meta.envVars ?? []).map((name) => (
                <li
                  key={name}
                  className="font-mono text-[11px] text-argos-fg-secondary flex items-center gap-2"
                >
                  <span className="size-1.5 rounded-full bg-argos-fg-tertiary" />
                  {name}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 font-mono text-[10px] text-argos-fg-tertiary leading-relaxed">
            La présence effective de ces variables côté serveur n'est pas exposée par l'API (sécurité). Vérifie dans <code>.env</code> ou via <code>echo $VAR</code>.
          </p>
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// 6. Conformité
// =============================================================================
function ComplianceSection({ meta }: { meta: BotMetadata }) {
  const aiActTone: Record<typeof meta.aiActRisk, "healthy" | "info" | "warning" | "danger"> = {
    minimal: "healthy",
    limited: "info",
    high: "warning",
    unacceptable: "danger",
  };
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <SectionHeader
        title="Conformité"
        subtitle="AI Act · RGPD · Bloctel"
        icon={Shield}
      />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <ComplianceRow
          label="Classe AI Act"
          tooltipTerm="AI Act"
          value={
            <Badge tone={aiActTone[meta.aiActRisk]}>
              {AI_ACT_LABEL[meta.aiActRisk]}
            </Badge>
          }
        />
        <ComplianceRow
          label="Traitement PII (RGPD)"
          tooltipTerm="RGPD"
          value={
            <Badge tone={meta.handlesPII ? "warning" : "neutral"}>
              {meta.handlesPII ? "Oui — registre requis" : "Non"}
            </Badge>
          }
        />
        <ComplianceRow
          label="Vérif Bloctel"
          tooltipTerm="Bloctel"
          value={
            <Badge tone={meta.needsBloctel ? "warning" : "neutral"}>
              {meta.needsBloctel ? "Requis (BtoC)" : "N/A"}
            </Badge>
          }
        />
      </div>
    </section>
  );
}

function ComplianceRow({
  label,
  tooltipTerm,
  value,
}: {
  label: string;
  tooltipTerm?: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1 mb-1">
        {label}
        {tooltipTerm && <TooltipIcon term={tooltipTerm} />}
      </div>
      <div className="flex items-center">{value}</div>
    </div>
  );
}

// =============================================================================
// 7. Drafts produits
// =============================================================================
function DraftsSection({
  drafts,
  onOpenInbox,
}: {
  drafts: InboxDraft[];
  onOpenInbox: () => void;
}) {
  return (
    <section className="rounded-md border border-argos-info/30 bg-argos-info/5 p-5">
      <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <InboxIcon size={14} strokeWidth={2} className="text-argos-info" />
          <h2 className="text-sm font-semibold text-argos-fg">
            Drafts produits par ce bot
          </h2>
          <Badge tone="info">{drafts.length} en attente</Badge>
        </div>
        <button
          type="button"
          onClick={onOpenInbox}
          className="font-mono text-[11px] text-argos-info hover:underline flex items-center gap-1"
        >
          Voir dans l'Inbox
          <ArrowUpRight size={11} strokeWidth={2} />
        </button>
      </div>
      <ul className="space-y-1.5">
        {drafts.slice(0, 5).map((d) => (
          <li
            key={d.id}
            className="rounded-md bg-argos-surface px-3 py-2 flex items-start justify-between gap-3 border border-argos-border-subtle"
          >
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-argos-fg truncate">
                {d.title}
              </div>
              <div className="font-mono text-[10px] text-argos-fg-tertiary">
                {formatRelativeTime(d.created_at)} · {d.file_path}
              </div>
            </div>
            <Badge tone="info">{d.status}</Badge>
          </li>
        ))}
        {drafts.length > 5 && (
          <li className="font-mono text-[10px] text-argos-fg-tertiary text-center pt-1">
            +{drafts.length - 5} de plus — voir Inbox
          </li>
        )}
      </ul>
    </section>
  );
}

// =============================================================================
// 8. Historique runs
// =============================================================================
function RunsSection({ runs }: { runs: AgentRunRow[] | null }) {
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "failed" | "skipped">(
    "all",
  );
  const filtered = useMemo(() => {
    if (!runs) return [];
    if (statusFilter === "all") return runs;
    if (statusFilter === "skipped") return runs.filter((r) => (r.status ?? "").startsWith("skipped_"));
    return runs.filter((r) => r.status === statusFilter);
  }, [runs, statusFilter]);

  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <History size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
        <h2 className="text-sm font-semibold text-argos-fg">Historique runs</h2>
        <span className="font-mono text-[10px] text-argos-fg-tertiary">
          (50 derniers, polling 5 s)
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          {(["all", "success", "failed", "skipped"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`font-mono text-[10px] px-2 py-0.5 rounded border transition-colors ${
                statusFilter === s
                  ? "bg-argos-info/15 border-argos-info/40 text-argos-info"
                  : "bg-argos-surface border-argos-border-subtle text-argos-fg-tertiary hover:text-argos-fg"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
      {runs === null && <SkeletonList count={3} />}
      {runs?.length === 0 && (
        <EmptyState
          tone="neutral"
          title="Pas encore de run"
          body="Cet agent n'a jamais été déclenché. Lance-le manuellement via « Run now » ou attends son créneau cron."
          compact
        />
      )}
      {runs && runs.length > 0 && filtered.length === 0 && (
        <EmptyState
          tone="neutral"
          title="Aucun run ne correspond"
          body="Le filtre statut exclut tout l'historique. Repasse sur « all »."
          compact
        />
      )}
      <div className="space-y-2">
        {filtered.map((run) => (
          <RunCard key={run.id} run={run} />
        ))}
      </div>
    </section>
  );
}

function RunCard({ run }: { run: AgentRunRow }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail =
    Boolean(run.output_summary && run.output_summary.length > 120) ||
    Boolean(run.error);
  return (
    <div className={`rounded-md border px-3 py-2.5 ${statusBgColor(run.status)}`}>
      <button
        type="button"
        onClick={() => hasDetail && setExpanded((e) => !e)}
        className={`w-full text-left ${hasDetail ? "cursor-pointer" : "cursor-default"}`}
      >
        <div className="flex items-center justify-between text-xs gap-3">
          <div className={`font-mono ${statusColor(run.status)} truncate`}>
            #{run.id} · {run.status ?? "?"}
          </div>
          <div className="font-mono text-argos-fg-tertiary shrink-0">
            {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
          </div>
        </div>
        {run.output_summary && (
          <div
            className={`mt-1.5 font-mono text-[11px] text-argos-fg-secondary break-words ${
              expanded ? "" : "line-clamp-2"
            }`}
          >
            {run.output_summary}
          </div>
        )}
        {run.error && expanded && (
          <div className="mt-1.5 font-mono text-[11px] text-argos-danger break-words whitespace-pre-wrap">
            {run.error}
          </div>
        )}
        {!expanded && run.error && (
          <div className="mt-1.5 font-mono text-[11px] text-argos-danger line-clamp-1">
            {run.error}
          </div>
        )}
        {hasDetail && (
          <div className="mt-1 font-mono text-[10px] text-argos-fg-tertiary">
            {expanded ? "▾ replier" : "▸ déplier détails"}
          </div>
        )}
      </button>
    </div>
  );
}

// =============================================================================
// 9. Doc & code (deeplinks copyables)
// =============================================================================
function DocSection({ botName, meta }: { botName: string; meta: BotMetadata }) {
  const links: { label: string; path: string; icon: typeof BookOpen }[] = [];
  if (meta.pythonModule) {
    links.push({ label: "Module Python", path: meta.pythonModule, icon: FileCode });
  }
  if (meta.slashCommand) {
    links.push({
      label: "Slash command",
      path: `.claude/commands/${meta.slashCommand}.md`,
      icon: BookOpen,
    });
  }
  // Tests par convention
  links.push({
    label: "Tests",
    path: `tests/test_${snakeCase(botName)}.py`,
    icon: Workflow,
  });
  // Annexe D
  links.push({
    label: "Annexe D (plan stratégique)",
    path: "docs/ARGOS_OPS_PLAN.md#annexe-d",
    icon: BookOpen,
  });

  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
      <SectionHeader
        title="Documentation & code"
        subtitle="Deeplinks vers les ressources liées à ce bot"
        icon={ExternalLink}
      />
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {links.map((link) => (
          <DocLink key={link.path} {...link} />
        ))}
      </ul>
    </section>
  );
}

function DocLink({
  label,
  path,
  icon: Icon,
}: {
  label: string;
  path: string;
  icon: typeof BookOpen;
}) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard
      .writeText(path)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => undefined);
  };
  return (
    <li>
      <button
        type="button"
        onClick={copy}
        className="w-full text-left rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2 hover:border-argos-border transition-colors group"
        title="Cliquer pour copier le chemin"
      >
        <div className="flex items-center gap-2 mb-1">
          <Icon size={12} strokeWidth={2} className="text-argos-fg-tertiary" />
          <span className="text-xs font-medium text-argos-fg">{label}</span>
          <span className="ml-auto font-mono text-[10px] text-argos-fg-tertiary group-hover:text-argos-fg">
            {copied ? "copié ✓" : "copier"}
          </span>
        </div>
        <div className="font-mono text-[10px] text-argos-fg-tertiary truncate">
          {path}
        </div>
      </button>
    </li>
  );
}

// =============================================================================
// Helpers
// =============================================================================
function findInCatalog(
  botName: string,
): { agent: CatalogAgent; category: string } | null {
  for (const cat of AGENT_CATEGORIES) {
    const match = cat.agents.find((a) => a.name === botName);
    if (match) return { agent: match, category: cat.title };
  }
  return null;
}

function snakeCase(name: string): string {
  return name.replace(/([a-z])([A-Z])/g, "$1_$2").toLowerCase();
}

function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)} %`;
}

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  icon?: typeof BookOpen;
}

function SectionHeader({ title, subtitle, icon: Icon }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mb-3 flex-wrap">
      {Icon && <Icon size={14} strokeWidth={2} className="text-argos-fg-tertiary" />}
      <h2 className="text-sm font-semibold text-argos-fg">{title}</h2>
      {subtitle && (
        <span className="font-mono text-[10px] text-argos-fg-tertiary">{subtitle}</span>
      )}
    </div>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  tooltipTerm?: string;
  tone: "healthy" | "warning" | "danger" | "neutral";
  sub?: string;
}

function KpiCard({ label, value, tooltipTerm, tone, sub }: KpiCardProps) {
  const palette: Record<
    KpiCardProps["tone"],
    { border: string; valueFg: string; bg: string }
  > = {
    healthy: {
      border: "border-argos-healthy/30",
      valueFg: "text-argos-healthy",
      bg: "bg-argos-healthy/5",
    },
    warning: {
      border: "border-argos-warning/30",
      valueFg: "text-argos-warning",
      bg: "bg-argos-warning/5",
    },
    danger: {
      border: "border-argos-danger/40",
      valueFg: "text-argos-danger",
      bg: "bg-argos-danger/5",
    },
    neutral: {
      border: "border-argos-border-subtle",
      valueFg: "text-argos-fg",
      bg: "bg-argos-surface",
    },
  };
  const p = palette[tone];
  return (
    <div className={`rounded-md border ${p.border} ${p.bg} px-4 py-3`}>
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1">
        {label}
        {tooltipTerm && <TooltipIcon term={tooltipTerm} />}
      </div>
      <div className={`mt-1 text-xl font-mono font-medium ${p.valueFg}`}>{value}</div>
      {sub && (
        <div className="mt-0.5 font-mono text-[10px] text-argos-fg-tertiary truncate">
          {sub}
        </div>
      )}
    </div>
  );
}
