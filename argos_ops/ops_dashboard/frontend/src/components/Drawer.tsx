// Drawer latéral droit du cockpit (refonte SF). Panneau de détail
// (lead / fait mémoire / run / draft) qui glisse depuis la droite. Scrim z-30,
// Esc, click-outside, focus-trap + restauration du focus, aria-modal.
// Cf. docs/UI_DECISIONS.md §5.1 / §6. (Animation slide affinée en Phase 7.)

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Largeur du panneau. */
  width?: "sm" | "md" | "lg";
}

const WIDTHS: Record<NonNullable<DrawerProps["width"]>, string> = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-2xl",
};

export function Drawer({ open, onClose, title, children, footer, width = "md" }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const focusable = panel?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    (focusable ?? panel)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const items = Array.from(
        panel.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      restoreRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="argos-fade-in fixed inset-0 z-30 flex justify-end bg-argos-bg/70 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        className={`flex h-full w-full ${WIDTHS[width]} flex-col border-l border-argos-border bg-argos-surface shadow-2xl focus-visible:outline-none`}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-argos-border-subtle px-5 py-3">
          <h2 className="text-sm font-semibold text-argos-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="rounded p-1 text-argos-fg-tertiary transition-colors hover:bg-argos-surface-2 hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info"
          >
            <X size={16} aria-hidden />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 text-sm text-argos-fg-secondary">{children}</div>
        {footer != null ? (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-argos-border-subtle px-5 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
