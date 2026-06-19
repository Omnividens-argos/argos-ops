import { ArrowRight, Layers, LayoutDashboard, Play, Search, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Route } from "../routes.ts";
import { TOOLS } from "../routes.ts";
import { POLES } from "../poles/poles.ts";
import { AGENT_CATEGORIES } from "../lib/agentCatalog";

// Command Palette façon Linear / Slack / VSCode (Ctrl+K).
// Trois familles d'action :
//   - Navigate     → bascule la route (Accueil, pôles, outils globaux)
//   - Open bot     → ouvre BotDetail pour un des bots du catalogue
//   - Run bot now  → déclenche un run via /api/agents/.../runs (RUNNABLE only)
//
// Fuzzy-ish matching simple (substring case-insensitive) + ranking par
// type (navigate > open > run pour égal score).

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (route: Route) => void;
  onOpenBot: (name: string) => void;
  onRunBot: (name: string) => Promise<void>;
  /** Set des noms d'agents déclenchables manuellement (Run now). */
  runnableAgents: ReadonlySet<string>;
}

type ActionType = "navigate" | "open" | "run";

interface Action {
  id: string;
  type: ActionType;
  label: string;
  hint: string;
  icon: LucideIcon;
  run: () => void | Promise<void>;
  /** Mots-clés supplémentaires pour le matching. */
  keywords: string;
}

