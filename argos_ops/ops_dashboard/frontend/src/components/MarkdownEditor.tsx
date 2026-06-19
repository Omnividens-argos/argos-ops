import { useState } from "react";
import type { KeyboardEvent } from "react";
import { Eye, Pencil, Columns2 } from "lucide-react";
import { MarkdownPreview } from "./MarkdownPreview.tsx";

type Mode = "write" | "preview" | "split";

interface MarkdownEditorProps {
  value: string;
  onChange: (md: string) => void;
  height?: number;
  placeholder?: string;
  ariaLabel?: string;
}

interface ModeOption {
  mode: Mode;
  label: string;
  icon: typeof Pencil;
}

const MODE_OPTIONS: readonly ModeOption[] = [
  { mode: "write", label: "Écrire", icon: Pencil },
  { mode: "preview", label: "Aperçu", icon: Eye },
  { mode: "split", label: "Split", icon: Columns2 },
];

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg";

export function MarkdownEditor({
  value,
  onChange,
  height,
  placeholder,
  ariaLabel,
}: MarkdownEditorProps): JSX.Element {
  const [mode, setMode] = useState<Mode>("split");
  const resolvedHeight = height ?? 320;
  const resolvedAriaLabel = ariaLabel ?? "Éditeur Markdown";

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key !== "Tab") return;
    event.preventDefault();
    const target = event.currentTarget;
    const start = target.selectionStart;
    const end = target.selectionEnd;
    const next = `${value.slice(0, start)}  ${value.slice(end)}`;
    const caret = start + 2;
    onChange(next);
    // Restore the caret after React re-renders the controlled value.
    requestAnimationFrame(() => {
      target.selectionStart = caret;
      target.selectionEnd = caret;
    });
  }

  const textarea = (
    <textarea
      className={`w-full resize-none font-mono text-sm bg-argos-surface text-argos-fg border border-argos-border rounded-md p-3 placeholder:text-argos-fg-tertiary ${FOCUS_RING}`}
      style={{ height: resolvedHeight }}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={handleKeyDown}
      aria-label={resolvedAriaLabel}
      placeholder={placeholder}
      spellCheck={false}
    />
  );

  const preview = (
    <div
      className="border border-argos-border rounded-md p-3 overflow-auto bg-argos-surface"
      style={{ height: resolvedHeight }}
      aria-label={`${resolvedAriaLabel} — aperçu`}
      role="region"
    >
      <MarkdownPreview content={value} />
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      <div
        className="inline-flex self-start rounded-md border border-argos-border bg-argos-surface-2 p-0.5"
        role="group"
        aria-label="Mode d'affichage de l'éditeur"
      >
        {MODE_OPTIONS.map(({ mode: optionMode, label, icon: Icon }) => {
          const active = mode === optionMode;
          return (
            <button
              key={optionMode}
              type="button"
              onClick={() => setMode(optionMode)}
              aria-pressed={active}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${FOCUS_RING} ${
                active
                  ? "bg-argos-surface text-argos-fg shadow-sm"
                  : "text-argos-fg-secondary hover:text-argos-fg"
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </button>
          );
        })}
      </div>

      {mode === "write" && textarea}
      {mode === "preview" && preview}
      {mode === "split" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {textarea}
          {preview}
        </div>
      )}
    </div>
  );
}
