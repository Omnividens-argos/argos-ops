// Shell unifié du cockpit Argos Ops (refonte SF, Phase 2b). UNE seule app :
// Home global + 8 pôles + outils globaux migrés du legacy (Inbox, Outputs,
// Atelier, Aide) + overlay BotDetail (surface de contrôle agent, via ⌘K).
// Routing par état (pas de react-router). Remplace App.tsx + PolesShell.

import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Home as HomeIcon, Loader2, Menu } from "lucide-react";
import { fetchHealth, fetchKPIs, runAgentNow } from "./api";
import { CommandPalette } from "./components/CommandPalette";
import { KeyboardShortcutsModal } from "./components/KeyboardShortcutsModal";
import { OnboardingTour } from "./components/OnboardingTour";
import { Topbar } from "./components/Topbar";
import { usePolling } from "./hooks/usePolling";
import { RUNNABLE_AGENTS } from "./lib/runnableAgents";
import { PolePage } from "./poles/PolePage.tsx";
import { POLES } from "./poles/poles.ts";
import { TOOLS } from "./routes.ts";
import type { Route } from "./routes.ts";
import { useChangeStream } from "./lib/useChangeStream.ts";
import type { ChangeStreamStatus } from "./lib/useChangeStream.ts";

// Code-split : les vues lourdes (Home/charts, Atelier WS, BotDetail, Inbox,
// Outputs, Aide) ne sont tirées qu'à l'ouverture.
const Home = lazy(() => import("./Home").then((m) => ({ default: m.Home })));
const Atelier = lazy(() => import("./views/Atelier").then((m) => ({ default: m.Atelier })));
const BotDetail = lazy(() => import("./views/BotDetail").then((m) => ({ default: m.BotDetail })));
const Help = lazy(() => import("./views/Help").then((m) => ({ default: m.Help })));
const Inbox = lazy(() => import("./views/Inbox").then((m) => ({ default: m.Inbox })));
const Outputs = lazy(() => import("./views/Outputs").then((m) => ({ default: m.Outputs })));

