// Tabs partagé du cockpit (refonte SF). Remplace les ~8 switch d'onglets
// hand-rollés (SrePage, MemoirePage, FinancePage, DirectionPage, PubPage,
// MarketingPage, VentePage, BotDetail). Accessible : role=tablist, navigation
// flèches ←/→/Home/End (activation automatique), aria-selected, focus ring.
// Cf. docs/UI_DECISIONS.md §6.

import type { KeyboardEvent, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export interface TabItem {
  id: string;
  label: string;
  icon?: LucideIcon;
  /** Pastille optionnelle (compteur, alerte) rendue à droite du label. */
  badge?: ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  /** Libellé du tablist pour les lecteurs d'écran. */
  ariaLabel?: string;
  className?: string;
}

export function Tabs({ tabs, active, onChange, ariaLabel, className }: TabsProps) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const idx = tabs.findIndex((t) => t.id === active);
    if (idx < 0) return;
    let next = idx;
    if (event.key === "ArrowRight") next = (idx + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    onChange(tabs[next].id);
  }

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={`flex flex-wrap items-center gap-1 border-b border-argos-border-subtle ${className ?? ""}`}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={`-mb-px flex items-center gap-2 rounded-t-md border-b-2 px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg ${
              isActive
                ? "border-argos-info text-argos-fg"
                : "border-transparent text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg"
            }`}
          >
            {Icon ? <Icon size={14} aria-hidden /> : null}
            <span>{tab.label}</span>
            {tab.badge != null ? <span className="ml-0.5">{tab.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

/** Panneau associé à un onglet (relie aria-labelledby / id pour l'a11y). */
export function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div role="tabpanel" id={`tabpanel-${id}`} aria-labelledby={`tab-${id}`} tabIndex={0} className="focus-visible:outline-none">
      {children}
    </div>
  );
}
