import {
  AlertTriangle,
  ArrowLeft,
  Clock,
  Crown,
  Frown,
  Kanban,
  Sparkles,
} from "lucide-react";
import { useCallback, useMemo } from "react";
import type { PipelineDeal, PipelineSnapshot } from "../api";
import { fetchPipeline } from "../api";
import { EmptyState } from "../components/EmptyState";
import { Badge, Flash } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatEur, formatRelativeTime } from "../lib/format";

// Vue Pipeline — kanban des deals commerciaux.
// Source : ``data/sales/deals/pipe.yaml`` (maintenu manuellement par le
// fondateur). Read-only — pour éditer un deal, ouvre le YAML dans l'IDE.
//
// 7 colonnes (stages canoniques de DealRiskScorer) :
//   discovery → demo_scheduled → demo_done → proposal_sent
//             → contract_sent → won (succès) / lost (échec)

interface PipelineProps {
  onBack: () => void;
}

const STAGES: { id: string; label: string; tone: "info" | "warning" | "healthy" | "danger" | "neutral" }[] = [
  { id: "discovery", label: "Discovery", tone: "info" },
  { id: "demo_scheduled", label: "Démo programmée", tone: "info" },
  { id: "demo_done", label: "Démo faite", tone: "info" },
  { id: "proposal_sent", label: "Devis envoyé", tone: "warning" },
  { id: "contract_sent", label: "Contrat envoyé", tone: "warning" },
  { id: "won", label: "Gagné", tone: "healthy" },
  { id: "lost", label: "Perdu", tone: "neutral" },
];

const SAMPLE_YAML = `deals:
  - deal_id: "acme-q2-2026"
    company: "Acme SA"
    stage: "demo_done"       # discovery | demo_scheduled | demo_done | proposal_sent | contract_sent | won | lost
    amount_eur: 4200
    last_activity_at: 2026-05-10
    owner: "founder"
    notes: "Marc revient mardi avec son board"

  - deal_id: "globex-q3-2026"
    company: "Globex Inc"
    stage: "proposal_sent"
    amount_eur: 9800
    last_activity_at: 2026-05-15
    owner: "founder"
    notes: "Sarah veut un benchmark vs concurrent X"
`;

export function Pipeline({ onBack }: PipelineProps) {
  const snapshot = usePolling(useCallback((s) => fetchPipeline(s), []), 60000);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-5">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg transition-colors"
      >
        <ArrowLeft size={12} strokeWidth={2} />
        Retour
      </button>

      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-argos-fg flex items-center gap-2">
          <Kanban size={22} strokeWidth={1.5} className="text-argos-info" />
          Pipeline commercial
        </h1>
        <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
          Vue kanban des deals en cours. Source : <code className="font-mono text-[11px]">{snapshot.data?.file_path ?? "data/sales/deals/pipe.yaml"}</code>{" "}
          — édité à la main par toi (lu par DealRiskScorer chaque lundi 9h30).
        </p>
      </header>

      {snapshot.error && (
        <Flash
          variant="error"
          message={`Impossible de charger le pipeline : ${snapshot.error.message}`}
        />
      )}

      {snapshot.data === null && snapshot.error === null && (
        <EmptyState tone="loading" title="Chargement du pipeline…" compact />
      )}

      {snapshot.data && !snapshot.data.has_data && <EmptyPipeline />}

      {snapshot.data?.has_data && <PipelineBoard snapshot={snapshot.data} />}
    </div>
  );
}

// =============================================================================
// Empty state — explique comment créer le YAML
// =============================================================================
function EmptyPipeline() {
  return (
    <div className="space-y-4">
      <EmptyState
        tone="neutral"
        icon={Kanban}
        title="Aucun deal dans le pipeline"
        body="Le fichier data/sales/deals/pipe.yaml est absent ou vide. Crée-le avec le template ci-dessous pour activer le kanban + le scoring DealRiskScorer."
      />
      <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <div className="flex items-baseline justify-between mb-2 flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-argos-fg">Template YAML</h3>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard.writeText(SAMPLE_YAML).catch(() => undefined);
            }}
            className="font-mono text-[10px] text-argos-info hover:underline"
          >
            copier
          </button>
        </div>
        <pre className="font-mono text-[11.5px] text-argos-fg-secondary leading-relaxed whitespace-pre-wrap break-words">
          {SAMPLE_YAML}
        </pre>
      </div>
    </div>
  );
}

