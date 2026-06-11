import { useCallback, useEffect, useState } from "react";
import { fetchHealth, fetchKPIs, runAgentNow } from "./api";
import { CommandPalette } from "./components/CommandPalette";
import { KeyboardShortcutsModal } from "./components/KeyboardShortcutsModal";
import { MobileBottomNav } from "./components/MobileBottomNav";
import { OnboardingTour } from "./components/OnboardingTour";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { usePolling } from "./hooks/usePolling";
import { RUNNABLE_AGENTS } from "./lib/runnableAgents";
import { Agents } from "./views/Agents";
import { Atelier } from "./views/Atelier";
import { BotDetail } from "./views/BotDetail";
import { CashCustomers } from "./views/CashCustomers";
import { HealthCompliance } from "./views/HealthCompliance";
import { Help } from "./views/Help";
import { Inbox } from "./views/Inbox";
import { Memory } from "./views/Memory";
import { Outputs } from "./views/Outputs";
import { Pipeline } from "./views/Pipeline";
import { Runs } from "./views/Runs";
import { ServiceDetail } from "./views/ServiceDetail";
import { Today } from "./views/Today";

// Routes top-level du panel (state-based, pas de react-router).
// `bot:<name>` est un overlay : `selectedBot` non-null prend le dessus.
export type View =
  | "today"
  | "inbox"
  | "agents"
  | "cash"
  | "pipeline"
  | "health"
  | "runs"
  | "outputs"
  | "memory"
  | "atelier"
  | "help";

export function App() {
  const [view, setView] = useState<View>("today");
  const [selectedBot, setSelectedBot] = useState<string | null>(null);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [forceOnboarding, setForceOnboarding] = useState(false);

  // Health + KPIs polling au niveau App pour partager les compteurs globaux
  // (Postgres status dans la topbar + breakers tripped) entre toutes les vues
  // sans dupliquer les requêtes.
  const health = usePolling(useCallback((s) => fetchHealth(s), []));
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));

  // Navigation centralisée — éteint les overlays (bot/service) quand on switch de vue.
  const navigate = useCallback((next: View) => {
    setSelectedBot(null);
    setSelectedService(null);
    setView(next);
  }, []);

  const openBot = useCallback((name: string) => {
    setSelectedService(null);
    setSelectedBot(name);
  }, []);

  const closeBot = useCallback(() => {
    setSelectedBot(null);
  }, []);

  const openService = useCallback((id: string) => {
    setSelectedBot(null);
    setSelectedService(id);
  }, []);

  const closeService = useCallback(() => {
    setSelectedService(null);
  }, []);

  const runBotNow = useCallback(async (name: string) => {
    try {
      await runAgentNow(name);
    } catch (err) {
      console.warn("runAgentNow failed", name, err);
      throw err;
    }
  }, []);

  // Raccourcis clavier globaux :
  //   1-7        = switch view (sans focus dans un input)
  //   ⌘/Ctrl+K   = ouvrir la palette
  //   ?          = ré-ouvre le tour d'onboarding
  //   Shift+/    = cheatsheet raccourcis
  //   esc        = ferme palette / shortcuts / bot detail
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const inField =
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement;

      // Ctrl+K / Cmd+K — toujours actif, même dans un input.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
        return;
      }
      if (inField) return;

      if (e.key === "Escape") {
        if (paletteOpen) {
          setPaletteOpen(false);
        } else if (shortcutsOpen) {
          setShortcutsOpen(false);
        } else if (selectedBot) {
          setSelectedBot(null);
        } else if (selectedService) {
          setSelectedService(null);
        }
        return;
      }
      // `?` (Shift+/) ouvre le cheatsheet raccourcis.
      if (e.key === "?") {
        e.preventDefault();
        setShortcutsOpen((open) => !open);
        return;
      }
      // `/` (slash seul) ouvre la palette — alias Cmd+K (pattern Linear).
      if (e.key === "/") {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }
      // Touche dédiée pour ré-ouvrir le tour d'onboarding (différent du
      // cheatsheet). On utilise « h » pour « help / onboarding ».
      if (e.key === "h" || e.key === "H") {
        if (!paletteOpen && !shortcutsOpen) {
          setForceOnboarding(true);
        }
        return;
      }
      if (e.key === "1") navigate("today");
      if (e.key === "2") navigate("inbox");
      if (e.key === "3") navigate("agents");
      if (e.key === "4") navigate("cash");
      if (e.key === "5") navigate("health");
      if (e.key === "6") navigate("runs");
      if (e.key === "7") navigate("outputs");
      if (e.key === "8") navigate("memory");
      if (e.key === "9") navigate("atelier");
      if (e.key === "0") navigate("help");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, paletteOpen, shortcutsOpen, selectedBot, selectedService]);

  return (
    <div className="h-screen flex bg-argos-bg text-argos-fg">
      <Sidebar
        current={view}
        onChange={navigate}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenShortcuts={() => setShortcutsOpen(true)}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          health={health.data}
          lastRefreshedAt={kpis.lastRefreshedAt}
          trippedBreakers={kpis.data?.tripped_breakers ?? 0}
          onOpenPalette={() => setPaletteOpen(true)}
        />
        <main className="flex-1 overflow-y-auto pb-14 md:pb-0">
          {selectedBot ? (
            <BotDetail
              botName={selectedBot}
              runnableAgents={RUNNABLE_AGENTS}
              onBack={closeBot}
              onOpenInbox={() => navigate("inbox")}
            />
          ) : selectedService ? (
            <ServiceDetail
              serviceId={selectedService}
              onBack={closeService}
              onOpenBot={openBot}
              onOpenInbox={() => navigate("inbox")}
            />
          ) : (
            <>
              {view === "today" && <Today onNavigate={navigate} onOpenBot={openBot} />}
              {view === "inbox" && <Inbox />}
              {view === "agents" && (
                <Agents onOpenBot={openBot} onOpenService={openService} />
              )}
              {view === "cash" && (
                <CashCustomers onOpenPipeline={() => navigate("pipeline")} />
              )}
              {view === "health" && <HealthCompliance />}
              {view === "runs" && <Runs />}
              {view === "outputs" && <Outputs />}
              {view === "memory" && <Memory onOpenBot={openBot} />}
              {view === "atelier" && <Atelier />}
              {view === "pipeline" && <Pipeline onBack={() => navigate("cash")} />}
              {view === "help" && (
                <Help
                  onReopenOnboarding={() => setForceOnboarding(true)}
                  onOpenShortcuts={() => setShortcutsOpen(true)}
                />
              )}
            </>
          )}
        </main>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={navigate}
        onOpenBot={openBot}
        onRunBot={runBotNow}
        runnableAgents={RUNNABLE_AGENTS}
      />

      <KeyboardShortcutsModal
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />

      <OnboardingTour
        forceOpen={forceOnboarding}
        onFinish={() => setForceOnboarding(false)}
      />

      <MobileBottomNav
        current={view}
        onChange={navigate}
        onOpenPalette={() => setPaletteOpen(true)}
      />
    </div>
  );
}
