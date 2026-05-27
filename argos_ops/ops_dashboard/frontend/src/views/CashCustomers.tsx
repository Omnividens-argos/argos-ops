import {
  ArrowUpRight,
  Banknote,
  Building2,
  Kanban,
  LifeBuoy,
  TrendingUp,
  Users,
} from "lucide-react";
import { useCallback } from "react";
import type { CashSnapshot, CohortsResponse } from "../api";
import { fetchCashSnapshot, fetchCohorts } from "../api";
import { EmptyState } from "../components/EmptyState";
import { SkeletonGrid } from "../components/Skeleton";
import { TooltipIcon } from "../components/Tooltip";
import { Badge, Flash } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatEur, formatRelativeTime } from "../lib/format";

// Vue Cash & Customers — page financière / clients.
// Source unique : /api/cash/snapshot (Stripe + leads + tickets, aggregé backend).
// Pas de graphique historique pour l'instant — pas d'aggregate temporel stocké.

interface CashCustomersProps {
  onOpenPipeline?: () => void;
}

export function CashCustomers({ onOpenPipeline }: CashCustomersProps = {}) {
  const snapshot = usePolling(useCallback((s) => fetchCashSnapshot(s), []), 30000);
  const cohorts = usePolling(useCallback((s) => fetchCohorts(6, s), []), 60000);

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <header className="space-y-1">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h1 className="text-2xl font-semibold text-argos-fg flex items-center gap-2">
            <Banknote size={22} strokeWidth={1.5} className="text-argos-healthy" />
            Cash & Customers
          </h1>
          {onOpenPipeline && (
            <button
              type="button"
              onClick={onOpenPipeline}
              className="inline-flex items-center gap-1.5 font-mono text-[11px] text-argos-info hover:underline"
            >
              <Kanban size={12} strokeWidth={2} />
              Ouvrir le pipeline commercial
              <ArrowUpRight size={11} strokeWidth={2} />
            </button>
          )}
        </div>
        <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
          Revenu, abonnements, leads, tickets — la santé financière et
          relationnelle d'Argos en un coup d'œil.
        </p>
        {snapshot.lastRefreshedAt && (
          <p className="font-mono text-[10px] text-argos-fg-tertiary">
            Snapshot rafraîchi {formatRelativeTime(snapshot.lastRefreshedAt.toISOString())}{" "}
            · poll toutes les 30 s.
          </p>
        )}
      </header>

      {snapshot.error && (
        <Flash
          variant="error"
          message={`Impossible de charger le snapshot : ${snapshot.error.message}`}
        />
      )}

      {snapshot.data === null && snapshot.error === null && (
        <SkeletonGrid count={3} cols="grid-cols-1 sm:grid-cols-3" />
      )}

      {snapshot.data && <CashContent data={snapshot.data} />}

      {/* === Cohortes de rétention === */}
      {cohorts.data && cohorts.data.has_data && cohorts.data.rows.length > 0 && (
        <CohortsSection data={cohorts.data} />
      )}
    </div>
  );
}

