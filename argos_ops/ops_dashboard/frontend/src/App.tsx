import { useCallback, useEffect, useState } from "react";
import { fetchHealth, fetchKPIs } from "./api";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { usePolling } from "./hooks/usePolling";
import { Agents } from "./views/Agents";
import { Overview } from "./views/Overview";
import { Runs } from "./views/Runs";

export type View = "overview" | "agents" | "runs";

export function App() {
  const [view, setView] = useState<View>("overview");

  // Health + KPIs polling au niveau App pour partager les compteurs globaux
  // (Postgres status dans la topbar + breakers tripped) entre toutes les vues
  // sans dupliquer les requêtes.
  const health = usePolling(useCallback((s) => fetchHealth(s), []));
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));

  // Raccourcis 1/2/3 pour switcher rapidement entre les vues (style Linear).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === "1") setView("overview");
      if (e.key === "2") setView("agents");
      if (e.key === "3") setView("runs");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="h-screen flex bg-argos-bg text-argos-fg">
      <Sidebar current={view} onChange={setView} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          health={health.data}
          lastRefreshedAt={kpis.lastRefreshedAt}
          trippedBreakers={kpis.data?.tripped_breakers ?? 0}
        />
        <main className="flex-1 overflow-y-auto">
          {view === "overview" && <Overview />}
          {view === "agents" && <Agents />}
          {view === "runs" && <Runs />}
        </main>
      </div>
    </div>
  );
}
