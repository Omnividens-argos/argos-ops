import { useCallback, useEffect, useState } from "react";
import { fetchHealth, fetchKPIs } from "./api";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { usePolling } from "./hooks/usePolling";
import { AgentDetail } from "./views/AgentDetail";
import { Agents } from "./views/Agents";
import { Breakers } from "./views/Breakers";
import { Overview } from "./views/Overview";
import { Runs } from "./views/Runs";

export type View = "overview" | "agents" | "runs" | "breakers" | "agent-detail";

export function App() {
  const [view, setView] = useState<View>("overview");
  // ``detailAgent`` est settable depuis la vue Agents (click sur une card).
  // On garde la sidebar « Agents » highlightée quand on est sur le détail
  // pour que l'utilisateur ne se sente pas perdu (cf. P16.C).
  const [detailAgent, setDetailAgent] = useState<string | null>(null);

  // Health + KPIs polling au niveau App pour partager les compteurs globaux
  // (Postgres status dans la topbar + breakers tripped) entre toutes les vues
  // sans dupliquer les requêtes.
  const health = usePolling(useCallback((s) => fetchHealth(s), []));
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));

  const navigateToAgent = useCallback((name: string) => {
    setDetailAgent(name);
    setView("agent-detail");
  }, []);

  const navigateBackToAgents = useCallback(() => {
    setDetailAgent(null);
    setView("agents");
  }, []);

  const handleSidebarChange = useCallback((next: View) => {
    if (next !== "agent-detail") setDetailAgent(null);
    setView(next);
  }, []);

  // Raccourcis 1/2/3/4 pour switcher rapidement entre les vues (style Linear).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      if (e.key === "1") handleSidebarChange("overview");
      if (e.key === "2") handleSidebarChange("agents");
      if (e.key === "3") handleSidebarChange("runs");
      if (e.key === "4") handleSidebarChange("breakers");
      if (e.key === "Escape" && view === "agent-detail") navigateBackToAgents();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleSidebarChange, navigateBackToAgents, view]);

  // La sidebar highlight "agents" quand on est sur le détail d'un agent.
  const sidebarHighlight: View = view === "agent-detail" ? "agents" : view;

  return (
    <div className="h-screen flex bg-argos-bg text-argos-fg">
      <Sidebar current={sidebarHighlight} onChange={handleSidebarChange} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          health={health.data}
          lastRefreshedAt={kpis.lastRefreshedAt}
          trippedBreakers={kpis.data?.tripped_breakers ?? 0}
        />
        <main className="flex-1 overflow-y-auto">
          {view === "overview" && <Overview />}
          {view === "agents" && <Agents onOpenAgent={navigateToAgent} />}
          {view === "runs" && <Runs />}
          {view === "breakers" && <Breakers />}
          {view === "agent-detail" && detailAgent && (
            <AgentDetail agentKey={detailAgent} onBack={navigateBackToAgents} />
          )}
        </main>
      </div>
    </div>
  );
}
