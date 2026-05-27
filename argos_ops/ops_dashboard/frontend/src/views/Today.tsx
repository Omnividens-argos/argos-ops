import {
  AlertOctagon,
  ArrowRight,
  Inbox,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useMemo } from "react";
import type { View } from "../App";
import type { AgentRunRow, AgentSummary } from "../api";
import { fetchAgents, fetchKPIs, fetchRuns } from "../api";
import { EmptyState } from "../components/EmptyState";
import { Heatmap } from "../components/Heatmap";
import { Sparkline } from "../components/Sparkline";
import { TooltipIcon } from "../components/Tooltip";
import { usePolling } from "../hooks/usePolling";
import { formatEur } from "../lib/format";

// Vue Today — page d'accueil débutant. Hiérarchie :
//   1. Greeting (humain, heure, état général d'un coup d'œil)
//   2. Actions (ce qui demande l'attention DU FONDATEUR, ranked par urgence)
//   3. KPIs (les 4 chiffres business clés, pas plus)
//   4. Activité (sparkline 7j + heatmap 12h compactes)
//
// Remplace Overview (devient `Trends` plus tard en Phase 3). Tout est
// branché sur les mêmes endpoints existants — pas d'API nouvelle requise.

interface TodayProps {
  onNavigate: (view: View) => void;
  onOpenBot: (name: string) => void;
}

export function Today({ onNavigate, onOpenBot }: TodayProps) {
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));
  const agents = usePolling(useCallback((s) => fetchAgents(s), []));
  const runs = usePolling(useCallback((s) => fetchRuns(200, s), []));

  const aggregates = useMemo(() => computeAggregates(runs.data ?? []), [runs.data]);
  const actionItems = useMemo(
    () => buildActionItems(agents.data ?? [], aggregates),
    [agents.data, aggregates],
  );

  const greeting = useMemo(buildGreeting, []);
  const allClear =
    actionItems.length === 0 && agents.data !== null && runs.data !== null;

  return (
    <div className="argos-fade-in p-6 max-w-6xl mx-auto space-y-6 theme-transition">
      {/* === Greeting === */}
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-argos-fg">{greeting}</h1>
        <p className="text-sm text-argos-fg-secondary">
          {allClear
            ? "Ta flotte tourne sans incident. Pas d'action urgente, profite."
            : `${actionItems.length} chose${actionItems.length > 1 ? "s" : ""} demande${actionItems.length > 1 ? "nt" : ""} ton attention.`}
        </p>
      </header>

      {/* === Action items === */}
      <section className="space-y-2">
        <h2 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          À traiter
        </h2>
        {actionItems.length === 0 ? (
          <EmptyState
            tone="celebrate"
            icon={Sparkles}
            title="Rien à traiter — bravo ✨"
            body="Pas d'agent en erreur, pas de breaker déclenché, pas de draft en attente. Tu peux fermer cet onglet sans culpabiliser."
            compact
          />
        ) : (
          <ul className="space-y-2">
            {actionItems.map((item) => (
              <ActionItemRow
                key={item.id}
                item={item}
                onNavigate={onNavigate}
                onOpenBot={onOpenBot}
              />
            ))}
          </ul>
        )}
      </section>

      {/* === KPIs principaux === */}
      <section className="space-y-2">
        <h2 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Chiffres clés
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KpiCard
            label="MRR"
            tooltipTerm="MRR"
            value={kpis.data ? formatEur(kpis.data.mrr_eur) : "—"}
          />
          <KpiCard
            label="Abonnements"
            value={kpis.data ? `${kpis.data.active_subscriptions}` : "—"}
          />
          <KpiCard
            label="Leads 24 h"
            value={kpis.data ? `${kpis.data.leads_last_24h}` : "—"}
          />
          <KpiCard
            label="Tickets ouverts"
            value={kpis.data ? `${kpis.data.open_tickets}` : "—"}
            alert={kpis.data ? kpis.data.open_tickets > 5 : false}
          />
        </div>
      </section>

      {/* === Activité === */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <ActivityPanel
          title="12 dernières heures"
          right={`${aggregates.runsLast12h} runs · ${aggregates.failedLast12h} échec(s)`}
        >
          <Heatmap cells={aggregates.heatmapCells} />
          <div className="flex items-center justify-between mt-1.5 font-mono text-[10px] text-argos-fg-tertiary">
            <span>-12 h</span>
            <span>-6 h</span>
            <span>maintenant</span>
          </div>
        </ActivityPanel>
        <ActivityPanel
          title="7 derniers jours"
          right={`${aggregates.runsLast7d} runs au total`}
        >
          <Sparkline
            values={aggregates.dailyCounts}
            width={520}
            height={48}
            colorClass="text-argos-info"
          />
          <div className="flex items-center justify-between mt-1.5 font-mono text-[10px] text-argos-fg-tertiary">
            <span>J-6</span>
            <span>J-3</span>
            <span>aujourd'hui</span>
          </div>
        </ActivityPanel>
      </section>

      {/* === Footer quick links === */}
      <footer className="pt-2 border-t border-argos-border-subtle flex items-center justify-between font-mono text-[10px] text-argos-fg-tertiary">
        <span>
          Astuce :{" "}
          <kbd className="border border-argos-border-subtle rounded px-1 py-0.5">
            Ctrl + K
          </kbd>{" "}
          ouvre la palette de commandes.
        </span>
        <button
          type="button"
          onClick={() => onNavigate("agents")}
          className="hover:text-argos-fg transition-colors"
        >
          Voir la flotte complète →
        </button>
      </footer>
    </div>
  );
}

