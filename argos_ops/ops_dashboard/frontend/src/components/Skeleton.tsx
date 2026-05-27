// Skeleton primitives — placeholders animés pour les états loading.
// Plus humains que « Chargement… » : ils donnent une idée de la forme du
// contenu à venir (la « squelette » d'une row, d'une card, d'une grille).
//
// L'animation pulse (`argos-skeleton` dans index.css) est inhibée par
// prefers-reduced-motion. Aucune dépendance.

interface BlockProps {
  /** Largeur Tailwind (ex. "w-1/2", "w-32"). Défaut : pleine largeur. */
  width?: string;
  /** Hauteur Tailwind (ex. "h-4", "h-12"). Défaut : "h-3" (~ ligne texte). */
  height?: string;
  /** Forme : rectangle, ligne (rounded full), cercle. */
  shape?: "rect" | "line" | "circle";
  className?: string;
}

export function SkeletonBlock({
  width = "w-full",
  height = "h-3",
  shape = "rect",
  className = "",
}: BlockProps) {
  const rounded =
    shape === "circle" ? "rounded-full" : shape === "line" ? "rounded-full" : "rounded";
  return (
    <div
      className={`argos-skeleton bg-argos-surface-2 ${width} ${height} ${rounded} ${className}`}
    />
  );
}

// =============================================================================
// SkeletonRow — pour les rangées de liste (Inbox draft, Outputs, runs…)
// =============================================================================
export function SkeletonRow() {
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface px-4 py-3 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2 min-w-0">
          <SkeletonBlock width="w-2/3" height="h-3.5" />
          <SkeletonBlock width="w-full" height="h-2.5" />
          <SkeletonBlock width="w-1/2" height="h-2" />
        </div>
        <SkeletonBlock width="w-16" height="h-5" shape="line" className="shrink-0" />
      </div>
    </div>
  );
}

// =============================================================================
// SkeletonCard — pour les KPI cards (Today, Cash, Health, BotDetail live)
// =============================================================================
export function SkeletonCard() {
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface px-4 py-3 space-y-2">
      <SkeletonBlock width="w-1/2" height="h-2" />
      <SkeletonBlock width="w-2/3" height="h-6" />
      <SkeletonBlock width="w-3/4" height="h-2" />
    </div>
  );
}

// =============================================================================
// SkeletonList — N rangées de SkeletonRow (utilitaire raccourci)
// =============================================================================
export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }, (_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}

// =============================================================================
// SkeletonGrid — N cards en grille (KPIs Today / Cash / Health)
// =============================================================================
export function SkeletonGrid({
  count = 4,
  cols = "grid-cols-2 sm:grid-cols-4",
}: {
  count?: number;
  cols?: string;
}) {
  return (
    <div className={`grid gap-3 ${cols}`}>
      {Array.from({ length: count }, (_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
