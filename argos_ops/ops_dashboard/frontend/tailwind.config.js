/** @type {import('tailwindcss').Config} */
// Palette canonique figée dans docs/UI_DECISIONS.md § 2 — dark-only zinc base
// + accents emerald/sky/amber/rose. La déclaration explicite ci-dessous évite
// d'avoir à se référer au CSS variable nommage à chaque composant.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces
        "argos-bg": "#09090b",        // zinc-950 — fond principal
        "argos-surface": "#18181b",   // zinc-900 — cards, sidebar, topbar
        "argos-surface-2": "#27272a", // zinc-800 — hover, table header
        "argos-border": "#3f3f46",    // zinc-700 — borders cards
        "argos-border-subtle": "#27272a", // zinc-800 — dividers tableaux
        // Texte
        "argos-fg": "#f4f4f5",        // zinc-100 — titres
        "argos-fg-secondary": "#a1a1aa", // zinc-400 — body
        "argos-fg-tertiary": "#71717a",  // zinc-500 — captions
        "argos-fg-disabled": "#52525b",  // zinc-600 — disabled
        // Status accents
        "argos-healthy": "#10b981",   // emerald-500
        "argos-info": "#0ea5e9",      // sky-500
        "argos-warning": "#f59e0b",   // amber-500
        "argos-danger": "#f43f5e",    // rose-500
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
};