export function CommandPalette({
  open,
  onClose,
  onNavigate,
  onOpenBot,
  onRunBot,
  runnableAgents,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [running, setRunning] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const allActions = useMemo<Action[]>(() => {
    const out: Action[] = [
      {
        id: "nav:home",
        type: "navigate",
        label: "Accueil",
        hint: "Dashboard global cross-pôle",
        icon: LayoutDashboard,
        keywords: "home accueil dashboard overview vue ensemble",
        run: () => onNavigate({ kind: "home" }),
      },
      ...POLES.map<Action>((p) => ({
        id: `nav:pole:${p.id}`,
        type: "navigate",
        label: p.name,
        hint: p.description,
        icon: Layers,
        keywords: `pole pôle ${p.id} ${p.name} ${p.agent ?? ""}`,
        run: () => onNavigate({ kind: "pole", id: p.id }),
      })),
      ...TOOLS.map<Action>((t) => ({
        id: `nav:tool:${t.id}`,
        type: "navigate",
        label: t.name,
        hint: t.description,
        icon: t.icon,
        keywords: `${t.id} ${t.name} outil global tool`,
        run: () => onNavigate({ kind: "tool", id: t.id }),
      })),
    ];

    // Tous les bots actifs du catalogue.
    for (const cat of AGENT_CATEGORIES) {
      for (const agent of cat.agents) {
        if (agent.status !== "active" || !agent.name) continue;
        const display = agent.displayName;
        out.push({
          id: `open:${agent.name}`,
          type: "open",
          label: `Ouvrir ${display}`,
          hint: `${cat.title} · ${agent.shortLabel}`,
          icon: ArrowRight,
          keywords: `${display} ${agent.shortLabel} ${cat.title} ${agent.description}`,
          run: () => onOpenBot(agent.name!),
        });
        if (runnableAgents.has(agent.name)) {
          out.push({
            id: `run:${agent.name}`,
            type: "run",
            label: `Run now — ${display}`,
            hint: `Déclenche ${display} maintenant`,
            icon: Play,
            keywords: `run now lance trigger ${display} ${agent.shortLabel}`,
            run: async () => {
              setRunning(agent.name!);
              try {
                await onRunBot(agent.name!);
              } finally {
                setRunning(null);
              }
            },
          });
        }
      }
    }
    return out;
  }, [onNavigate, onOpenBot, onRunBot, runnableAgents]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q === "") {
      return allActions.slice(0, 8);
    }
    const tokens = q.split(/\s+/).filter(Boolean);
    return allActions
      .map((a) => {
        const hay = `${a.label} ${a.hint} ${a.keywords}`.toLowerCase();
        let score = 0;
        for (const t of tokens) {
          if (!hay.includes(t)) return null;
          score += hay.startsWith(t) ? 4 : hay.split(t).length - 1;
          if (a.label.toLowerCase().startsWith(t)) score += 6;
        }
        // Petit boost pour les nav (souvent l'intention).
        if (a.type === "navigate") score += 2;
        return { action: a, score };
      })
      .filter((x): x is { action: Action; score: number } => x !== null)
      .sort((a, b) => b.score - a.score)
      .slice(0, 20)
      .map((x) => x.action);
  }, [allActions, query]);

  // Reset & focus à chaque ouverture.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      const id = window.setTimeout(() => inputRef.current?.focus(), 10);
      return () => window.clearTimeout(id);
    }
    return undefined;
  }, [open]);

  // Active toujours dans les bornes du résultat filtré.
  useEffect(() => {
    if (active >= filtered.length) setActive(0);
  }, [filtered, active]);

  if (!open) return null;

  const handleSubmit = async () => {
    const action = filtered[active];
    if (!action) return;
    const closeAfter = action.type !== "run";
    if (closeAfter) onClose();
    await action.run();
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center pt-[12vh] px-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div className="absolute inset-0 bg-argos-bg/70 backdrop-blur-[2px]" />
      <div
        className="relative w-full max-w-xl bg-argos-surface border border-argos-border rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-argos-border-subtle">
          <Search size={14} className="text-argos-fg-tertiary shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tape une action — ex : « veille », « inbox », « run uptime »…"
            className="flex-1 bg-transparent border-none outline-none text-sm text-argos-fg placeholder:text-argos-fg-disabled"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(filtered.length - 1, i + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(0, i - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                void handleSubmit();
              } else if (e.key === "Escape") {
                e.preventDefault();
                onClose();
              }
            }}
          />
          <kbd className="hidden sm:inline font-mono text-[10px] text-argos-fg-tertiary border border-argos-border-subtle rounded px-1.5 py-0.5">
            esc
          </kbd>
        </div>

        <div className="max-h-[50vh] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="p-6 text-center">
              <Sparkles
                size={20}
                strokeWidth={1.5}
                className="mx-auto mb-2 text-argos-fg-tertiary"
              />
              <div className="text-sm text-argos-fg-secondary">
                Rien ne match « {query} »
              </div>
              <div className="font-mono text-[11px] text-argos-fg-tertiary mt-1">
                Essaie un nom d'agent ou « run », « inbox », « veille »…
              </div>
            </div>
          ) : (
            filtered.map((action, idx) => {
              const Icon = action.icon;
              const isActive = idx === active;
              const isRunning = running === action.id.replace(/^run:/, "");
              return (
                <button
                  key={action.id}
                  type="button"
                  onMouseEnter={() => setActive(idx)}
                  onClick={() => {
                    if (action.type !== "run") onClose();
                    void action.run();
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
                    isActive
                      ? "bg-argos-surface-2 text-argos-fg"
                      : "text-argos-fg-secondary hover:bg-argos-surface-2/60"
                  }`}
                >
                  <Icon
                    size={14}
                    strokeWidth={2}
                    className={`shrink-0 ${
                      action.type === "run"
                        ? "text-argos-info"
                        : action.type === "open"
                          ? "text-argos-fg-tertiary"
                          : "text-argos-fg-secondary"
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{action.label}</div>
                    <div className="font-mono text-[10px] text-argos-fg-tertiary truncate">
                      {action.hint}
                    </div>
                  </div>
                  <span className="font-mono text-[9px] uppercase tracking-widest text-argos-fg-tertiary shrink-0">
                    {isRunning ? "…" : action.type}
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div className="px-3 py-1.5 border-t border-argos-border-subtle flex items-center justify-between font-mono text-[10px] text-argos-fg-tertiary">
          <span>
            <kbd className="border border-argos-border-subtle rounded px-1 py-0.5">↑↓</kbd>{" "}
            naviguer ·{" "}
            <kbd className="border border-argos-border-subtle rounded px-1 py-0.5">⏎</kbd>{" "}
            valider
          </span>
          <span>{filtered.length} résultat{filtered.length > 1 ? "s" : ""}</span>
        </div>
      </div>
    </div>
  );
}
