// Barre de filtres du pôle Veille : recherche plein-texte + thème + sévérité +
// fenêtre temporelle. Pur présentationnel (état remonté au parent VeillePage).

import { Search, X } from "lucide-react";
import type { Severity } from "../api.ts";
import { TextInput } from "../../components/ui.tsx";
import { SEVERITY_LABEL, type DateRange } from "./lib.ts";

const SEVERITIES: (Severity | "all")[] = ["all", "critical", "warning", "info"];
const RANGES: { id: DateRange; label: string }[] = [
  { id: "all", label: "tout" },
  { id: "24h", label: "24 h" },
  { id: "7d", label: "7 j" },
  { id: "30d", label: "30 j" },
];

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors ${
        active
          ? "border-argos-info/40 bg-argos-info/15 text-argos-info"
          : "border-argos-border-subtle bg-argos-surface-2 text-argos-fg-tertiary hover:text-argos-fg"
      }`}
    >
      {children}
    </button>
  );
}

export interface FilterState {
  query: string;
  themes: Set<string>;
  severity: Severity | "all";
  range: DateRange;
}

export interface FilterBarProps {
  availableThemes: string[];
  state: FilterState;
  onChange: (next: FilterState) => void;
}

export function FilterBar({ availableThemes, state, onChange }: FilterBarProps) {
  const toggleTheme = (theme: string) => {
    const next = new Set(state.themes);
    if (next.has(theme)) next.delete(theme);
    else next.add(theme);
    onChange({ ...state, themes: next });
  };

  const hasFilters =
    state.query !== "" ||
    state.themes.size > 0 ||
    state.severity !== "all" ||
    state.range !== "all";

  return (
    <div className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
      <div className="flex items-center gap-2">
        <Search className="h-3.5 w-3.5 shrink-0 text-argos-fg-tertiary" aria-hidden />
        <div className="flex-1">
          <TextInput
            placeholder="Rechercher dans la mémoire de veille (corps, tag, script)…"
            value={state.query}
            onChange={(e) => onChange({ ...state, query: e.target.value })}
          />
        </div>
        {hasFilters && (
          <button
            type="button"
            onClick={() =>
              onChange({ query: "", themes: new Set(), severity: "all", range: "all" })
            }
            className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary hover:text-argos-fg"
          >
            <X className="h-3 w-3" aria-hidden /> reset
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
            sévérité
          </span>
          {SEVERITIES.map((s) => (
            <Chip
              key={s}
              active={state.severity === s}
              onClick={() => onChange({ ...state, severity: s })}
            >
              {s === "all" ? "toutes" : SEVERITY_LABEL[s]}
            </Chip>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
            fenêtre
          </span>
          {RANGES.map((r) => (
            <Chip
              key={r.id}
              active={state.range === r.id}
              onClick={() => onChange({ ...state, range: r.id })}
            >
              {r.label}
            </Chip>
          ))}
        </div>

        {availableThemes.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
              thème
            </span>
            {availableThemes.map((theme) => (
              <Chip key={theme} active={state.themes.has(theme)} onClick={() => toggleTheme(theme)}>
                {theme}
              </Chip>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
