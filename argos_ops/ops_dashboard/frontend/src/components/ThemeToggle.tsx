import { Moon, Sun } from "lucide-react";
import { useTheme } from "../hooks/useTheme";

// Toggle theme light/dark — icône Sun/Moon en topbar. L'init synchrone
// se fait dans index.html (anti-FOUC), ce composant ne fait que basculer.

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "Passer en mode clair" : "Passer en mode sombre"}
      title={isDark ? "Mode clair" : "Mode sombre"}
      className="size-8 inline-flex items-center justify-center rounded-md border border-argos-border-subtle text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg transition-colors"
    >
      {isDark ? <Sun size={14} strokeWidth={2} /> : <Moon size={14} strokeWidth={2} />}
    </button>
  );
}
