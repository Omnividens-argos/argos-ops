import { Keyboard, X } from "lucide-react";
import { useEffect } from "react";

// Cheatsheet des raccourcis clavier, ouvert via `?` ou `Shift+/`.
// Volontairement statique : la liste vit en dur ici, alignée avec ce qui est
// câblé dans App.tsx::onKey. Si tu ajoutes un raccourci, ajoute-le ici.

interface Shortcut {
  keys: string[];
  label: string;
  context?: string;
}

const SHORTCUTS: { group: string; items: Shortcut[] }[] = [
  {
    group: "Navigation",
    items: [
      { keys: ["1"], label: "Aller à Aujourd'hui" },
      { keys: ["2"], label: "Aller à Inbox" },
      { keys: ["3"], label: "Aller au Catalogue d'agents" },
      { keys: ["4"], label: "Aller à Cash & Clients" },
      { keys: ["5"], label: "Aller à Health & Compliance" },
      { keys: ["6"], label: "Aller à Runs" },
      { keys: ["7"], label: "Aller à Outputs library" },
      { keys: ["8"], label: "Aller à Aide & glossaire" },
    ],
  },
  {
    group: "Actions globales",
    items: [
      {
        keys: ["⌘", "K"],
        label: "Ouvrir la palette de commandes",
        context: "ou Ctrl + K sur Windows / Linux",
      },
      { keys: ["?"], label: "Ré-ouvrir le tour d'onboarding" },
      {
        keys: ["Shift", "/"],
        label: "Ouvrir ce cheatsheet",
      },
      { keys: ["Esc"], label: "Fermer palette / overlay / bot detail" },
    ],
  },
  {
    group: "Dans la Command Palette",
    items: [
      { keys: ["↑", "↓"], label: "Naviguer dans les résultats" },
      { keys: ["⏎"], label: "Valider le résultat sélectionné" },
      { keys: ["Esc"], label: "Fermer la palette" },
    ],
  },
  {
    group: "Dans l'éditeur YAML",
    items: [
      {
        keys: ["Tab"],
        label: "Indenter (insère 2 espaces)",
      },
      {
        keys: ["Shift", "Tab"],
        label: "Désindenter (retire 2 espaces)",
      },
    ],
  },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsModal({ open, onClose }: Props) {
  // Esc ferme la modale.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="keyboard-shortcuts-title"
    >
      <div className="absolute inset-0 bg-argos-bg/70 backdrop-blur-[2px]" />
      <div
        className="relative w-full max-w-lg bg-argos-surface border border-argos-border rounded-lg shadow-2xl overflow-hidden max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-argos-border-subtle flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Keyboard size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
            <h2
              id="keyboard-shortcuts-title"
              className="text-sm font-semibold text-argos-fg"
            >
              Raccourcis clavier
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg flex items-center gap-1"
          >
            <X size={12} strokeWidth={2} />
            esc
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
          {SHORTCUTS.map((group) => (
            <div key={group.group}>
              <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
                {group.group}
              </h3>
              <ul className="space-y-1.5">
                {group.items.map((sc, idx) => (
                  <li
                    key={`${group.group}-${idx}`}
                    className="flex items-start justify-between gap-3"
                  >
                    <div className="text-xs text-argos-fg-secondary leading-relaxed">
                      {sc.label}
                      {sc.context && (
                        <span className="block font-mono text-[10px] text-argos-fg-tertiary">
                          {sc.context}
                        </span>
                      )}
                    </div>
                    <div className="shrink-0 flex items-center gap-1">
                      {sc.keys.map((key, kidx) => (
                        <span key={kidx} className="flex items-center gap-1">
                          {kidx > 0 && (
                            <span className="font-mono text-[10px] text-argos-fg-tertiary">+</span>
                          )}
                          <kbd className="font-mono text-[10px] text-argos-fg-secondary border border-argos-border rounded px-1.5 py-0.5 bg-argos-surface-2">
                            {key}
                          </kbd>
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="px-4 py-2 border-t border-argos-border-subtle bg-argos-surface-2/40 font-mono text-[10px] text-argos-fg-tertiary text-center">
          Astuce : la palette (⌘K) reste plus puissante pour chercher /
          déclencher quelque chose précisément.
        </div>
      </div>
    </div>
  );
}
