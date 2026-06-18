// Composant partagé « file de validation » — drafts produits par un agent en
// attente de validation humaine (email, post social, devis...). Humain-in-the-
// loop (D-017). En S0 : rendu + état vide ; handlers optionnels (désactivés si
// absents). Les sessions pôle passent de vrais `items` + callbacks.

import { Badge, Button } from "../../components/ui.tsx";

export interface QueueItem {
  id: string;
  title: string;
  /** Canal / destination (ex. "linkedin", "email", "devis"). */
  channel: string;
  status: string;
}

export interface ValidationQueueProps {
  items: QueueItem[];
  onValidate?: (id: string) => void;
  onReject?: (id: string) => void;
}

export function ValidationQueue({ items, onValidate, onReject }: ValidationQueueProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        File de validation vide — aucun draft en attente.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((it) => (
        <li
          key={it.id}
          className="flex items-center justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Badge tone="neutral">{it.channel}</Badge>
              <span className="truncate font-mono text-xs text-argos-fg">{it.title}</span>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
              {it.status}
            </span>
          </div>
          <div className="flex shrink-0 gap-1.5">
            <Button
              variant="primary"
              size="sm"
              disabled={!onValidate}
              onClick={onValidate ? () => onValidate(it.id) : undefined}
            >
              valider
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={!onReject}
              onClick={onReject ? () => onReject(it.id) : undefined}
            >
              rejeter
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
