import { useEffect, useState } from "react";

// Hook theme light/dark persisté en localStorage. Le script anti-FOUC dans
// index.html applique la classe `.dark` AVANT le mount React pour éviter
// le flash. Ce hook synchronise React state avec l'état DOM puis gère
// les toggles.

export type Theme = "light" | "dark";

const STORAGE_KEY = "argos-theme";

function readInitial(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function useTheme(): {
  theme: Theme;
  toggle: () => void;
  setTheme: (next: Theme) => void;
} {
  const [theme, setThemeState] = useState<Theme>(readInitial);

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // localStorage indisponible (mode private etc.) — pas critique
    }
  }, [theme]);

  return {
    theme,
    setTheme: setThemeState,
    toggle: () => setThemeState((t) => (t === "dark" ? "light" : "dark")),
  };
}