// =============================================================================
// Greeting selon l'heure
// =============================================================================
function buildGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return "On veille tard 🌙";
  if (hour < 12) return "Bonjour ☀️";
  if (hour < 18) return "Bon après-midi";
  if (hour < 22) return "Bonsoir";
  return "Encore là ?";
}

// =============================================================================
// Action items — ranking d'urgence
// =============================================================================
type ActionTone = "danger" | "warning" | "info" | "neutral";

interface ActionItem {
  id: string;
  tone: ActionTone;
  icon: LucideIcon;
  title: string;
  body?: string;
  cta: string;
  action: (cb: {
    onNavigate: (view: View) => void;
    onOpenBot: (name: string) => void;
  }) => void;
}

function buildActionItems(
  agents: AgentSummary[],
  aggregates: ReturnType<typeof computeAggregates>,
): ActionItem[] {
  const out: ActionItem[] = [];

  const tripped = agents.filter((a) => a.breaker_tripped);
  if (tripped.length > 0) {
    out.push({
      id: "tripped",
      tone: "danger",
      icon: AlertOctagon,
      title: `${tripped.length} disjoncteur${tripped.length > 1 ? "s" : ""} déclenché${tripped.length > 1 ? "s" : ""}`,
      body: tripped
        .slice(0, 3)
        .map((a) => a.name)
        .join(" · "),
      cta: "Voir Health & Compliance",
      action: ({ onNavigate }) => onNavigate("health"),
    });
  }

  const failed = agents.filter((a) => a.last_run_status === "failed" && !a.breaker_tripped);
  if (failed.length > 0) {
    const first = failed[0];
    out.push({
      id: "failed",
      tone: "warning",
      icon: Zap,
      title: `${failed.length} agent${failed.length > 1 ? "s" : ""} en erreur au dernier run`,
      body: failed
        .slice(0, 3)
        .map((a) => a.name)
        .join(" · "),
      cta:
        failed.length === 1
          ? `Ouvrir ${first.name}`
          : "Voir le catalogue",
      action: ({ onNavigate, onOpenBot }) => {
        if (failed.length === 1) onOpenBot(first.name);
        else onNavigate("agents");
      },
    });
  }

  // Drafts à valider (placeholder — quand l'API Inbox sera live, on lira le count ici).
  // Pour l'instant on affiche un point d'entrée stable vers /inbox quoi qu'il arrive.
  if (aggregates.runsToday > 0) {
    // Heuristique simple : si des bots ont tourné aujourd'hui, il y a possiblement des drafts.
    // L'Inbox elle-même affichera ses propres compteurs.
    out.push({
      id: "inbox",
      tone: "info",
      icon: Inbox,
      title: "Drafts en attente de validation",
      body: "Emails outbound, posts sociaux, devis, contrats, briefs SEO. À toi de valider ou ajuster.",
      cta: "Ouvrir l'Inbox",
      action: ({ onNavigate }) => onNavigate("inbox"),
    });
  }

  return out;
}

