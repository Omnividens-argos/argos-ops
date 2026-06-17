// Shell du cockpit archi v2 : rail de navigation des 8 pôles + zone de contenu
// rendant la page du pôle actif. Réutilise le thème (index.css) et les
// primitives UI du dashboard existant. Routing par état local (pas de router) —
// même approche que App.tsx legacy.

import { useState } from "react";
import { PolePage } from "./PolePage.tsx";
import { POLES } from "./poles.ts";

export function PolesShell() {
  const [activeId, setActiveId] = useState<string>(POLES[0].id);
  const active = POLES.find((p) => p.id === activeId) ?? POLES[0];

  return (
    <div className="flex min-h-screen bg-argos-bg text-argos-fg">
      {/* Rail des 8 onglets pôles */}
      <nav className="flex w-56 shrink-0 flex-col border-r border-argos-border-subtle bg-argos-surface">
        <div className="border-b border-argos-border-subtle px-4 py-4">
          <div className="font-mono text-sm font-medium text-argos-fg">Argos Ops</div>
          <div className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Pôles · archi v2
          </div>
        </div>
        <ul className="flex flex-1 flex-col gap-0.5 p-2">
          {POLES.map((p) => {
            const isActive = p.id === active.id;
            return (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setActiveId(p.id)}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left font-mono text-xs transition-colors ${
                    isActive
                      ? "bg-argos-info/15 text-argos-info"
                      : "text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg"
                  }`}
                >
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded text-[10px] ${
                      isActive
                        ? "bg-argos-info/25 text-argos-info"
                        : "bg-argos-surface-2 text-argos-fg-tertiary"
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
        <div className="border-t border-argos-border-subtle px-4 py-3 font-mono text-[10px] text-argos-fg-disabled">
          8 pôles · socle S0
        </div>
      </nav>

      {/* Contenu du pôle actif */}
      <main className="flex-1 overflow-y-auto px-6 py-6">
        <PolePage pole={active} />
      </main>
    </div>
  );
}
