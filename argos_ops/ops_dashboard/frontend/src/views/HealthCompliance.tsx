import {
  AlertOctagon,
  CheckCircle2,
  Database,
  HeartPulse,
  Info,
  Shield,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import type { BreakerInfo, HealthSnapshot } from "../api";
import {
  fetchBreakers,
  fetchHealthSnapshot,
  resetBreaker,
  tripBreaker,
} from "../api";
import { EmptyState } from "../components/EmptyState";
import { SkeletonGrid, SkeletonList } from "../components/Skeleton";
import { Tooltip } from "../components/Tooltip";
import { Badge, Button, Flash, TextInput } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import {
  AI_ACT_LABEL,
  BOT_METADATA,
  type AIActRisk,
} from "../lib/botMetadata";
import { formatAbsoluteTime, formatRelativeTime } from "../lib/format";

// Vue Health & Compliance — absorbe l'ancienne page Breakers.
// Trois grandes sections :
//   1. Infra & flotte — snapshot DB, runs récents, agents par état config
//   2. Disjoncteurs (Breakers) — état + trip manuel + reset (ex-Breakers.tsx)
//   3. Conformité — distribution AI Act / PII / Bloctel calculée client-side
//                  depuis BOT_METADATA + agents connus
//
// Tout est lecture-écriture sur les endpoints existants — pas besoin d'un
// nouveau endpoint compliance côté backend.

const SEVERITY_TONE: Record<BreakerInfo["severity"], "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  warning: "warning",
  info: "info",
  unknown: "neutral",
};

export function HealthCompliance() {
  const health = usePolling(useCallback((s) => fetchHealthSnapshot(s), []), 30000);
  const breakers = usePolling(useCallback((s) => fetchBreakers(s), []), 10000);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; msg: string } | null>(null);
  const [bumpKey, setBumpKey] = useState(0);
  const refetch = () => setBumpKey((k) => k + 1);

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-argos-fg flex items-center gap-2">
          <HeartPulse size={22} strokeWidth={1.5} className="text-argos-info" />
          Health & Compliance
        </h1>
        <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
          Santé de la flotte (DB, runs, agents), disjoncteurs déclenchés, et
          conformité AI Act / RGPD / Bloctel — en un endroit unique.
        </p>
      </header>

      {flash && (
        <Flash
          variant={flash.variant}
          message={flash.msg}
          onDismiss={() => setFlash(null)}
        />
      )}

      {/* === 1. Infra & flotte === */}
      <InfraSection snapshot={health.data} error={health.error} />

      {/* === 2. Breakers === */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <AlertOctagon size={16} strokeWidth={2} className="text-argos-fg-secondary" />
          <h2 className="text-base font-semibold text-argos-fg">
            <Tooltip term="Breaker" decorate={false}>
              Disjoncteurs
            </Tooltip>
          </h2>
          {breakers.data && (
            <Badge tone={breakers.data.length > 0 ? "danger" : "healthy"}>
              {breakers.data.length}{" "}
              <Tooltip term="Tripped" decorate={false}>
                tripped
              </Tooltip>
            </Badge>
          )}
        </div>

        {/* Encart explicatif réutilisé de l'ex-Breakers.tsx */}
        <section className="rounded-md border border-argos-info/30 bg-argos-info/5 p-4 flex gap-3">
          <Info size={16} strokeWidth={2} className="text-argos-info shrink-0 mt-0.5" />
          <div className="space-y-1.5 text-xs text-argos-fg-secondary leading-relaxed">
            <p>
              Comme dans un tableau électrique : si quelque chose d'anormal
              arrive (chute MRR brutale, 3 erreurs Stripe d'affilée, etc.) un
              disjoncteur « saute » et coupe l'agent automatiquement pour
              éviter qu'il fasse des dégâts.
            </p>
            <p className="font-mono text-[10px] text-argos-fg-tertiary">
              Tu peux aussi en activer un manuellement (ex : avant de partir
              en vacances). Un breaker tripped doit être resetté manuellement
              après avoir corrigé la cause racine.
            </p>
          </div>
        </section>

        <TripBreakerForm onFlash={setFlash} onMutated={refetch} />

        {breakers.data === null && (
          <SkeletonList count={2} />
        )}
        {breakers.data?.length === 0 && (
          <EmptyState
            tone="celebrate"
            icon={CheckCircle2}
            title="Aucun disjoncteur déclenché ✨"
            body="Système nominal — tous les agents tournent dans leurs garde-fous."
            compact
          />
        )}
        <div className="space-y-2">
          {breakers.data?.map((breaker) => (
            <BreakerCard
              key={`${breaker.name}-${bumpKey}`}
              breaker={breaker}
              onFlash={setFlash}
              onMutated={refetch}
            />
          ))}
        </div>

        {breakers.error && (
          <Flash
            variant="error"
            message={`Erreur API breakers : ${breakers.error.message}`}
          />
        )}
      </section>

      {/* === 3. Compliance === */}
      <ComplianceSection />

      {/* === 4. À venir === */}
      <section className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface/40 p-4">
        <p className="text-xs text-argos-fg-tertiary leading-relaxed">
          <span className="text-argos-fg-secondary">À venir (Phase 4)</span> :
          secrets &gt; 90 j à rotater (SecretRotator), certificats SSL expirant
          (SSLExpirer), backups DB de la veille (BackupVerifier), CVE
          critiques sur stack clients (CVEMonitor) — chacun aggrege sa propre
          source côté backend.
        </p>
      </section>
    </div>
  );
}

