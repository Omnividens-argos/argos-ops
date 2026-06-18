// File de validation des créas publicitaires — humain-in-the-loop (D-017).
// Valide / rejette / met en ligne (shadow) chaque créa, et la sélectionne pour la
// comparaison A/B. Go-live gelé si le breaker est armé (le backend renvoie 409).

import type { AdCreative, AdPlatform } from "../api.ts";
import { Badge, Button } from "../../components/ui.tsx";
import { CREATIVE_STATUS_LABEL, CREATIVE_STATUS_TONE, platformLabel } from "./lib.ts";

export interface CreativeQueueProps {
  creatives: AdCreative[];
  platforms: AdPlatform[];
  selectedId: string | null;
  busyId: string | null;
  breakerTripped: boolean;
  onSelect: (id: string) => void;
  onValidate: (id: string) => void;
  onReject: (id: string) => void;
  onGoLive: (id: string) => void;
}

export function CreativeQueue({
  creatives,
  platforms,
  selectedId,
  busyId,
  breakerTripped,
  onSelect,
  onValidate,
  onReject,
  onGoLive,
}: CreativeQueueProps) {
  if (creatives.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucune créa — le skill ads-creative en dépose ici (status=draft).
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {creatives.map((c) => {
        const isSelected = c.id === selectedId;
        const isBusy = c.id === busyId;
        const badVariants = c.variants.filter((v) => !v.headline_ok || !v.primary_ok).length;
        return (
          <li
            key={c.id}
            className={`rounded-md border bg-argos-surface px-3 py-2.5 transition-colors ${
              isSelected ? "border-argos-info/50" : "border-argos-border-subtle"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <button type="button" onClick={() => onSelect(c.id)} className="min-w-0 flex-1 text-left">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={CREATIVE_STATUS_TONE[c.status] ?? "neutral"}>
                    {CREATIVE_STATUS_LABEL[c.status] ?? c.status}
                  </Badge>
                  <Badge tone="neutral">{platformLabel(platforms, c.platform)}</Badge>
                  <span className="truncate font-mono text-xs font-medium text-argos-fg">{c.title}</span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[10px] text-argos-fg-tertiary">
                  <span>{c.variants.length} variante(s)</span>
                  {c.persona && <span>· persona {c.persona}</span>}
                  {badVariants > 0 ? (
                    <span className="text-argos-warning">· {badVariants} hors limites</span>
                  ) : (
                    <span className="text-argos-healthy">· longueurs OK</span>
                  )}
                </div>
              </button>

              <div className="flex shrink-0 items-center gap-1.5">
                {(c.status === "draft" || c.status === "rejected") && (
                  <Button size="sm" variant="primary" disabled={isBusy} onClick={() => onValidate(c.id)}>
                    valider
                  </Button>
                )}
                {c.status === "validated" && (
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={isBusy || breakerTripped}
                    onClick={() => onGoLive(c.id)}
                    title={breakerTripped ? "Breaker armé — mise en ligne gelée" : "Mettre en ligne (shadow)"}
                  >
                    go live
                  </Button>
                )}
                {(c.status === "draft" || c.status === "validated") && (
                  <Button size="sm" variant="danger" disabled={isBusy} onClick={() => onReject(c.id)}>
                    rejeter
                  </Button>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
