import { createContext, useCallback, useContext, useEffect, useState } from "react";

// Préférences utilisateur — persistées dans localStorage et propagées via
// React context. Aujourd'hui : mode (débutant / expert) et density (compact /
// confortable). Volontairement minimaliste — pas de lib (zustand, jotai).
//
// Le mode débutant masque les contrôles avancés (intensity slider, daily
// limit, tier1 threshold) et expose juste les essentiels (enable/pause/notes).

export type UserMode = "beginner" | "expert";
export type Density = "compact" | "comfortable";

interface UserPrefs {
  mode: UserMode;
  density: Density;
  setMode: (next: UserMode) => void;
  setDensity: (next: Density) => void;
}

const DEFAULT_PREFS: UserPrefs = {
  mode: "beginner",
  density: "comfortable",
  setMode: () => {},
  setDensity: () => {},
};

const KEY = "argos.userPrefs.v1";

const Ctx = createContext<UserPrefs>(DEFAULT_PREFS);

function loadFromStorage(): { mode: UserMode; density: Density } {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { mode: "beginner", density: "comfortable" };
    const parsed = JSON.parse(raw) as Partial<{ mode: UserMode; density: Density }>;
    return {
      mode: parsed.mode === "expert" ? "expert" : "beginner",
      density: parsed.density === "compact" ? "compact" : "comfortable",
    };
  } catch {
    return { mode: "beginner", density: "comfortable" };
  }
}

function persist(prefs: { mode: UserMode; density: Density }): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // ignore (mode privé)
  }
}

export function UserPrefsProvider({ children }: { children: React.ReactNode }) {
  const [{ mode, density }, setState] = useState(() => loadFromStorage());

  useEffect(() => {
    persist({ mode, density });
  }, [mode, density]);

  const setMode = useCallback((next: UserMode) => {
    setState((prev) => ({ ...prev, mode: next }));
  }, []);

  const setDensity = useCallback((next: Density) => {
    setState((prev) => ({ ...prev, density: next }));
  }, []);

  return (
    <Ctx.Provider value={{ mode, density, setMode, setDensity }}>{children}</Ctx.Provider>
  );
}

export function useUserPrefs(): UserPrefs {
  return useContext(Ctx);
}

// Helper — renvoie le bon set de classes Tailwind selon la density courante.
// Centralisé pour rester cohérent à travers les composants (sidebar, listes…).
export function useDensityClasses(): {
  /** Padding vertical d'une row de liste (Inbox / Catalogue). */
  rowPaddingY: string;
  /** Padding vertical d'un item de nav (sidebar). */
  navPaddingY: string;
  /** Gap vertical entre items d'une liste. */
  gapY: string;
} {
  const { density } = useUserPrefs();
  if (density === "compact") {
    return {
      rowPaddingY: "py-1.5",
      navPaddingY: "py-1",
      gapY: "space-y-1",
    };
  }
  return {
    rowPaddingY: "py-3",
    navPaddingY: "py-2",
    gapY: "space-y-2",
  };
}
