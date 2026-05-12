/** @type {import('tailwindcss').Config} */
// Dual theme via CSS variables — voir src/index.css pour les valeurs hex.
// La source de vérité du choix design est docs/UI_DECISIONS.md § 2.

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "argos-bg": "rgb(var(--color-bg-base) / <alpha-value>)",
        "argos-surface": "rgb(var(--color-bg-surface) / <alpha-value>)",
        "argos-surface-2": "rgb(var(--color-bg-surface-2) / <alpha-value>)",
        "argos-border": "rgb(var(--color-border) / <alpha-value>)",
        "argos-border-subtle": "rgb(var(--color-border-subtle) / <alpha-value>)",
        "argos-fg": "rgb(var(--color-fg) / <alpha-value>)",
        "argos-fg-secondary": "rgb(var(--color-fg-secondary) / <alpha-value>)",
        "argos-fg-tertiary": "rgb(var(--color-fg-tertiary) / <alpha-value>)",
        "argos-fg-disabled": "rgb(var(--color-fg-disabled) / <alpha-value>)",
        "argos-healthy": "rgb(var(--color-healthy) / <alpha-value>)",
        "argos-info": "rgb(var(--color-info) / <alpha-value>)",
        "argos-warning": "rgb(var(--color-warning) / <alpha-value>)",
        "argos-danger": "rgb(var(--color-danger) / <alpha-value>)",
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
};
