// Composants UI primitifs réutilisables — cohérents avec UI_DECISIONS.md
// (dark zinc + accents emerald/sky/amber/rose). Évite de dupliquer du
// markup Tailwind entre les vues.

import type { ButtonHTMLAttributes, InputHTMLAttributes } from "react";

// =============================================================================
// Button
// =============================================================================
type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-argos-info/15 border-argos-info/40 text-argos-info hover:bg-argos-info/25",
  secondary:
    "bg-argos-surface-2 border-argos-border-subtle text-argos-fg-secondary hover:bg-argos-border-subtle hover:text-argos-fg",
  danger:
    "bg-argos-danger/15 border-argos-danger/40 text-argos-danger hover:bg-argos-danger/25",
  ghost:
    "bg-transparent border-transparent text-argos-fg-tertiary hover:bg-argos-surface-2 hover:text-argos-fg",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "text-[11px] px-2 py-1",
  md: "text-xs px-3 py-1.5",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`font-mono rounded-md border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      {...rest}
    />
  );
}

// =============================================================================
// Toggle / Switch
// =============================================================================
interface ToggleProps {
  enabled: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
}

export function Toggle({ enabled, onChange, disabled, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
        enabled ? "bg-argos-healthy" : "bg-argos-surface-2 border border-argos-border-subtle"
      }`}
    >
      <span
        className={`inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${
          enabled ? "translate-x-5" : "translate-x-1"
        }`}
      />
    </button>
  );
}

// =============================================================================
// Range Slider (intensity 1-10)
// =============================================================================
interface SliderProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  value: number;
  onValueChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
}

export function Slider({
  value,
  onValueChange,
  min = 1,
  max = 10,
  step = 1,
  ...rest
}: SliderProps) {
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onValueChange(Number(e.target.value))}
      className="w-full h-1 bg-argos-surface-2 rounded-lg appearance-none cursor-pointer accent-argos-info"
      {...rest}
    />
  );
}

// =============================================================================
// Input texte / number
// =============================================================================
interface TextInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
}

export function TextInput({ label, className = "", ...rest }: TextInputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {label}
        </label>
      )}
      <input
        className={`bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60 ${className}`}
        {...rest}
      />
    </div>
  );
}

// =============================================================================
// Badge / Pill
// =============================================================================
type BadgeTone = "neutral" | "healthy" | "info" | "warning" | "danger";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-argos-surface-2 text-argos-fg-tertiary border-argos-border-subtle",
  healthy: "bg-argos-healthy/10 text-argos-healthy border-argos-healthy/30",
  info: "bg-argos-info/10 text-argos-info border-argos-info/30",
  warning: "bg-argos-warning/10 text-argos-warning border-argos-warning/30",
  danger: "bg-argos-danger/10 text-argos-danger border-argos-danger/30",
};

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border font-mono text-[10px] uppercase tracking-widest ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

// =============================================================================
// Toast-like inline error/success
// =============================================================================
interface FlashProps {
  variant: "success" | "error";
  message: string;
  onDismiss?: () => void;
}

export function Flash({ variant, message, onDismiss }: FlashProps) {
  const styles =
    variant === "success"
      ? "bg-argos-healthy/10 border-argos-healthy/40 text-argos-healthy"
      : "bg-argos-danger/10 border-argos-danger/40 text-argos-danger";
  return (
    <div
      className={`border rounded-md px-3 py-2 font-mono text-xs flex items-center justify-between gap-3 ${styles}`}
    >
      <span className="truncate">{message}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="font-mono text-[11px] underline decoration-dotted underline-offset-2 opacity-80 hover:opacity-100"
        >
          dismiss
        </button>
      )}
    </div>
  );
}