// =============================================================================
// Kanban board
// =============================================================================
function PipelineBoard({ snapshot }: { snapshot: PipelineSnapshot }) {
  const byStage = useMemo(() => {
    const map: Record<string, PipelineDeal[]> = {};
    for (const stage of STAGES) map[stage.id] = [];
    for (const deal of snapshot.deals) {
      (map[deal.stage] ?? (map[deal.stage] = [])).push(deal);
    }
    return map;
  }, [snapshot.deals]);

  const stalled = snapshot.deals.filter((d) => d.risk_level === "stalled");
  const atRisk = snapshot.deals.filter((d) => d.risk_level === "at_risk");

  return (
    <>
      {/* Hero summary */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard
          label="Deals en cours"
          value={`${snapshot.deals.filter((d) => !["won", "lost"].includes(d.stage)).length}`}
          tone="info"
        />
        <KpiCard
          label="Pipe value"
          value={formatEur(snapshot.total_amount_eur)}
          tone="healthy"
          sub="sommes des deals non-lost"
        />
        <KpiCard
          label="Stalled (≥14 j)"
          value={`${stalled.length}`}
          tone={stalled.length > 0 ? "danger" : "healthy"}
          icon={AlertTriangle}
        />
        <KpiCard
          label="At risk (≥7 j)"
          value={`${atRisk.length}`}
          tone={atRisk.length > 0 ? "warning" : "healthy"}
          icon={Clock}
        />
      </section>

      {/* Kanban columns */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {STAGES.map((stage) => {
          const deals = byStage[stage.id] ?? [];
          const totalAmount = deals.reduce((s, d) => s + (d.amount_eur ?? 0), 0);
          return (
            <StageColumn
              key={stage.id}
              label={stage.label}
              count={deals.length}
              total={totalAmount}
              deals={deals}
              isWon={stage.id === "won"}
              isLost={stage.id === "lost"}
            />
          );
        })}
      </section>

      <p className="font-mono text-[10px] text-argos-fg-tertiary text-right">
        Snapshot rafraîchi {formatRelativeTime(snapshot.last_refreshed_at)} ·
        poll toutes les 60 s. Édite{" "}
        <code className="font-mono">{snapshot.file_path}</code> pour modifier le pipe.
      </p>
    </>
  );
}

function StageColumn({
  label,
  count,
  total,
  deals,
  isWon,
  isLost,
}: {
  label: string;
  count: number;
  total: number;
  deals: PipelineDeal[];
  isWon: boolean;
  isLost: boolean;
}) {
  return (
    <div className={`rounded-md border bg-argos-surface ${isWon ? "border-argos-healthy/30" : isLost ? "border-argos-border-subtle opacity-60" : "border-argos-border-subtle"}`}>
      <header className="px-3 py-2 border-b border-argos-border-subtle flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-argos-fg flex items-center gap-1.5">
          {isWon && <Crown size={12} strokeWidth={2} className="text-argos-healthy" />}
          {isLost && <Frown size={12} strokeWidth={2} className="text-argos-fg-tertiary" />}
          {label}
        </h3>
        <div className="text-right">
          <div className="font-mono text-xs text-argos-fg">{count}</div>
          {total > 0 && (
            <div className="font-mono text-[10px] text-argos-fg-tertiary">
              {formatEur(total)}
            </div>
          )}
        </div>
      </header>
      <div className="p-2 space-y-2 min-h-[120px]">
        {deals.length === 0 ? (
          <div className="font-mono text-[10px] text-argos-fg-tertiary text-center pt-4">
            Vide
          </div>
        ) : (
          deals.map((d) => <DealCard key={d.deal_id} deal={d} />)
        )}
      </div>
    </div>
  );
}

function DealCard({ deal }: { deal: PipelineDeal }) {
  const riskBorder: Record<PipelineDeal["risk_level"], string> = {
    healthy: "border-argos-border-subtle",
    at_risk: "border-argos-warning/40",
    stalled: "border-argos-danger/40 bg-argos-danger/5",
  };
  return (
    <div
      className={`rounded-md border ${riskBorder[deal.risk_level]} bg-argos-bg/40 px-3 py-2`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="text-sm font-medium text-argos-fg truncate">{deal.company}</div>
        {deal.risk_level === "stalled" && <Badge tone="danger">stalled</Badge>}
        {deal.risk_level === "at_risk" && <Badge tone="warning">at risk</Badge>}
      </div>
      {deal.amount_eur !== null && (
        <div className="font-mono text-[11px] text-argos-fg-secondary">
          {formatEur(deal.amount_eur)}
        </div>
      )}
      <div className="font-mono text-[10px] text-argos-fg-tertiary mt-1">
        {deal.deal_id} · {deal.owner ?? "—"} ·{" "}
        {deal.last_activity_at
          ? formatRelativeTime(deal.last_activity_at)
          : "pas d'activité loggée"}
        {deal.days_since_activity !== null && deal.days_since_activity >= 7 && (
          <> · J+{deal.days_since_activity}</>
        )}
      </div>
      {deal.notes && (
        <div className="mt-1.5 text-[11px] text-argos-fg-secondary line-clamp-2 italic">
          « {deal.notes} »
        </div>
      )}
    </div>
  );
}

// =============================================================================
// KPI card
// =============================================================================
function KpiCard({
  label,
  value,
  tone,
  sub,
  icon: Icon = Sparkles,
}: {
  label: string;
  value: string;
  tone: "healthy" | "warning" | "danger" | "info" | "neutral";
  sub?: string;
  icon?: typeof Sparkles;
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
      fg: "text-argos-fg",
    },
  };
  const p = palette[tone];
  return (
    <div className={`rounded-md border ${p.border} ${p.bg} px-4 py-3`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={12} strokeWidth={2} className="text-argos-fg-tertiary" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {label}
        </span>
      </div>
      <div className={`text-xl font-mono font-medium ${p.fg}`}>{value}</div>
      {sub && (
        <div className="mt-0.5 font-mono text-[10px] text-argos-fg-tertiary truncate">
          {sub}
        </div>
      )}
    </div>
  );
}
