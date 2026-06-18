// Comparaison A/B(/C) côte à côte des variantes d'une créa sélectionnée. Chaque
// variante : angle, headline + texte principal, avec compteur de caractères vs la
// contrainte de la plateforme (headline_ok / primary_ok côté backend).

import type { AdCreative, AdPlatform, CreativeVariant } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { platformById, platformLabel } from "./lib.ts";

export interface ABComparisonProps {
  creative: AdCreative | null;
  platforms: AdPlatform[];
}

function Counter({ len, max, ok }: { len: number; max: number; ok: boolean }) {
  return (
    <span className={`font-mono text-[10px] ${ok ? "text-argos-healthy" : "text-argos-danger"}`}>
      {len}
      {max > 0 ? `/${max}` : ""} car.
    </span>
  );
}

function VariantCard({
  variant,
  headlineMax,
  primaryMax,
}: {
  variant: CreativeVariant;
  headlineMax: number;
  primaryMax: number;
}) {
  return (
    <div className="flex min-w-[240px] flex-1 flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-bg px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <Badge tone="info">Variante {variant.label}</Badge>
        {variant.angle && (
          <span className="truncate font-mono text-[10px] text-argos-fg-tertiary">{variant.angle}</span>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[9px] uppercase tracking-widest text-argos-fg-disabled">
            headline
          </span>
          <Counter len={variant.headline_len} max={headlineMax} ok={variant.headline_ok} />
        </div>
        <p className="font-mono text-[11px] font-medium leading-snug text-argos-fg">
          {variant.headline || "—"}
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[9px] uppercase tracking-widest text-argos-fg-disabled">
            texte principal
          </span>
          <Counter len={variant.primary_len} max={primaryMax} ok={variant.primary_ok} />
        </div>
        <p className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-argos-fg-secondary">
          {variant.primary_text || "—"}
        </p>
      </div>

      {variant.description && (
        <p className="border-t border-argos-border-subtle pt-1.5 font-mono text-[10px] leading-snug text-argos-fg-tertiary">
          {variant.description}
        </p>
      )}
    </div>
  );
}

export function ABComparison({ creative, platforms }: ABComparisonProps) {
  if (!creative) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Sélectionne une créa pour comparer ses variantes A/B côte à côte.
      </div>
    );
  }
  const plat = platformById(platforms, creative.platform);
  const headlineMax = plat?.headline_max ?? 0;
  const primaryMax = plat?.primary_max ?? 0;

  return (
    <div className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{platformLabel(platforms, creative.platform)}</Badge>
        <span className="font-mono text-xs font-medium text-argos-fg">{creative.title}</span>
        {creative.objective && (
          <span className="font-mono text-[10px] text-argos-fg-tertiary">· {creative.objective}</span>
        )}
      </div>

      {creative.variants.length === 0 ? (
        <p className="font-mono text-[11px] text-argos-fg-tertiary">(aucune variante)</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {creative.variants.map((v, i) => (
            <VariantCard
              key={`${v.label}-${i}`}
              variant={v}
              headlineMax={headlineMax}
              primaryMax={primaryMax}
            />
          ))}
        </div>
      )}

      {creative.brief && (
        <p className="border-t border-argos-border-subtle pt-2 font-mono text-[10px] leading-snug text-argos-fg-tertiary">
          {creative.brief}
        </p>
      )}
    </div>
  );
}
