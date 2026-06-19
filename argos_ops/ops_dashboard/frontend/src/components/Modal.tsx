// Modal partagé du cockpit (refonte SF). Remplace les 3 copies hand-rollées
// (KeyboardShortcutsModal, FactProvenanceModal, IODetailModal). Scrim z-40,
// Esc, click-outside, focus-trap + restauration du focus, aria-modal.
// Cf. docs/UI_DECISIONS.md §5.1 / §6.

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Largeur max du panneau. */
  size?: "sm" | "md" | "lg" | "xl";
  /** Empêche la fermeture par Esc / clic-dehors (ex. formulaire dirty). */
  dismissable?: boolean;
}

const SIZES: Record<NonNullable<ModalProps["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
  xl: "max-w-5xl",
};

export function Modal({ open, onClose, title, children, footer, size = "md", dismissable = true }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    // Focus initial sur le panneau (ou premier focusable).
    const focusable = panel?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    (focusable ?? panel)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && dismissable) {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      // Focus-trap : cycle dans le panneau.
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
  }, [open, dismissable, onClose]);

  if (!open) return null;

  return (
    <div
      className="argos-fade-in fixed inset-0 z-40 flex items-center justify-center bg-argos-bg/70 p-4 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && dismissable) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        className={`flex max-h-[90vh] w-full ${SIZES[size]} flex-col overflow-hidden rounded-lg border border-argos-border bg-argos-surface shadow-2xl focus-visible:outline-none`}
      >
        {title != null ? (
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
        ) : null}
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