// =============================================================================
// 1. Infra & flotte
// =============================================================================
function InfraSection({
  snapshot,
  error,
}: {
  snapshot: HealthSnapshot | null;
  error: Error | null;
}) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <Database size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
        <h2 className="text-base font-semibold text-argos-fg">Infrastructure & flotte</h2>
        <span className="font-mono text-[10px] text-argos-fg-tertiary">
          (snapshot 30 s)
        </span>
      </div>
      {error && <Flash variant="error" message={`Snapshot : ${error.message}`} />}
      {snapshot === null && error === null && (
        <SkeletonGrid count={4} cols="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" />
      )}
      {snapshot && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard
            label="Postgres"
            value={snapshot.db_ok ? "Online" : "DOWN"}
            tone={snapshot.db_ok ? "healthy" : "danger"}
            sub={
              snapshot.db_ok
                ? "Backend joignable"
                : "Backend ne peut pas se connecter à la DB"
            }
          />
          <StatCard
            label="Runs 24 h"
            value={`${snapshot.runs_last_24h}`}
            tone={
              snapshot.failed_last_24h > 0
                ? snapshot.failed_last_24h >= 3
                  ? "danger"
                  : "warning"
                : "neutral"
            }
            sub={`${snapshot.failed_last_24h} échec${snapshot.failed_last_24h !== 1 ? "s" : ""} · ${snapshot.runs_last_7d} sur 7 j`}
          />
          <StatCard
            label="Agents actifs"
            value={`${snapshot.agents_breakdown.enabled}`}
            tone="healthy"
            sub={`${snapshot.agents_breakdown.disabled} disabled · ${snapshot.agents_breakdown.paused} paused`}
          />
          <StatCard
            label="Breakers tripped"
            value={`${snapshot.tripped_breakers}`}
            tone={snapshot.tripped_breakers > 0 ? "danger" : "healthy"}
            sub={
              snapshot.tripped_breakers > 0
                ? snapshot.tripped_breaker_names.slice(0, 3).join(", ")
                : "Système nominal"
            }
          />
        </div>
      )}
    </section>
  );
}

