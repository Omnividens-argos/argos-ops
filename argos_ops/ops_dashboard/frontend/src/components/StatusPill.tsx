import {
  CheckCircle2,
  Circle,
  PauseCircle,
  Power,
  ShieldAlert,
  Timer,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { RunStatus } from "../api";

// Pill status unifié — combine icône Lucide + couleur + label (WCAG color-not-only).
// Source : docs/UI_DECISIONS.md § 4 (révision 2026-05-12).

interface Props {
  status: RunStatus | null;
  /** Si true, l'agent est désactivé manuellement via le panel. */
  disabled?: boolean;
  /** Si true, l'agent est paused (paused_until > now). */
  paused?: boolean;
  /** Si true, l'agent est bloqué par un breaker. */
  breakerTripped?: boolean;
}

interface PillSpec {
  icon: LucideIcon;
  label: string;
  classes: string;
}

function getSpec({ status, disabled, paused, breakerTripped }: Props): PillSpec {
  if (breakerTripped) {
    return {
      icon: ShieldAlert,
      label: "bloqué",
      classes:
        "bg-argos-danger/10 text-argos-danger border-argos-danger/30",
    };
  }
  if (disabled) {
    return {
      icon: Power,
      label: "désactivé",
      classes:
        "bg-argos-surface-2 text-argos-fg-disabled border-argos-border-subtle",
    };
  }
  if (paused) {
    return {
      icon: PauseCircle,
      label: "en pause",
      classes:
        "bg-argos-warning/10 text-argos-warning border-argos-warning/30",
    };
  }
  switch (status) {
    case "success":
      return {
        icon: CheckCircle2,
        label: "sain",
        classes:
          "bg-argos-healthy/10 text-argos-healthy border-argos-healthy/30",
      };
    case "failed":
      return {
        icon: XCircle,
        label: "échec",
        classes:
          "bg-argos-danger/10 text-argos-danger border-argos-danger/30",
      };
    case "killed_by_breaker":
      return {
        icon: ShieldAlert,
        label: "bloqué",
        classes:
          "bg-argos-danger/10 text-argos-danger border-argos-danger/30",
      };
    case "skipped_disabled":
      return {
        icon: Power,
        label: "désactivé",
        classes:
          "bg-argos-surface-2 text-argos-fg-disabled border-argos-border-subtle",
      };
    case "skipped_paused":
      return {
        icon: PauseCircle,
        label: "en pause",
        classes:
          "bg-argos-warning/10 text-argos-warning border-argos-warning/30",
      };
    case "skipped_daily_limit":
      return {
        icon: Timer,
        label: "quota atteint",
        classes:
          "bg-argos-info/10 text-argos-info border-argos-info/30",
      };
    default:
      return {
        icon: Circle,
        label: "jamais exécuté",
        classes:
          "bg-argos-surface-2 text-argos-fg-tertiary border-argos-border-subtle",
      };
  }
}

export function StatusPill(props: Props) {
  const spec = getSpec(props);
  const Icon = spec.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border font-mono text-[11px] ${spec.classes}`}
    >
      <Icon size={12} strokeWidth={2.25} />
      {spec.label}
    </span>
  );
}
