import { useEffect, useId, useRef, useState } from "react";
import { HelpCircle } from "lucide-react";
import { lookupTerm } from "../lib/glossary";

// Tooltip réutilisable — wrap un terme technique et révèle son explication
// au hover/focus. Trois usages :
//
//   1. <Tooltip term="MRR">MRR</Tooltip>     // auto-lookup dans le glossaire
//   2. <Tooltip text="Hint custom">Label</Tooltip>
//   3. <TooltipIcon term="Tier 1" />          // icône ? cliquable, pas de wrap
//
// Le contenu apparaît au hover du parent OU au focus clavier (a11y). Délai
// 200ms en entrée, sortie immédiate (cf. UI guideline #18). Anti-clip par
// repositionnement automatique au-dessus si pas de place en dessous.

interface TooltipProps {
  term?: string;
  text?: string;
  children: React.ReactNode;
  /** Décoration sous le wrap pour signaler que c'est cliquable. */
  decorate?: boolean;
}

export function Tooltip({ term, text, children, decorate = true }: TooltipProps) {
  const entry = term ? lookupTerm(term) : null;
  const content = text ?? entry?.long ?? null;
  const id = useId();

  if (!content) {
    // Pas de contenu connu — laisse passer le children sans wrapper inutile.
    return <>{children}</>;
  }

  return (
    <TooltipWrapper content={content} id={id}>
      <span
        className={
          decorate
            ? "underline decoration-dotted decoration-argos-fg-disabled underline-offset-2 cursor-help"
            : "cursor-help"
        }
        tabIndex={0}
        aria-describedby={id}
      >
        {children}
      </span>
    </TooltipWrapper>
  );
}

interface TooltipIconProps {
  term?: string;
  text?: string;
  size?: number;
}

export function TooltipIcon({ term, text, size = 12 }: TooltipIconProps) {
  const entry = term ? lookupTerm(term) : null;
  const content = text ?? entry?.long ?? null;
  const id = useId();
  if (!content) return null;
  return (
    <TooltipWrapper content={content} id={id}>
      <button
        type="button"
        className="inline-flex items-center text-argos-fg-tertiary hover:text-argos-fg transition-colors"
        tabIndex={0}
        aria-label={`Aide : ${term ?? text}`}
        aria-describedby={id}
      >
        <HelpCircle size={size} strokeWidth={2} />
      </button>
    </TooltipWrapper>
  );
}

// =============================================================================
// Wrapper interne — popup positionné dynamiquement
// =============================================================================
interface WrapperProps {
  content: string;
  id: string;
  children: React.ReactNode;
}

function TooltipWrapper({ content, id, children }: WrapperProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<"top" | "bottom">("bottom");
  const triggerRef = useRef<HTMLSpanElement>(null);
  const timerRef = useRef<number | null>(null);

  const show = () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      // Décide top vs bottom selon la place disponible.
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        setPosition(spaceBelow > 180 ? "bottom" : "top");
      }
      setOpen(true);
    }, 200);
  };

  const hide = () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    setOpen(false);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex items-center"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={`absolute z-50 ${
            position === "bottom" ? "top-full mt-1.5" : "bottom-full mb-1.5"
          } left-0 max-w-xs w-max bg-argos-surface-2 border border-argos-border rounded-md px-2.5 py-1.5 text-[11px] leading-relaxed text-argos-fg shadow-lg pointer-events-none`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
