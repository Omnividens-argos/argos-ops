// Preview FIDÈLE par canal d'un draft sélectionné : carte aux codes visuels de
// la plateforme (avatar + handle, corps en typo sociale qui s'enroule, troncature
// réaliste « …voir plus », mise en valeur des #hashtags / @mentions / liens), plus
// le compteur de caractères vs la contrainte du canal (length_ok). Aide à valider
// qu'un post LinkedIn est assez long, qu'un post X tient en 280, etc.

import { useMemo, useState } from "react";

import type { MarketingChannel, MarketingDraft } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { channelById } from "./lib.ts";

export interface ChannelPreviewProps {
  draft: MarketingDraft | null;
  channels: MarketingChannel[];
}

// --- Config visuelle par canal ----------------------------------------------
// previewCutoff = nb de caractères affichés avant l'affordance « …voir plus ».
// undefined → on retombe sur max_chars (le canal n'a pas de pli court spécifique).
interface ChannelVisual {
  label: string;
  avatarInitial: string;
  handle: string;
  // Classes Tailwind de l'avatar (fond + texte) — couleur de marque approchée.
  avatarClass: string;
  previewCutoff?: number;
}

const CHANNEL_VISUALS: Record<string, ChannelVisual> = {
  linkedin: {
    label: "LinkedIn",
    avatarInitial: "A",
    handle: "Argos · Omnividens",
    avatarClass: "bg-[#0a66c2] text-white",
    previewCutoff: 210,
  },
  mastodon: {
    label: "Mastodon",
    avatarInitial: "A",
    handle: "@argos@infosec.exchange",
    avatarClass: "bg-[#6364ff] text-white",
  },
  meta: {
    label: "Facebook",
    avatarInitial: "A",
    handle: "Argos",
    avatarClass: "bg-[#1877f2] text-white",
  },
  x: {
    label: "X",
    avatarInitial: "A",
    handle: "@argos_secu",
    avatarClass: "bg-argos-fg text-argos-bg",
  },
  twitter: {
    label: "X",
    avatarInitial: "A",
    handle: "@argos_secu",
    avatarClass: "bg-argos-fg text-argos-bg",
  },
  bluesky: {
    label: "Bluesky",
    avatarInitial: "A",
    handle: "@argos.bsky.social",
    avatarClass: "bg-[#0085ff] text-white",
  },
  truth: {
    label: "Truth Social",
    avatarInitial: "A",
    handle: "@argos",
    avatarClass: "bg-[#5448ee] text-white",
  },
};

const FALLBACK_VISUAL: ChannelVisual = {
  label: "Canal",
  avatarInitial: "A",
  handle: "Argos",
  avatarClass: "bg-argos-surface-2 text-argos-fg",
};

// --- Mise en valeur des entités sociales -------------------------------------
// On colore les #hashtags, @mentions et URLs en argos-info, le reste en argos-fg.
// Split sur les frontières de mots/URL ; on garde les séparateurs (espaces,
// ponctuation, retours ligne) intacts pour préserver la mise en forme.
const ENTITY_RE = /(https?:\/\/[^\s]+|www\.[^\s]+|[#@][\p{L}\p{N}_]+)/gu;

function highlightBody(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = new RegExp(ENTITY_RE);
  let last = 0;
  let key = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    const start = match.index;
    if (start > last) {
      out.push(text.slice(last, start));
    }
    out.push(
      <span key={key++} className="text-argos-info">
        {match[0]}
      </span>,
    );
    last = start + match[0].length;
  }
  if (last < text.length) {
    out.push(text.slice(last));
  }
  return out;
}

export function ChannelPreview({ draft, channels }: ChannelPreviewProps) {
  const [expanded, setExpanded] = useState(false);

  const channel = draft ? channelById(channels, draft.channel) : undefined;
  const visual = draft
    ? (CHANNEL_VISUALS[draft.channel] ?? FALLBACK_VISUAL)
    : FALLBACK_VISUAL;

  const max = channel?.max_chars ?? draft?.max_chars ?? 0;
  const min = channel?.min_chars ?? 0;
  // On fait confiance au compteur backend (code points Python, comme length_ok),
  // pas à draft.body.length (UTF-16 en JS) — sinon un emoji astral fait diverger
  // la preview de la file de validation.
  const len = draft?.length ?? 0;
  const over = max > 0 && len > max;
  const under = len < min;
  const countTone = over || under ? "text-argos-danger" : "text-argos-healthy";

  // Pli de troncature : LinkedIn replie tôt (~210 car.), les autres au max canal.
  const cutoff = visual.previewCutoff ?? (max > 0 ? max : undefined);
  const body = draft?.body ?? "";
  const needsTruncation = cutoff !== undefined && body.length > cutoff;

  const shown = useMemo(() => {
    if (!needsTruncation || expanded || cutoff === undefined) return body;
    // On coupe à la dernière frontière de mot avant le pli pour éviter de
    // tronquer au milieu d'un hashtag/mention.
    const slice = body.slice(0, cutoff);
    const lastSpace = slice.lastIndexOf(" ");
    return lastSpace > cutoff * 0.6 ? slice.slice(0, lastSpace) : slice;
  }, [body, cutoff, expanded, needsTruncation]);

  if (!draft) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Sélectionne un draft pour le prévisualiser par canal.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone="info">{channel?.label ?? visual.label}</Badge>
          <span className="truncate font-mono text-xs font-medium text-argos-fg">
            {draft.title}
          </span>
        </div>
        <span className={`font-mono text-[11px] tabular-nums ${countTone}`}>
          {len}
          {max > 0 ? ` / ${max}` : ""} car.
        </span>
      </div>

      {/* Carte stylée à la plateforme : avatar + handle, corps en typo sociale. */}
      <div className="rounded-lg border border-argos-border-subtle bg-argos-bg px-3 py-3">
        <div className="mb-2 flex items-center gap-2">
          <span
            aria-hidden="true"
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${visual.avatarClass}`}
          >
            {visual.avatarInitial}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold leading-tight text-argos-fg">
              {visual.label}
            </p>
            <p className="truncate font-mono text-[10px] leading-tight text-argos-fg-tertiary">
              {visual.handle}
            </p>
          </div>
        </div>

        <p className="whitespace-pre-wrap break-words font-sans text-[13px] leading-relaxed text-argos-fg">
          {body ? highlightBody(shown) : <span className="text-argos-fg-tertiary">(corps vide)</span>}
          {needsTruncation && !expanded && (
            <>
              <span aria-hidden="true">… </span>
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className="font-sans text-[13px] font-medium text-argos-fg-secondary hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
              >
                voir plus
              </button>
            </>
          )}
        </p>

        {needsTruncation && expanded && (
          <button
            type="button"
            onClick={() => setExpanded(false)}
            className="mt-1 font-sans text-[12px] font-medium text-argos-fg-secondary hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
          >
            voir moins
          </button>
        )}
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
