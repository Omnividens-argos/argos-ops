import {
  Activity,
  Archive,
  Banknote,
  BookOpen,
  Command,
  GraduationCap,
  HeartPulse,
  HelpCircle,
  Inbox,
  Keyboard,
  Layers,
  LayoutDashboard,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { View } from "../App";
import { useDensityClasses, useUserPrefs } from "../hooks/useUserPrefs";

interface NavItem {
  id: View;
  label: string;
  shortcut: string;
  icon: LucideIcon;
  tooltip?: string;
}

// Ordre = pyramide d'action quotidienne :
//   1. Today    — point d'entrée matin
//   2. Inbox    — drafts à valider (action quotidienne)
//   3. Catalogue— flotte, config & inspection
//   4. Cash     — santé business
//   5. Health   — santé technique + compliance (absorbe Breakers)
//   6. Runs     — historique d'exécution
//   7. Help     — glossaire + cheatsheet (footer)
const ITEMS: NavItem[] = [
  {
    id: "today",
    label: "Aujourd'hui",
    shortcut: "1",
    icon: LayoutDashboard,
    tooltip: "Ce qui demande ton attention maintenant — alertes + drafts à valider.",
  },
  {
    id: "inbox",
    label: "Inbox",
    shortcut: "2",
    icon: Inbox,
    tooltip:
      "File unifiée des drafts produits par les bots (emails, posts, devis, contrats, briefs) en attente de validation humaine.",
  },
  {
    id: "agents",
    label: "Catalogue",
    shortcut: "3",
    icon: Activity,
    tooltip:
      "79 bots × 12 services. Toggle, pause, configure et ouvre la page détail de chaque agent.",
  },
  {
    id: "cash",
    label: "Cash & Clients",
    shortcut: "4",
    icon: Banknote,
    tooltip:
      "MRR / ARR, abonnements Stripe, leads inbound, tickets ouverts. La santé business d'Argos.",
  },
  {
    id: "health",
    label: "Health & Compliance",
    shortcut: "5",
    icon: HeartPulse,
    tooltip:
      "Santé technique (DB, runs, agents), disjoncteurs (breakers), conformité AI Act / RGPD / Bloctel.",
  },
  {
    id: "runs",
    label: "Runs",
    shortcut: "6",
    icon: Layers,
    tooltip: "Historique chronologique de toutes les exécutions agents (succès / erreur / killed).",
  },
  {
    id: "outputs",
    label: "Outputs",
    shortcut: "7",
    icon: Archive,
    tooltip:
      "Bibliothèque consultable de tout ce que les bots ont produit (drafts en cours + validés + rejetés + posted). Recherche fulltext.",
  },
];

interface Props {
  current: View;
  onChange: (view: View) => void;
  onOpenPalette: () => void;
  onOpenShortcuts: () => void;
}

export function Sidebar({
  current,
  onChange,
  onOpenPalette,
  onOpenShortcuts,
}: Props) {
  const { mode, setMode, density, setDensity } = useUserPrefs();
  const { navPaddingY } = useDensityClasses();

  return (
    <aside className="hidden md:flex w-56 shrink-0 border-r border-argos-border-subtle bg-argos-surface flex-col theme-transition overflow-y-auto">
      <div className="px-5 py-5 border-b border-argos-border-subtle">
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-argos-healthy" />
          <div className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
            Argos Ops
          </div>
        </div>
        <div className="mt-1 text-sm font-semibold text-argos-fg">Cockpit</div>
      </div>

      {/* Command palette button */}
      <div className="px-2 pt-3 pb-2 border-b border-argos-border-subtle">
        <button
          type="button"
          onClick={onOpenPalette}
          className="w-full flex items-center justify-between gap-2 px-3 py-1.5 rounded-md border border-argos-border-subtle bg-argos-bg/40 text-argos-fg-tertiary hover:text-argos-fg hover:border-argos-border transition-colors group"
          title="Ouvrir la palette de commandes (Ctrl+K)"
        >
          <span className="flex items-center gap-2 text-xs">
            <Command size={12} strokeWidth={2} />
            <span>Chercher / agir…</span>
          </span>
          <kbd className="font-mono text-[10px] border border-argos-border-subtle rounded px-1.5 py-0.5 group-hover:border-argos-border transition-colors">
            ⌘K
          </kbd>
        </button>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {ITEMS.map((item) => {
          const active = item.id === current;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`group w-full flex items-center justify-between px-3 ${navPaddingY} rounded-md text-sm transition-colors ${
                active
                  ? "bg-argos-surface-2 text-argos-fg"
                  : "text-argos-fg-secondary hover:bg-argos-surface-2/60 hover:text-argos-fg"
              }`}
              title={item.tooltip}
            >
              <span className="flex items-center gap-2.5">
                <Icon size={14} strokeWidth={2} className="shrink-0" />
                {item.label}
                {item.tooltip && (
                  <HelpCircle
                    size={11}
                    strokeWidth={2}
                    className="text-argos-fg-tertiary opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label={item.tooltip}
                  />
                )}
              </span>
              <kbd className="font-mono text-[10px] text-argos-fg-tertiary border border-argos-border-subtle rounded px-1.5 py-0.5">
                {item.shortcut}
              </kbd>
            </button>
          );
        })}

        {/* Help (footer-style mais cliquable comme une vue) */}
        <div className="pt-2 mt-2 border-t border-argos-border-subtle space-y-0.5">
          <button
            type="button"
            onClick={() => onChange("help")}
            className={`group w-full flex items-center justify-between px-3 ${navPaddingY} rounded-md text-sm transition-colors ${
              current === "help"
                ? "bg-argos-surface-2 text-argos-fg"
                : "text-argos-fg-secondary hover:bg-argos-surface-2/60 hover:text-argos-fg"
            }`}
            title="Glossaire technique + raccourcis + relance onboarding"
          >
            <span className="flex items-center gap-2.5">
              <BookOpen size={14} strokeWidth={2} className="shrink-0" />
              Aide & glossaire
            </span>
            <kbd className="font-mono text-[10px] text-argos-fg-tertiary border border-argos-border-subtle rounded px-1.5 py-0.5">
              8
            </kbd>
          </button>
          <button
            type="button"
            onClick={onOpenShortcuts}
            className={`group w-full flex items-center justify-between px-3 ${navPaddingY} rounded-md text-sm transition-colors text-argos-fg-secondary hover:bg-argos-surface-2/60 hover:text-argos-fg`}
            title="Cheatsheet raccourcis clavier (Shift + /)"
          >
            <span className="flex items-center gap-2.5">
              <Keyboard size={14} strokeWidth={2} className="shrink-0" />
              Raccourcis
            </span>
            <kbd className="font-mono text-[10px] text-argos-fg-tertiary border border-argos-border-subtle rounded px-1.5 py-0.5">
              ?
            </kbd>
          </button>
        </div>
      </nav>

      {/* Density toggle */}
      <div className="border-t border-argos-border-subtle px-2 py-2">
        <div className="px-1 mb-1 font-mono text-[9px] uppercase tracking-widest text-argos-fg-tertiary">
          Densité
        </div>
        <div
          className="grid grid-cols-2 gap-1 p-0.5 rounded-md bg-argos-bg/40 border border-argos-border-subtle"
          role="radiogroup"
          aria-label="Densité d'affichage"
        >
          <button
            type="button"
            role="radio"
            aria-checked={density === "comfortable"}
            onClick={() => setDensity("comfortable")}
            className={`flex items-center justify-center py-1 rounded font-mono text-[10px] transition-colors ${
              density === "comfortable"
                ? "bg-argos-info/15 text-argos-info"
                : "text-argos-fg-tertiary hover:text-argos-fg"
            }`}
            title="Confortable — espacement aéré (lecture détendue)"
          >
            Confort.
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={density === "compact"}
            onClick={() => setDensity("compact")}
            className={`flex items-center justify-center py-1 rounded font-mono text-[10px] transition-colors ${
              density === "compact"
                ? "bg-argos-info/15 text-argos-info"
                : "text-argos-fg-tertiary hover:text-argos-fg"
            }`}
            title="Compact — plus d'items à l'écran, espacement serré"
          >
            Compact
          </button>
        </div>
      </div>

      {/* Mode toggle (débutant / expert) */}
      <div className="border-t border-argos-border-subtle px-2 py-2">
        <div className="px-1 mb-1 font-mono text-[9px] uppercase tracking-widest text-argos-fg-tertiary">
          Mode interface
        </div>
        <div
          className="grid grid-cols-2 gap-1 p-0.5 rounded-md bg-argos-bg/40 border border-argos-border-subtle"
          role="radiogroup"
          aria-label="Mode interface"
        >
          <button
            type="button"
            role="radio"
            aria-checked={mode === "beginner"}
            onClick={() => setMode("beginner")}
            className={`flex items-center justify-center gap-1 py-1 rounded font-mono text-[10px] transition-colors ${
              mode === "beginner"
                ? "bg-argos-info/15 text-argos-info"
                : "text-argos-fg-tertiary hover:text-argos-fg"
            }`}
            title="Mode débutant — masque les options avancées"
          >
            <GraduationCap size={11} strokeWidth={2} />
            Débutant
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === "expert"}
            onClick={() => setMode("expert")}
            className={`flex items-center justify-center gap-1 py-1 rounded font-mono text-[10px] transition-colors ${
              mode === "expert"
                ? "bg-argos-info/15 text-argos-info"
                : "text-argos-fg-tertiary hover:text-argos-fg"
            }`}
            title="Mode expert — déplie toutes les options"
          >
            <Wrench size={11} strokeWidth={2} />
            Expert
          </button>
        </div>
      </div>

      <div className="border-t border-argos-border-subtle px-5 py-2 font-mono text-[10px] text-argos-fg-tertiary leading-relaxed">
        <kbd className="border border-argos-border-subtle rounded px-1 py-0.5">H</kbd>{" "}
        ré-ouvre le tour
      </div>
    </aside>
  );
}