function RailNav({
  route,
  onNavigate,
  live,
}: {
  route: Route;
  onNavigate: (r: Route) => void;
  live: ChangeStreamStatus;
}) {
  const liveDot =
    live === "open" ? "bg-argos-healthy" : live === "connecting" ? "bg-argos-warning" : "bg-argos-fg-disabled";
  const liveLabel = live === "open" ? "Temps réel" : live === "connecting" ? "Connexion…" : "Hors-ligne (polling)";
  const itemBase =
    "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-1 focus-visible:ring-offset-argos-surface";
  const active = "bg-argos-info/15 text-argos-info";
  const idle = "text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg";

  return (
    <>
      <div className="border-b border-argos-border-subtle px-4 py-4">
        <div className="font-mono text-sm font-medium text-argos-fg">Argos Ops</div>
        <div className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Cockpit · archi v2
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-2">
        <ul className="flex flex-col gap-0.5">
          <li>
            <button
              type="button"
              onClick={() => onNavigate({ kind: "home" })}
              aria-current={route.kind === "home" ? "page" : undefined}
              className={`${itemBase} ${route.kind === "home" ? active : idle}`}
            >
              <HomeIcon size={16} aria-hidden />
              <span>Accueil</span>
            </button>
          </li>
        </ul>

        <div>
          <div className="px-2.5 pb-1 font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
            Pôles
          </div>
          <ul className="flex flex-col gap-0.5">
            {POLES.map((p) => {
              const isActive = route.kind === "pole" && route.id === p.id;
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => onNavigate({ kind: "pole", id: p.id })}
                    aria-current={isActive ? "page" : undefined}
                    className={`${itemBase} ${isActive ? active : idle}`}
                  >
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded font-mono text-[10px] ${
                        isActive ? "bg-argos-info/25 text-argos-info" : "bg-argos-surface-2 text-argos-fg-tertiary"
                      }`}
                    >
                      {p.num}
                    </span>
                    <span className="truncate">{p.name}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <div className="px-2.5 pb-1 font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
            Outils globaux
          </div>
          <ul className="flex flex-col gap-0.5">
            {TOOLS.map((t) => {
              const isActive = route.kind === "tool" && route.id === t.id;
              const Icon = t.icon;
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => onNavigate({ kind: "tool", id: t.id })}
                    aria-current={isActive ? "page" : undefined}
                    className={`${itemBase} ${isActive ? active : idle}`}
                  >
                    <Icon size={16} aria-hidden />
                    <span>{t.name}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-argos-border-subtle px-4 py-3 font-mono text-[10px] text-argos-fg-disabled">
        <span>⌘K · ? raccourcis</span>
        <span className="flex items-center gap-1.5" title={liveLabel}>
          <span className={`size-1.5 rounded-full ${liveDot}`} aria-hidden />
          <span className="sr-only">{liveLabel}</span>
        </span>
      </div>
    </>
  );
}

export function AppShell() {
  const [route, setRoute] = useState<Route>({ kind: "home" });
  const [selectedBot, setSelectedBot] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [forceOnboarding, setForceOnboarding] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Canal temps réel : invalide React Query + redispatch DOM sur changement disque.
  const live = useChangeStream();

  // Health + KPIs polling partagés (status DB topbar + breakers tripped).
  const health = usePolling(useCallback((s) => fetchHealth(s), []));
  const kpis = usePolling(useCallback((s) => fetchKPIs(s), []));

  const navigate = useCallback((next: Route) => {
    setSelectedBot(null);
    setMobileNavOpen(false);
    setRoute(next);
  }, []);

  const openBot = useCallback((name: string) => setSelectedBot(name), []);
  const closeBot = useCallback(() => setSelectedBot(null), []);
  const runBotNow = useCallback(async (name: string) => {
    await runAgentNow(name);
  }, []);

  // Raccourcis clavier globaux.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const inField =
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
        return;
      }
      if (inField) return;

      if (e.key === "Escape") {
        if (paletteOpen) setPaletteOpen(false);
        else if (shortcutsOpen) setShortcutsOpen(false);
        else if (selectedBot) setSelectedBot(null);
        else if (mobileNavOpen) setMobileNavOpen(false);
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        setShortcutsOpen((open) => !open);
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }
      if (e.key === "h" || e.key === "H") {
        if (!paletteOpen && !shortcutsOpen) setForceOnboarding(true);
        return;
      }
      // Nav numérique : 0 = home, 1-8 = pôles.
      if (e.key === "0") navigate({ kind: "home" });
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= POLES.length) {
        navigate({ kind: "pole", id: POLES[n - 1].id });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, paletteOpen, shortcutsOpen, selectedBot, mobileNavOpen]);

  function renderContent() {
    if (selectedBot) {
      return (
        <BotDetail
          botName={selectedBot}
          runnableAgents={RUNNABLE_AGENTS}
          onBack={closeBot}
          onOpenInbox={() => navigate({ kind: "tool", id: "inbox" })}
        />
      );
    }
    if (route.kind === "home") return <Home onNavigate={navigate} />;
    if (route.kind === "pole") {
      const pole = POLES.find((p) => p.id === route.id) ?? POLES[0];
      return (
        <div className="px-6 py-6">
          <PolePage pole={pole} />
        </div>
      );
    }
    // route.kind === "tool"
    if (route.id === "inbox") return <Inbox />;
    if (route.id === "outputs") return <Outputs />;
    if (route.id === "atelier") return <Atelier />;
    return (
      <Help
        onReopenOnboarding={() => setForceOnboarding(true)}
        onOpenShortcuts={() => setShortcutsOpen(true)}
      />
    );
  }

  return (
    <div className="flex h-screen bg-argos-bg text-argos-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[60] focus:rounded-md focus:border focus:border-argos-info focus:bg-argos-surface focus:px-3 focus:py-2 focus:text-sm focus:text-argos-fg"
      >
        Aller au contenu
      </a>
      {/* Rail desktop */}
      <nav
        className="hidden w-60 shrink-0 flex-col border-r border-argos-border-subtle bg-argos-surface lg:flex"
        aria-label="Navigation principale"
      >
        <RailNav route={route} onNavigate={navigate} live={live} />
      </nav>

      {/* Drawer mobile */}
      {mobileNavOpen ? (
        <div className="fixed inset-0 z-30 flex lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-argos-bg/70 backdrop-blur-sm"
            aria-label="Fermer le menu"
            onClick={() => setMobileNavOpen(false)}
          />
          <nav
            className="argos-fade-in relative flex w-64 flex-col border-r border-argos-border bg-argos-surface"
            aria-label="Navigation principale"
          >
            <RailNav route={route} onNavigate={navigate} live={live} />
          </nav>
        </div>
      ) : null}

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Barre mobile (hamburger) */}
        <div className="flex h-12 items-center gap-2 border-b border-argos-border-subtle bg-argos-surface px-3 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Ouvrir le menu"
            className="rounded p-1.5 text-argos-fg-secondary transition-colors hover:bg-argos-surface-2 hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info"
          >
            <Menu size={18} aria-hidden />
          </button>
          <span className="font-mono text-sm font-medium text-argos-fg">Argos Ops</span>
        </div>

        <Topbar
          health={health.data}
          lastRefreshedAt={kpis.lastRefreshedAt}
          trippedBreakers={kpis.data?.tripped_breakers ?? 0}
          onOpenPalette={() => setPaletteOpen(true)}
        />

        <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto focus-visible:outline-none">
          <Suspense
            fallback={
              <div className="flex items-center justify-center py-20 text-argos-fg-tertiary" role="status" aria-live="polite">
                <Loader2 size={18} className="animate-spin motion-reduce:animate-none" aria-hidden />
                <span className="ml-2 text-sm">Chargement…</span>
              </div>
            }
          >
            {renderContent()}
          </Suspense>
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

      <KeyboardShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />

      <OnboardingTour forceOpen={forceOnboarding} onFinish={() => setForceOnboarding(false)} />
    </div>
  );
}
