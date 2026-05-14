import { ArrowLeft, Pause, Play, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { AgentConfig, AgentRunRow, AgentSummary, BreakerInfo } from "../api";
import {
  fetchAgentConfig,
  fetchAgentRuns,
  fetchAgents,
  fetchBreakers,
  patchAgentConfig,
  runAgentNow,
} from "../api";
import { Sparkline } from "../components/Sparkline";
import { StatusPill } from "../components/StatusPill";
import { Badge, Button, Flash, Slider, TextInput, Toggle } from "../components/ui";
import { findAgentInCatalog } from "../lib/agentCatalog";
import {
  formatAbsoluteTime,
  formatDuration,
  formatRelativeTime,
  statusBgColor,
  statusColor,
} from "../lib/format";
import { AgentRoadmapDetail } from "./AgentRoadmapDetail";

// Page dédiée à un agent (P16.C) — accessible en cliquant sur sa card.
// Sections : header (back + status + Run now) → quick actions (toggle/pause) →
// métriques 7j → config form → breakers liés → 50 derniers runs.
// Pour les slots roadmap, on déboucle sur ``AgentRoadmapDetail`` qui sert
// de preview sans tirer de data backend (agent pas encore implémenté).

interface Props {
  agentKey: string;
  onBack: () => void;
}

export function AgentDetail({ agentKey, onBack }: Props) {
  const catalogEntry = findAgentInCatalog(agentKey);

  if (!catalogEntry) {
    return (
      <div className="p-6">
        <Button variant="ghost" onClick={onBack}>
          <span className="inline-flex items-center gap-1.5">
            <ArrowLeft size={12} /> Retour
          </span>
        </Button>
        <div className="mt-4 text-sm text-argos-fg-tertiary">
          Agent inconnu : <span className="font-mono">{agentKey}</span>.
        </div>
      </div>
    );
  }

  if (catalogEntry.agent.status === "roadmap") {
    return (
      <AgentRoadmapDetail
        agent={catalogEntry.agent}
        category={catalogEntry.category}
        onBack={onBack}
      />
    );
  }

  return (
    <ActiveAgentDetail
      agentName={catalogEntry.agent.name ?? catalogEntry.agent.displayName}
      categoryTitle={catalogEntry.category.title}
      runnable={catalogEntry.agent.runnable ?? false}
      outboundConfirmation={catalogEntry.agent.outboundConfirmation ?? false}
      description={catalogEntry.agent.description}
      shortLabel={catalogEntry.agent.shortLabel}
      onBack={onBack}
    />
  );
}

// =============================================================================
// Vue détail pour un agent actif
// =============================================================================
interface ActiveAgentDetailProps {
  agentName: string;
  categoryTitle: string;
  runnable: boolean;
  outboundConfirmation: boolean;
  description: string;
  shortLabel: string;
  onBack: () => void;
}

function ActiveAgentDetail({
  agentName,
  categoryTitle,
  runnable,
  outboundConfirmation,
  description,
  shortLabel,
  onBack,
}: ActiveAgentDetailProps) {
  const [summary, setSummary] = useState<AgentSummary | null>(null);
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [runs, setRuns] = useState<AgentRunRow[] | null>(null);
  const [breakers, setBreakers] = useState<BreakerInfo[] | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; msg: string } | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [confirmRun, setConfirmRun] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Charge tout (summary + config + runs + breakers) + repoll auto toutes les
  // 5s comme les autres vues, pour voir le run manuel apparaître en temps réel.
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    const loadAll = async () => {
      try {
        const [allAgents, cfg, recentRuns, allBreakers] = await Promise.all([
          fetchAgents(controller.signal),
          fetchAgentConfig(agentName, controller.signal),
          fetchAgentRuns(agentName, 50, controller.signal),
          fetchBreakers(controller.signal),
        ]);
        if (cancelled) return;
        setSummary(allAgents.find((a) => a.name === agentName) ?? null);
        setConfig(cfg);
        setRuns(recentRuns);
        setBreakers(allBreakers);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!cancelled) {
          setFlash({ variant: "error", msg: `Chargement : ${(err as Error).message}` });
        }
      }
    };

    void loadAll();
    const id = window.setInterval(() => void loadAll(), 5000);

    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(id);
    };
  }, [agentName, refreshKey]);

  const refetch = useCallback(() => setRefreshKey((k) => k + 1), []);

  const enabled = config?.enabled ?? true;
  const paused = Boolean(
    config?.paused_until && new Date(config.paused_until).getTime() > Date.now(),
  );
  const breakerTripped = summary?.breaker_tripped ?? false;
  const relatedBreakers = useMemo(
    () => (breakers ?? []).filter((b) => isRelatedBreaker(b.name, agentName)),
    [breakers, agentName],
  );

  const handleRunNow = async () => {
    if (outboundConfirmation && !confirmRun) {
      setConfirmRun(true);
      return;
    }
    setConfirmRun(false);
    setPendingAction("run");
    try {
      const result = await runAgentNow(agentName);
      setFlash({
        variant: result.status === "success" ? "success" : "error",
        msg: `${agentName} → ${result.status}${
          result.output_summary ? ` · ${result.output_summary}` : ""
        }${result.error ? ` · ${result.error}` : ""}`,
      });
      refetch();
    } catch (err) {
      setFlash({ variant: "error", msg: `Run now : ${(err as Error).message}` });
    } finally {
      setPendingAction(null);
    }
  };

  const handleToggle = async () => {
    setPendingAction("toggle");
    try {
      const next = !enabled;
      await patchAgentConfig(agentName, { enabled: next });
      setFlash({
        variant: "success",
        msg: `${agentName} : ${next ? "réactivé" : "désactivé"}`,
      });
      refetch();
    } catch (err) {
      setFlash({ variant: "error", msg: `Toggle : ${(err as Error).message}` });
    } finally {
      setPendingAction(null);
    }
  };

  const handlePause = async (minutes: number | "clear") => {
    setPendingAction("pause");
    try {
      if (minutes === "clear") {
        await patchAgentConfig(agentName, { clear_paused: true });
        setFlash({ variant: "success", msg: `${agentName} : pause levée` });
      } else {
        const until = new Date(Date.now() + minutes * 60 * 1000).toISOString();
        await patchAgentConfig(agentName, { paused_until: until });
        setFlash({
          variant: "success",
          msg: `${agentName} : pause ${minutes === 60 ? "1h" : minutes === 24 * 60 ? "24h" : `${minutes}min`} active`,
        });
      }
      refetch();
    } catch (err) {
      setFlash({ variant: "error", msg: `Pause : ${(err as Error).message}` });
    } finally {
      setPendingAction(null);
    }
  };

  const metrics = useMemo(() => computeMetrics(runs ?? []), [runs]);

  return (
    <div className="p-6 space-y-5">
      {flash && (
        <Flash variant={flash.variant} message={flash.msg} onDismiss={() => setFlash(null)} />
      )}

      {/* Header — back + name + status + Run now */}
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={onBack}>
              <span className="inline-flex items-center gap-1.5">
                <ArrowLeft size={12} /> Retour
              </span>
            </Button>
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
                {categoryTitle}
              </div>
              <h1 className="text-xl font-semibold text-argos-fg">{agentName}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <StatusPill
              status={summary?.last_run_status ?? null}
              disabled={!enabled}
              paused={paused}
              breakerTripped={breakerTripped}
            />
            {runnable ? (
              <Button
                variant="primary"
                size="md"
                onClick={handleRunNow}
                disabled={pendingAction !== null || breakerTripped}
              >
                <span className="inline-flex items-center gap-1.5">
                  <RefreshCw
                    size={12}
                    className={pendingAction === "run" ? "animate-spin" : ""}
                  />
                  {pendingAction === "run" ? "Exécution…" : "Run now"}
                </span>
              </Button>
            ) : (
              <Badge tone="neutral">Interactif uniquement</Badge>
            )}
          </div>
        </div>
        <p className="text-xs text-argos-fg-secondary max-w-3xl">{description}</p>
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {shortLabel}
        </div>
      </header>

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
            <h2 className="text-base font-semibold text-argos-fg mb-2">
              Lancer {agentName} maintenant ?
            </h2>
            <p className="text-xs text-argos-fg-secondary mb-4">
              Cet agent peut envoyer du sortant (emails / relances Stripe).
              S'il a déjà tourné aujourd'hui, son idempotence évite les doublons,
              mais vérifie le dernier run avant de confirmer.
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

      {/* Quick actions */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
              État
            </span>
            <Toggle
              enabled={enabled}
              onChange={handleToggle}
              disabled={pendingAction !== null}
              label={`Activer / désactiver ${agentName}`}
            />
            <span className="text-xs text-argos-fg-secondary">
              {enabled ? "Activé (cron actif)" : "Désactivé (cron skip)"}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {paused ? (
              <Button
                size="sm"
                variant="primary"
                onClick={() => handlePause("clear")}
                disabled={pendingAction !== null}
              >
                <span className="inline-flex items-center gap-1.5">
                  <Play size={11} /> Reprendre
                </span>
              </Button>
            ) : (
              <>
                <Button
                  size="sm"
                  onClick={() => handlePause(60)}
                  disabled={pendingAction !== null || !enabled}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Pause size={11} /> Pause 1h
                  </span>
                </Button>
                <Button
                  size="sm"
                  onClick={() => handlePause(24 * 60)}
                  disabled={pendingAction !== null || !enabled}
                >
                  Pause 24h
                </Button>
              </>
            )}
          </div>
        </div>
        {config?.paused_until && paused && (
          <div className="mt-2 font-mono text-[10px] text-argos-warning">
            Paused until {formatAbsoluteTime(config.paused_until)}
          </div>
        )}
      </section>

      {/* Métriques 7j */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Runs (50 derniers)"
          value={String(metrics.total)}
          tone="info"
        />
        <MetricCard
          label="Success rate"
          value={metrics.total === 0 ? "—" : `${metrics.successRate.toFixed(0)}%`}
          tone={
            metrics.total === 0 || metrics.successRate >= 95
              ? "healthy"
              : metrics.successRate >= 80
                ? "warning"
                : "danger"
          }
        />
        <MetricCard
          label="Durée moyenne"
          value={metrics.avgDuration === null ? "—" : formatDuration(metrics.avgDuration)}
          tone="neutral"
        />
        <MetricCard
          label="Sparkline 24h"
          value=""
          tone="neutral"
          extra={
            metrics.hourlyCounts.every((v) => v === 0) ? (
              <span className="font-mono text-[11px] text-argos-fg-tertiary">aucun run</span>
            ) : (
              <Sparkline
                values={metrics.hourlyCounts}
                width={120}
                height={28}
                colorClass="text-argos-info"
              />
            )
          }
        />
      </section>

      {/* Config runtime */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          Config runtime
        </h2>
        {config === null ? (
          <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
        ) : (
          <ConfigForm
            config={config}
            onSaved={(next) => {
              setConfig(next);
              setFlash({ variant: "success", msg: `${agentName} : config sauvegardée` });
              refetch();
            }}
            onError={(err) =>
              setFlash({ variant: "error", msg: `Config : ${err.message}` })
            }
          />
        )}
      </section>

      {/* Breakers liés */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          Breakers liés
        </h2>
        {breakers === null ? (
          <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
        ) : relatedBreakers.length === 0 ? (
          <div className="text-xs text-argos-fg-tertiary">
            Aucun breaker tripped pour cet agent.
          </div>
        ) : (
          <ul className="space-y-2">
            {relatedBreakers.map((b) => (
              <li
                key={b.name}
                className="rounded-md border border-argos-warning/30 bg-argos-warning/10 px-3 py-2"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="font-mono text-xs text-argos-fg">{b.name}</div>
                  <Badge tone={b.severity === "critical" ? "danger" : "warning"}>
                    {b.severity}
                  </Badge>
                </div>
                {b.reason && (
                  <div className="font-mono text-[11px] text-argos-fg-secondary mt-1">
                    {b.reason}
                  </div>
                )}
                {b.tripped_at && (
                  <div className="font-mono text-[10px] text-argos-fg-tertiary mt-0.5">
                    Tripped {formatRelativeTime(b.tripped_at)}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Historique runs */}
      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          50 derniers runs
        </h2>
        {runs === null ? (
          <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
        ) : runs.length === 0 ? (
          <div className="text-sm text-argos-fg-tertiary">Aucun run enregistré.</div>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <RunCard key={run.id} run={run} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// =============================================================================
// Sous-composants
// =============================================================================
function MetricCard({
  label,
  value,
  tone,
  extra,
}: {
  label: string;
  value: string;
  tone: "neutral" | "healthy" | "info" | "warning" | "danger";
  extra?: React.ReactNode;
}) {
  const toneMap: Record<typeof tone, string> = {
    neutral: "text-argos-fg",
    healthy: "text-argos-healthy",
    info: "text-argos-info",
    warning: "text-argos-warning",
    danger: "text-argos-danger",
  };
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-1.5">
        {label}
      </div>
      {value && (
        <div className={`text-lg font-semibold font-mono ${toneMap[tone]}`}>{value}</div>
      )}
      {extra && <div className="mt-1">{extra}</div>}
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
  const [scheduleCron, setScheduleCron] = useState(config.schedule_cron ?? "");
  const [notes, setNotes] = useState(config.notes ?? "");
  const [saving, setSaving] = useState(false);

  // Re-sync si la config externe change (refresh polling).
  useEffect(() => {
    setIntensity(config.intensity_level);
    setDailyLimit(config.daily_limit === null ? "" : String(config.daily_limit));
    setTier1(config.tier1_threshold);
    setScheduleCron(config.schedule_cron ?? "");
    setNotes(config.notes ?? "");
  }, [config]);

  const dirty =
    intensity !== config.intensity_level ||
    String(config.daily_limit ?? "") !== dailyLimit ||
    tier1 !== config.tier1_threshold ||
    (config.schedule_cron ?? "") !== scheduleCron ||
    (config.notes ?? "") !== notes;

  const handleSave = async () => {
    setSaving(true);
    try {
      const patched = await patchAgentConfig(config.agent_name, {
        intensity_level: intensity,
        daily_limit: dailyLimit === "" ? null : Number(dailyLimit),
        tier1_threshold: tier1,
        schedule_cron: scheduleCron === "" ? null : scheduleCron,
        notes: notes || null,
      });
      onSaved(patched);
    } catch (err) {
      onError(err as Error);
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
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
        <TextInput
          label="Schedule cron (info seul)"
          value={scheduleCron}
          onChange={(e) => setScheduleCron(e.target.value)}
          placeholder="0 8 * * *"
        />
      </div>

      <TextInput
        label="Notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="raison d'un état exceptionnel, contexte…"
      />

      <div className="flex items-center gap-2 pt-1 flex-wrap">
        <Button variant="primary" onClick={handleSave} disabled={!dirty || saving}>
          {saving ? "Sauvegarde…" : "Sauvegarder"}
        </Button>
        <Badge tone={config.enabled ? "healthy" : "danger"}>
          {config.enabled ? "enabled" : "disabled"}
        </Badge>
        {config.paused_until && (
          <Badge tone="warning">
            Paused until {formatAbsoluteTime(config.paused_until)}
          </Badge>
        )}
        <span className="font-mono text-[10px] text-argos-fg-tertiary ml-auto">
          updated {formatRelativeTime(config.updated_at)}
          {config.updated_by ? ` by ${config.updated_by}` : ""}
        </span>
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

// =============================================================================
// Helpers
// =============================================================================
function computeMetrics(runs: AgentRunRow[]): {
  total: number;
  successRate: number;
  avgDuration: number | null;
  hourlyCounts: number[];
} {
  if (runs.length === 0) {
    return {
      total: 0,
      successRate: 0,
      avgDuration: null,
      hourlyCounts: new Array(24).fill(0),
    };
  }
  const successful = runs.filter((r) => r.status === "success").length;
  const durations = runs
    .map((r) => r.duration_seconds)
    .filter((d): d is number => d !== null);
  const avgDuration =
    durations.length > 0 ? durations.reduce((a, b) => a + b, 0) / durations.length : null;

  // 24h sparkline : bucket par heure sur les dernières 24h.
  const now = Date.now();
  const cutoff = now - 24 * 60 * 60 * 1000;
  const hourlyCounts = new Array(24).fill(0) as number[];
  for (const run of runs) {
    const ts = new Date(run.started_at).getTime();
    if (ts < cutoff) continue;
    const hoursAgo = Math.floor((now - ts) / (60 * 60 * 1000));
    const bucket = 23 - hoursAgo;
    if (bucket >= 0 && bucket < 24) hourlyCounts[bucket] += 1;
  }

  return {
    total: runs.length,
    successRate: (successful / runs.length) * 100,
    avgDuration,
    hourlyCounts,
  };
}

function isRelatedBreaker(breakerName: string, agentName: string): boolean {
  // Kill switch global = exact match (DigestBuilder, EmailBot, FinanceBot,
  // SupportBot). Breakers métier = préfixe agent (ex : email_smtp_*,
  // mrr_drop_*, stripe_*).
  if (breakerName === agentName) return true;
  const prefixMap: Record<string, string[]> = {
    EmailBot: ["email_"],
    FinanceBot: ["mrr_", "stripe_"],
  };
  const prefixes = prefixMap[agentName] ?? [];
  return prefixes.some((p) => breakerName.startsWith(p));
}