function CashContent({ data }: { data: CashSnapshot }) {
  return (
    <>
      {/* Hero revenue cards */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <HeroCard
          label="MRR"
          tooltipTerm="MRR"
          value={formatEur(data.mrr_eur)}
          tone="healthy"
          icon={Banknote}
        />
        <HeroCard
          label="ARR"
          tooltipTerm="ARR"
          value={formatEur(data.arr_eur)}
          tone="healthy"
          icon={TrendingUp}
        />
        <HeroCard
          label="Abonnements actifs"
          value={`${data.active_subscriptions}`}
          tone="neutral"
          icon={Building2}
          sub={
            data.active_subscriptions === 0
              ? "Aucun abonnement actif"
              : `${data.subs_breakdown.active} active · ${data.subs_breakdown.trialing} trialing`
          }
        />
      </section>

      {/* Subs breakdown */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <SectionHeader
          title="Abonnements — répartition par statut"
          icon={Building2}
          subtitle="Snapshot Stripe (companies.subscription_status)"
        />
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <BreakdownCard
            label="Active"
            count={data.subs_breakdown.active}
            tone="healthy"
          />
          <BreakdownCard
            label="Trialing"
            count={data.subs_breakdown.trialing}
            tone="info"
          />
          <BreakdownCard
            label="Past due"
            count={data.subs_breakdown.past_due}
            tone={data.subs_breakdown.past_due > 0 ? "warning" : "neutral"}
          />
          <BreakdownCard
            label="Canceled"
            count={data.subs_breakdown.canceled}
            tone="neutral"
          />
          <BreakdownCard
            label="Autre"
            count={data.subs_breakdown.other}
            tone="neutral"
          />
        </div>
        {data.subs_breakdown.past_due > 0 && (
          <p className="mt-3 font-mono text-[11px] text-argos-warning">
            ⚠ {data.subs_breakdown.past_due} abonnement
            {data.subs_breakdown.past_due > 1 ? "s" : ""} en past_due —
            FinanceBot devrait avoir lancé une séquence de relance{" "}
            <TooltipIcon term="Dunning" />.
          </p>
        )}
      </section>

      {/* Leads */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <SectionHeader
          title="Leads inbound"
          icon={Users}
          subtitle="Comptés depuis la table leads sur 3 fenêtres temporelles"
        />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <BreakdownCard
            label="24 h"
            count={data.leads_last_24h}
            tone={data.leads_last_24h > 0 ? "info" : "neutral"}
          />
          <BreakdownCard
            label="7 j"
            count={data.leads_last_7d}
            tone={data.leads_last_7d > 0 ? "info" : "neutral"}
          />
          <BreakdownCard
            label="30 j"
            count={data.leads_last_30d}
            tone={data.leads_last_30d > 0 ? "info" : "neutral"}
          />
        </div>
        {data.leads_last_24h === 0 && data.leads_last_7d === 0 && (
          <p className="mt-3 font-mono text-[11px] text-argos-fg-tertiary">
            Aucun lead inbound sur les 7 derniers jours. ProspectMiner +
            IntentSignalsBot devraient cracher des leads outbound — vois leur
            page bot pour les configurer.
          </p>
        )}
      </section>

      {/* Tickets */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <SectionHeader
          title="Tickets ouverts"
          icon={LifeBuoy}
          subtitle="Par priorité — escalade humaine pilotée par EscalationRouter"
        />
        {data.open_tickets === 0 ? (
          <EmptyState
            tone="celebrate"
            title="Aucun ticket ouvert ✨"
            body="Tout est traité — bravo. EscalationRouter vérifie automatiquement les SLA toutes les 15 min."
            compact
          />
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <BreakdownCard
                label="P0 (critical)"
                count={data.tickets_breakdown.p0}
                tone={data.tickets_breakdown.p0 > 0 ? "danger" : "neutral"}
              />
              <BreakdownCard
                label="P1 (high)"
                count={data.tickets_breakdown.p1}
                tone={data.tickets_breakdown.p1 > 0 ? "warning" : "neutral"}
              />
              <BreakdownCard
                label="P2 (medium)"
                count={data.tickets_breakdown.p2}
                tone="info"
              />
              <BreakdownCard
                label="Autre"
                count={data.tickets_breakdown.other}
                tone="neutral"
              />
            </div>
            <p className="mt-3 font-mono text-[11px] text-argos-fg-tertiary">
              Total : {data.open_tickets} ticket{data.open_tickets > 1 ? "s" : ""} ouvert
              {data.open_tickets > 1 ? "s" : ""}.
            </p>
          </>
        )}
      </section>

      {/* Footnote — what's coming */}
      <section className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface/40 p-4">
        <p className="text-xs text-argos-fg-tertiary leading-relaxed">
          <span className="text-argos-fg-secondary">À venir (Phase 4)</span> :
          courbe MRR / churn / NRR sur 12 mois (InvoicePredictor + ChurnPredictor),
          health scores par client (HealthScoreBot), prédiction cash 30/60/90 j.
        </p>
      </section>
    </>
  );
}

// =============================================================================
// Cohortes — table de rétention par mois de signup
// =============================================================================
function CohortsSection({ data }: { data: CohortsResponse }) {
  const months = data.months_tracked;
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5 overflow-x-auto">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <TrendingUp size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
        <h2 className="text-sm font-semibold text-argos-fg">
          Cohortes de rétention
        </h2>
        <span className="font-mono text-[10px] text-argos-fg-tertiary">
          (approx — pas d'historique Stripe local, on regarde le statut actuel)
        </span>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-argos-border-subtle">
            <th className="text-left font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary pb-2 pr-3">
              Cohorte (signup)
            </th>
            <th className="text-right font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary pb-2 pr-3">
              Taille
            </th>
            {Array.from({ length: months }, (_, i) => (
              <th
                key={i}
                className="text-right font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary pb-2 px-2"
              >
                M+{i}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.signup_month} className="border-b border-argos-border-subtle/40">
              <td className="py-2 pr-3 font-mono text-argos-fg">{row.signup_month}</td>
              <td className="py-2 pr-3 font-mono text-right text-argos-fg-secondary">
                {row.cohort_size}
              </td>
              {row.retained_by_month.map((count, idx) => {
                const pct = row.cohort_size > 0 ? count / row.cohort_size : 0;
                return (
                  <td key={idx} className="py-2 px-2 text-right">
                    <CohortCell count={count} pct={pct} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 font-mono text-[10px] text-argos-fg-tertiary leading-relaxed">
        <span className="text-argos-fg-secondary">Lecture</span> : M+0 = mois de signup (taille de la cohorte).
        M+1 = un mois après. Le pourcentage indique la part de la cohorte
        toujours active aujourd'hui (approximation tant qu'on n'a pas d'events
        Stripe historisés).
      </p>
    </section>
  );
}

function CohortCell({ count, pct }: { count: number; pct: number }) {
  // Color scale du blanc au vert en fonction de la rétention.
  const bg =
    pct >= 0.9
      ? "bg-argos-healthy/30 text-argos-healthy"
      : pct >= 0.5
        ? "bg-argos-healthy/15 text-argos-healthy"
        : pct >= 0.25
          ? "bg-argos-warning/15 text-argos-warning"
          : pct > 0
            ? "bg-argos-danger/15 text-argos-danger"
            : "bg-argos-surface-2 text-argos-fg-tertiary";
  return (
    <span
      className={`inline-block min-w-[3rem] rounded px-2 py-0.5 font-mono ${bg}`}
      title={`${count} / cohorte (${Math.round(pct * 100)} %)`}
    >
      {count > 0 ? `${count}` : "—"}
    </span>
  );
}

// =============================================================================
// Hero card
// =============================================================================
function HeroCard({
  label,
  tooltipTerm,
  value,
  tone,
  icon: Icon,
  sub,
}: {
  label: string;
  tooltipTerm?: string;
  value: string;
  tone: "healthy" | "warning" | "danger" | "neutral";
  icon: typeof Banknote;
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
    <div className={`rounded-md border ${p.border} ${p.bg} p-5`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} strokeWidth={1.5} className="text-argos-fg-tertiary" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1">
          {label}
          {tooltipTerm && <TooltipIcon term={tooltipTerm} />}
        </span>
      </div>
      <div className={`text-3xl font-mono font-medium ${p.fg}`}>{value}</div>
      {sub && (
        <div className="mt-1 font-mono text-[10px] text-argos-fg-tertiary">
          {sub}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Breakdown card (count par bucket)
// =============================================================================
function BreakdownCard({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: "healthy" | "warning" | "danger" | "info" | "neutral";
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
    info: {
      border: "border-argos-info/30",
      bg: "bg-argos-info/5",
      fg: "text-argos-info",
    },
    neutral: {
      border: "border-argos-border-subtle",
      bg: "bg-argos-surface",
      fg: "text-argos-fg-tertiary",
    },
  };
  const p = palette[tone];
  return (
    <div className={`rounded-md border ${p.border} ${p.bg} px-3 py-2`}>
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </div>
      <div className={`mt-0.5 text-xl font-mono font-medium ${p.fg}`}>{count}</div>
    </div>
  );
}

// =============================================================================
// Section header
// =============================================================================
function SectionHeader({
  title,
  icon: Icon,
  subtitle,
}: {
  title: string;
  icon: typeof Banknote;
  subtitle?: string;
}) {
  return (
    <div className="flex items-baseline gap-2 mb-3 flex-wrap">
      <Icon size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
      <h2 className="text-sm font-semibold text-argos-fg">{title}</h2>
      {subtitle && (
        <span className="font-mono text-[10px] text-argos-fg-tertiary">{subtitle}</span>
      )}
    </div>
  );
}

// Le badge n'est pas utilisé pour l'instant mais on garde l'import pour
// l'usage futur si on rajoute des chips de filtre.
void Badge;