// =============================================================================
// 3. Compliance section — counts depuis BOT_METADATA (client-side)
// =============================================================================
function ComplianceSection() {
  const counts = useMemo(() => {
    const aiAct: Record<AIActRisk, number> = {
      minimal: 0,
      limited: 0,
      high: 0,
      unacceptable: 0,
    };
    let pii = 0;
    let bloctel = 0;
    let totalKnown = 0;
    for (const meta of Object.values(BOT_METADATA)) {
      totalKnown++;
      aiAct[meta.aiActRisk]++;
      if (meta.handlesPII) pii++;
      if (meta.needsBloctel) bloctel++;
    }
    return { aiAct, pii, bloctel, totalKnown };
  }, []);

  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <Shield size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
        <h2 className="text-base font-semibold text-argos-fg">Conformité</h2>
        <span className="font-mono text-[10px] text-argos-fg-tertiary">
          (BOT_METADATA — {counts.totalKnown} bots documentés)
        </span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* AI Act risk distribution */}
        <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
            <Tooltip term="AI Act" decorate={false}>
              Distribution AI Act
            </Tooltip>
          </h3>
          <ul className="space-y-1.5">
            <RiskRow label="Minimal" count={counts.aiAct.minimal} total={counts.totalKnown} tone="healthy" />
            <RiskRow label="Limited (transparence)" count={counts.aiAct.limited} total={counts.totalKnown} tone="info" />
            <RiskRow label="High risk" count={counts.aiAct.high} total={counts.totalKnown} tone="warning" />
            <RiskRow label="Unacceptable" count={counts.aiAct.unacceptable} total={counts.totalKnown} tone="danger" />
          </ul>
          <p className="mt-3 font-mono text-[10px] text-argos-fg-tertiary leading-relaxed">
            Les bots {AI_ACT_LABEL.high} et {AI_ACT_LABEL.unacceptable} nécessitent un
            registre formel (RGPDAuditor, AIActComplianceBot s'en occupent
            automatiquement chaque lundi).
          </p>
        </div>

        {/* PII + Bloctel */}
        <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-4 space-y-3">
          <div>
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
              <Tooltip term="RGPD" decorate={false}>
                Bots qui traitent des données personnelles
              </Tooltip>
            </h3>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-medium text-argos-warning">
                {counts.pii}
              </span>
              <span className="font-mono text-[11px] text-argos-fg-tertiary">
                / {counts.totalKnown} bots — registre RGPD requis
              </span>
            </div>
          </div>
          <div className="border-t border-argos-border-subtle pt-3">
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
              <Tooltip term="Bloctel" decorate={false}>
                Bots concernés par le démarchage BtoC
              </Tooltip>
            </h3>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-mono font-medium text-argos-fg">
                {counts.bloctel}
              </span>
              <span className="font-mono text-[11px] text-argos-fg-tertiary">
                / {counts.totalKnown} bots — vérif Bloctel obligatoire
              </span>
            </div>
            {counts.bloctel === 0 && (
              <p className="mt-1 font-mono text-[10px] text-argos-fg-tertiary">
                Argos est 100 % BtoB — aucun bot BtoC actif.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function RiskRow({
  label,
  count,
  total,
  tone,
}: {
  label: string;
  count: number;
  total: number;
  tone: "healthy" | "warning" | "danger" | "info";
}) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const colors: Record<typeof tone, string> = {
    healthy: "bg-argos-healthy",
    warning: "bg-argos-warning",
    danger: "bg-argos-danger",
    info: "bg-argos-info",
  };
  return (
    <li>
      <div className="flex items-center justify-between font-mono text-[11px] mb-0.5">
        <span className="text-argos-fg-secondary">{label}</span>
        <span className="text-argos-fg">
          {count} <span className="text-argos-fg-tertiary">/ {total}</span>
        </span>
      </div>
      <div className="w-full h-1.5 rounded-full bg-argos-surface-2 overflow-hidden">
        <div
          className={`h-full ${colors[tone]} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </li>
  );
}

// =============================================================================
// Stat card (réutilisable pour la section infra)
// =============================================================================
function StatCard({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone: "healthy" | "warning" | "danger" | "neutral";
  sub?: string;
}) {
  const palette: Record<typeof tone, { border: string; bg: string; fg: string }> = {
    healthy: {
      border: "border-argos-healthy/30",
      bg: "bg-argos-healthy/5",
      fg: "text-argos-healthy",
    },
    warning: {
      border: "border-argos-warning/30",
      bg: "bg-argos-warning/5",
      fg: "text-argos-warning",
    },
    danger: {
      border: "border-argos-danger/40",
      bg: "bg-argos-danger/5",
      fg: "text-argos-danger",
    },
    neutral: {
      border: "border-argos-border-subtle",
      bg: "bg-argos-surface",
      fg: "text-argos-fg",
    },
  };
  const p = palette[tone];
  return (
    <div className={`rounded-md border ${p.border} ${p.bg} px-4 py-3`}>
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </div>
      <div className={`mt-1 text-xl font-mono font-medium ${p.fg}`}>{value}</div>
      {sub && (
        <div className="mt-0.5 font-mono text-[10px] text-argos-fg-tertiary truncate">
          {sub}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Trip breaker form (réutilisé de l'ex-Breakers.tsx, allégé)
// =============================================================================
function TripBreakerForm({
  onFlash,
  onMutated,
}: {
  onFlash: (f: { variant: "success" | "error"; msg: string }) => void;
  onMutated: () => void;
}) {
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [severity, setSeverity] = useState<"critical" | "warning" | "info">("warning");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!name || !reason) {
      onFlash({ variant: "error", msg: "Name et reason requis pour trip" });
      return;
    }
    setSubmitting(true);
    try {
      await tripBreaker(name, { reason, severity });
      onFlash({ variant: "success", msg: `Breaker '${name}' tripped` });
      setName("");
      setReason("");
      setSeverity("warning");
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `Trip : ${(e as Error).message}` });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
      <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
        Trip manuel
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr_auto_auto] gap-3 items-end">
        <TextInput
          label="Breaker name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="ex. FinanceBot, weekend_kill"
        />
        <TextInput
          label="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="contexte (audité dans breakers.notes)"
        />
        <div className="flex flex-col gap-1">
          <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Severity
          </label>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as "critical" | "warning" | "info")}
            className="bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg focus:outline-none focus:border-argos-info/60"
          >
            <option value="warning">warning</option>
            <option value="critical">critical</option>
            <option value="info">info</option>
          </select>
        </div>
        <Button variant="danger" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "…" : "Trip"}
        </Button>
      </div>
      <p className="mt-2 font-mono text-[10px] text-argos-fg-tertiary">
        Le trip manuel passé ici n'envoie pas de notif Discord (le fondateur
        agit consciemment).
      </p>
    </section>
  );
}

// =============================================================================
// Breaker card (réutilisé de l'ex-Breakers.tsx)
// =============================================================================
function BreakerCard({
  breaker,
  onFlash,
  onMutated,
}: {
  breaker: BreakerInfo;
  onFlash: (f: { variant: "success" | "error"; msg: string }) => void;
  onMutated: () => void;
}) {
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    if (
      !window.confirm(
        `Reset le breaker '${breaker.name}' ?\n\nMotif initial : ${breaker.reason ?? "—"}`,
      )
    ) {
      return;
    }
    setResetting(true);
    try {
      await resetBreaker(breaker.name);
      onFlash({ variant: "success", msg: `Breaker '${breaker.name}' reseté` });
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `Reset : ${(e as Error).message}` });
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="rounded-md border border-argos-danger/30 bg-argos-surface p-4 flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-sm font-semibold text-argos-fg">
            {breaker.name}
          </span>
          <Badge tone={SEVERITY_TONE[breaker.severity]}>{breaker.severity}</Badge>
        </div>
        {breaker.reason && (
          <div className="font-mono text-xs text-argos-fg-secondary break-words">
            {breaker.reason}
          </div>
        )}
        <div className="mt-1.5 font-mono text-[10px] text-argos-fg-tertiary">
          Tripped {formatRelativeTime(breaker.tripped_at)}
          {breaker.reset_after && (
            <>
              {" · "}auto-reset à {formatAbsoluteTime(breaker.reset_after)}
            </>
          )}
        </div>
      </div>
      <Button variant="primary" onClick={handleReset} disabled={resetting}>
        {resetting ? "…" : "Reset"}
      </Button>
    </div>
  );
}