function ActionItemRow({
  item,
  onNavigate,
  onOpenBot,
}: {
  item: ActionItem;
  onNavigate: (view: View) => void;
  onOpenBot: (name: string) => void;
}) {
  const Icon = item.icon;
  const palette: Record<ActionTone, { border: string; bg: string; fg: string }> = {
    danger: {
      border: "border-argos-danger/40",
      bg: "bg-argos-danger/5",
      fg: "text-argos-danger",
    },
    warning: {
      border: "border-argos-warning/40",
      bg: "bg-argos-warning/5",
      fg: "text-argos-warning",
    },
    info: {
      border: "border-argos-info/40",
      bg: "bg-argos-info/5",
      fg: "text-argos-info",
    },
    neutral: {
      border: "border-argos-border-subtle",
      bg: "bg-argos-surface",
      fg: "text-argos-fg-tertiary",
    },
  };
  const p = palette[item.tone];

  return (
    <li>
      <button
        type="button"
        onClick={() => item.action({ onNavigate, onOpenBot })}
        className={`group w-full text-left rounded-md border ${p.border} ${p.bg} px-4 py-3 flex items-start gap-3 hover:border-argos-border transition-colors`}
      >
        <Icon size={18} strokeWidth={2} className={`shrink-0 mt-0.5 ${p.fg}`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-argos-fg">{item.title}</div>
          {item.body && (
            <div className="font-mono text-[11px] text-argos-fg-secondary mt-0.5 truncate">
              {item.body}
            </div>
          )}
        </div>
        <span className={`font-mono text-[11px] flex items-center gap-1 ${p.fg} shrink-0 group-hover:translate-x-0.5 transition-transform`}>
          {item.cta}
          <ArrowRight size={12} strokeWidth={2} />
        </span>
      </button>
    </li>
  );
}

// =============================================================================
// KPI Card
// =============================================================================
interface KpiCardProps {
  label: string;
  value: string;
  tooltipTerm?: string;
  alert?: boolean;
}

function KpiCard({ label, value, tooltipTerm, alert }: KpiCardProps) {
  return (
    <div
      className={`rounded-md border bg-argos-surface px-4 py-3 ${
        alert ? "border-argos-danger/40 bg-argos-danger/5" : "border-argos-border-subtle"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1">
          {label}
          {tooltipTerm && <TooltipIcon term={tooltipTerm} />}
        </div>
      </div>
      <div
        className={`mt-1 text-xl font-mono font-medium ${
          alert ? "text-argos-danger" : "text-argos-fg"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

// =============================================================================
// Activity panel
// =============================================================================
function ActivityPanel({
  title,
  right,
  children,
}: {
  title: string;
  right: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1.5">
          <TrendingUp size={11} strokeWidth={2} />
          {title}
        </h3>
        <span className="font-mono text-[10px] text-argos-fg-tertiary">{right}</span>
      </div>
      {children}
    </div>
  );
}

// =============================================================================
// Agrégations
// =============================================================================
function computeAggregates(runs: AgentRunRow[]) {
  const now = new Date();
  const midnight = new Date(now);
  midnight.setHours(0, 0, 0, 0);

  const today = runs.filter((r) => new Date(r.started_at) >= midnight);
  const runsToday = today.length;
  const failedToday = today.filter((r) => r.status === "failed").length;

  const heatmapCells: { label: string; count: number; failed: number }[] = [];
  for (let i = 11; i >= 0; i--) {
    const cellEnd = new Date(now.getTime() - i * 60 * 60 * 1000);
    const cellStart = new Date(cellEnd.getTime() - 60 * 60 * 1000);
    const inCell = runs.filter((r) => {
      const t = new Date(r.started_at);
      return t >= cellStart && t < cellEnd;
    });
    heatmapCells.push({
      label: `${cellStart.getHours()}h-${cellEnd.getHours()}h`,
      count: inCell.length,
      failed: inCell.filter((r) => r.status === "failed").length,
    });
  }
  const runsLast12h = heatmapCells.reduce((s, c) => s + c.count, 0);
  const failedLast12h = heatmapCells.reduce((s, c) => s + c.failed, 0);

  const dailyCounts: number[] = [];
  for (let i = 6; i >= 0; i--) {
    const dayStart = new Date(midnight);
    dayStart.setDate(dayStart.getDate() - i);
    const dayEnd = new Date(dayStart);
    dayEnd.setDate(dayEnd.getDate() + 1);
    const inDay = runs.filter((r) => {
      const t = new Date(r.started_at);
      return t >= dayStart && t < dayEnd;
    });
    dailyCounts.push(inDay.length);
  }
  const runsLast7d = dailyCounts.reduce((s, c) => s + c, 0);

  return {
    runsToday,
    failedToday,
    runsLast12h,
    failedLast12h,
    runsLast7d,
    heatmapCells,
    dailyCounts,
  };
}

