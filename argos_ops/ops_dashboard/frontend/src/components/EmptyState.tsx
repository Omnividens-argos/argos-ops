import type { LucideIcon } from "lucide-react";
import { Sparkles } from "lucide-react";

// Empty state humain — remplace les "Empty" / "Aucune donnée" arides.
// Pattern systématique : icône douce + titre positif + sous-texte explicatif
// + (optionnel) action CTA.
//
// Tons sémantiques :
//   - "celebrate" (par défaut) : tout va bien, vide = bonne nouvelle ("0 alertes ✨")
//   - "neutral" : vide normal, juste informatif ("aucun lead aujourd'hui")
//   - "loading" : pendant le polling initial
//   - "error" : échec de fetch

type EmptyTone = "celebrate" | "neutral" | "loading" | "error";

interface EmptyStateProps {
  tone?: EmptyTone;
  icon?: LucideIcon;
  title: string;
  body?: string;
  action?: React.ReactNode;
  compact?: boolean;
}

const TONE_STYLES: Record<EmptyTone, string> = {
  celebrate: "border-argos-healthy/30 bg-argos-healthy/5",
  neutral: "border-argos-border-subtle bg-argos-surface/40",
  loading: "border-argos-border-subtle bg-argos-surface/40",
  error: "border-argos-danger/30 bg-argos-danger/5",
};

const TONE_ICON_COLOR: Record<EmptyTone, string> = {
  celebrate: "text-argos-healthy",
  neutral: "text-argos-fg-tertiary",
  loading: "text-argos-fg-tertiary animate-pulse",
  error: "text-argos-danger",
};

export function EmptyState({
  tone = "neutral",
  icon: Icon = Sparkles,
  title,
  body,
  action,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={`rounded-md border ${TONE_STYLES[tone]} ${
        compact ? "p-4" : "p-8"
      } flex flex-col items-center text-center gap-3`}
    >
      <Icon
        size={compact ? 20 : 28}
        strokeWidth={1.5}
        className={TONE_ICON_COLOR[tone]}
      />
      <div className="space-y-1">
        <div className="text-sm font-semibold text-argos-fg">{title}</div>
        {body && (
          <p className="text-xs text-argos-fg-secondary leading-relaxed max-w-md">
            {body}
          </p>
        )}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
