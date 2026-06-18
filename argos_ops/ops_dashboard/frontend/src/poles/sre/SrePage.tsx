// Page du pôle SRE & Meta-Ops (archi v2, S8). Aucun agent : 13 scripts en cron
// auto. 5 onglets : Statut temps réel (vert/jaune/rouge + perf + lancer) · Runs
// (historique runlog) · Breakers (+ reset) · Planning (cron + plan orchestrateur)
// · Kill-switch (gel global + par script). Branche le shell poles.html sur
// GET /api/poles/sre/*.

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { type SreOverview, fetchSreOverview } from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { severityTone } from "./lib.ts";
import { StatusBoard } from "./StatusBoard.tsx";
import { RunHistory } from "./RunHistory.tsx";
import { BreakerPanel } from "./BreakerPanel.tsx";
import { CronPlanner } from "./CronPlanner.tsx";
import { KillSwitchPanel } from "./KillSwitchPanel.tsx";

type Tab = "status" | "runs" | "breakers" | "planning" | "killswitch";

const TABS: { id: Tab; label: string }[] = [
  { id: "status", label: "Statut" },
  { id: "runs", label: "Runs" },
  { id: "breakers", label: "Breakers" },
  { id: "planning", label: "Planning" },
  { id: "killswitch", label: "Kill-switch" },
];

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex flex-col">
      <span className={`font-mono text-base font-medium ${tone}`}>{value}</span>
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        {label}
      </span>
    </div>
  );
}

export function SrePage() {
  const [overview, setOverview] = useState<SreOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("status");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchSreOverview(controller.signal)
      .then(setOverview)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);

  function renderTab(): ReactNode {
    if (!overview) return null;
    switch (tab) {
      case "status":
        return <StatusBoard scripts={overview.scripts} onChanged={refresh} />;
      case "runs":
        return (
          <RunHistory
            scripts={overview.scripts.map((s) => s.script)}
            recent={overview.recent_runs}
          />
        );
      case "breakers":
        return <BreakerPanel breakers={overview.breakers} onChanged={refresh} />;
      case "planning":
        return <CronPlanner schedule={overview.schedule} plan={overview.plan} />;
      case "killswitch":
        return (
          <KillSwitchPanel
            killswitch={overview.killswitch}
            scripts={overview.scripts}
            onChanged={refresh}
          />
        );
      default:
        return null;
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 8/8</span>
            <Badge tone="neutral">aucun agent — cron auto</Badge>
            {overview && (
              <Badge tone={severityTone(overview.health)}>flotte {overview.health}</Badge>
            )}
          </div>
          <Button size="sm" variant="ghost" onClick={refresh}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">SRE &amp; Meta-Ops</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">
          Santé de la flotte : watchers, uptime, SSL, DNS, audit deps/secrets/backups, flaky CI,
          dérive de config et générateurs. Déterministe de bout en bout — surveillé en temps réel,
          avec breakers, kill-switch et orchestrateur.
        </p>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat label="scripts" value={overview.counts.scripts_total} tone="text-argos-fg" />
            <Stat label="sains" value={overview.counts.green} tone="text-argos-healthy" />
            <Stat label="jaune" value={overview.counts.yellow} tone="text-argos-warning" />
            <Stat label="rouge" value={overview.counts.red} tone="text-argos-danger" />
            <Stat
              label="breakers armés"
              value={overview.counts.breakers_tripped}
              tone={
                overview.counts.breakers_tripped > 0 ? "text-argos-danger" : "text-argos-fg"
              }
            />
            <Stat
              label="gelés"
              value={overview.counts.frozen}
              tone={overview.counts.frozen > 0 ? "text-argos-warning" : "text-argos-fg"}
            />
            <Stat label="dûs" value={overview.counts.due_now} tone="text-argos-info" />
            <Stat label="runs 24h" value={overview.counts.runs_24h} tone="text-argos-fg" />
          </div>
        )}
      </header>

      <nav className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 font-mono text-xs transition-colors ${
              tab === t.id
                ? "bg-argos-info/15 text-argos-info"
                : "text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {loading && (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-8 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Chargement du statut de la flotte…
        </div>
      )}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {overview && !loading && <div>{renderTab()}</div>}
    </div>
  );
}
