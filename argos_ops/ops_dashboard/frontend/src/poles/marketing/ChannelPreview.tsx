// Preview par canal d'un draft sélectionné : rendu du corps tel qu'il paraîtra,
// avec compteur de caractères vs la contrainte du canal (length_ok). Aide à
// valider qu'un post LinkedIn est assez long, qu'un post X tient en 280, etc.

import type { MarketingChannel, MarketingDraft } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { channelById } from "./lib.ts";

export interface ChannelPreviewProps {
  draft: MarketingDraft | null;
  channels: MarketingChannel[];
}

export function ChannelPreview({ draft, channels }: ChannelPreviewProps) {
  if (!draft) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Sélectionne un draft pour le prévisualiser par canal.
      </div>
    );
  }
  const channel = channelById(channels, draft.channel);
  const max = channel?.max_chars ?? 0;
  const min = channel?.min_chars ?? 0;
  // On fait confiance au compteur backend (code points Python, comme length_ok),
  // pas à draft.body.length (UTF-16 en JS) — sinon un emoji astral fait diverger
  // la preview de la file de validation.
  const len = draft.length;
  const over = max > 0 && len > max;
  const under = len < min;
  const countTone = over || under ? "text-argos-danger" : "text-argos-healthy";

  return (
    <div className="flex flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone="info">{channel?.label ?? draft.channel}</Badge>
          <span className="truncate font-mono text-xs font-medium text-argos-fg">
            {draft.title}
          </span>
        </div>
        <span className={`font-mono text-[11px] ${countTone}`}>
          {len}
          {max > 0 ? ` / ${max}` : ""} car.
        </span>
      </div>

      <div className="rounded-md border border-argos-border-subtle bg-argos-bg px-3 py-2.5">
        <p className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-argos-fg">
          {draft.body || "(corps vide)"}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] text-argos-fg-tertiary">
        {draft.writer && <Badge tone="neutral">{draft.writer}</Badge>}
        {over && <span className="text-argos-danger">dépasse la limite du canal</span>}
        {under && !over && (
          <span className="text-argos-warning">
            sous le minimum recommandé ({min} car.)
          </span>
        )}
        {!over && !under && <span className="text-argos-healthy">longueur conforme au canal</span>}
      </div>
    </div>
  );
}
