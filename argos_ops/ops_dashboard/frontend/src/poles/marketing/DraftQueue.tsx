// File de validation des drafts éditoriaux — humain-in-the-loop (D-017). Valide /
// rejette / édite inline chaque draft, et le sélectionne pour la preview par
// canal. Un draft `published` est figé (lecture seule).

import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import type { MarketingChannel, MarketingDraft } from "../api.ts";
import { Badge, Button } from "../../components/ui.tsx";
import { STATUS_LABEL, STATUS_TONE, channelLabel } from "./lib.ts";

export interface DraftQueueProps {
  drafts: MarketingDraft[];
  channels: MarketingChannel[];
  selectedId: string | null;
  busyId: string | null;
  onSelect: (id: string) => void;
  onValidate: (id: string) => void;
  onReject: (id: string) => void;
  onEdit: (id: string, patch: { title: string; body: string }) => void;
}

const TEXTAREA_CLS =
  "w-full rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60";

function EditForm({
  draft,
  onCancel,
  onSave,
}: {
  draft: MarketingDraft;
  onCancel: () => void;
  onSave: (patch: { title: string; body: string }) => void;
}) {
  const [title, setTitle] = useState(draft.title);
  const [body, setBody] = useState(draft.body);
  return (
    <div className="flex flex-col gap-2">
      <input
        className={TEXTAREA_CLS}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Titre"
      />
      <textarea
        className={`${TEXTAREA_CLS} min-h-[120px] resize-y`}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Corps du draft"
      />
      <div className="flex items-center gap-1.5">
        <Button size="sm" variant="primary" onClick={() => onSave({ title, body })}>
          enregistrer
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          annuler
        </Button>
      </div>
    </div>
  );
}

export function DraftQueue({
  drafts,
  channels,
  selectedId,
  busyId,
  onSelect,
  onValidate,
  onReject,
  onEdit,
}: DraftQueueProps) {
  const [editingId, setEditingId] = useState<string | null>(null);

  if (drafts.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        File de validation vide — aucun draft. Les writers (skills) en déposent ici.
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {drafts.map((d) => {
        const isSelected = d.id === selectedId;
        const isEditing = d.id === editingId;
        const isBusy = d.id === busyId;
        const frozen = d.status === "published";
        return (
          <li
            key={d.id}
            className={`rounded-md border bg-argos-surface px-3 py-2.5 transition-colors ${
              isSelected ? "border-argos-info/50" : "border-argos-border-subtle"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <button
                type="button"
                onClick={() => onSelect(d.id)}
                className="min-w-0 flex-1 text-left"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={STATUS_TONE[d.status]}>{STATUS_LABEL[d.status]}</Badge>
                  <Badge tone="neutral">{channelLabel(channels, d.channel)}</Badge>
                  <span className="truncate font-mono text-xs font-medium text-argos-fg">
                    {d.title}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-argos-fg-tertiary">
                  <span className={d.length_ok ? "text-argos-healthy" : "text-argos-warning"}>
                    {d.length}
                    {d.max_chars > 0 ? `/${d.max_chars}` : ""} car.
                  </span>
                  {d.scheduled_for && <span>· planifié</span>}
                  {d.source && <span>· {d.source}</span>}
                </div>
              </button>

              {!isEditing && (
                <div className="flex shrink-0 items-center gap-1.5">
                  {!frozen && (d.status === "draft" || d.status === "rejected") && (
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={isBusy}
                      onClick={() => onValidate(d.id)}
                    >
                      <Check className="mr-0.5 inline h-3 w-3" aria-hidden /> valider
                    </Button>
                  )}
                  {!frozen && (d.status === "draft" || d.status === "validated") && (
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={isBusy}
                      onClick={() => onReject(d.id)}
                    >
                      <X className="mr-0.5 inline h-3 w-3" aria-hidden /> rejeter
                    </Button>
                  )}
                  {!frozen && (
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label="éditer le draft"
                      onClick={() => setEditingId(d.id)}
                    >
                      <Pencil className="inline h-3 w-3" aria-hidden />
                    </Button>
                  )}
                </div>
              )}
            </div>

            {isEditing && (
              <div className="mt-2">
                <EditForm
                  draft={d}
                  onCancel={() => setEditingId(null)}
                  onSave={(patch) => {
                    onEdit(d.id, patch);
                    setEditingId(null);
                  }}
                />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
