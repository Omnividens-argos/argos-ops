// KB éditoriale éditable : liste des fiches de marque (messages clés, preuves,
// personas) avec création / édition inline / suppression. Chargée comme contexte
// par les skills writers ; éditée ici par le fondateur.

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { MarketingKBEntry } from "../api.ts";
import { Badge, Button, TextInput } from "../../components/ui.tsx";
import { shortDate, slugify } from "./lib.ts";

const TEXTAREA_CLS =
  "w-full rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60";

export interface KBEditorProps {
  entries: MarketingKBEntry[];
  busySlug: string | null;
  onUpsert: (slug: string, patch: { title: string; body: string; tags: string[] }) => void;
  onDelete: (slug: string) => void;
}

function parseTags(csv: string): string[] {
  return csv
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

function EntryForm({
  initial,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  initial: { title: string; body: string; tags: string };
  submitLabel: string;
  onCancel?: () => void;
  onSubmit: (patch: { title: string; body: string; tags: string[] }) => void;
}) {
  const [title, setTitle] = useState(initial.title);
  const [body, setBody] = useState(initial.body);
  const [tags, setTags] = useState(initial.tags);
  const canSubmit = title.trim().length > 0;
  return (
    <div className="flex flex-col gap-2">
      <TextInput placeholder="Titre de la fiche" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea
        className={`${TEXTAREA_CLS} min-h-[90px] resize-y`}
        placeholder="Contenu de la fiche"
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <TextInput
        placeholder="tags (séparés par des virgules)"
        value={tags}
        onChange={(e) => setTags(e.target.value)}
      />
      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          variant="primary"
          disabled={!canSubmit}
          onClick={() => onSubmit({ title: title.trim(), body, tags: parseTags(tags) })}
        >
          {submitLabel}
        </Button>
        {onCancel && (
          <Button size="sm" variant="ghost" onClick={onCancel}>
            annuler
          </Button>
        )}
      </div>
    </div>
  );
}

export function KBEditor({ entries, busySlug, onUpsert, onDelete }: KBEditorProps) {
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
          {entries.length} fiche(s)
        </span>
        {!creating && (
          <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
            <Plus className="mr-0.5 inline h-3 w-3" aria-hidden /> nouvelle fiche
          </Button>
        )}
      </div>

      {creating && (
        <div className="rounded-md border border-argos-info/40 bg-argos-surface px-3 py-3">
          <EntryForm
            initial={{ title: "", body: "", tags: "" }}
            submitLabel="créer"
            onCancel={() => setCreating(false)}
            onSubmit={(patch) => {
              onUpsert(slugify(patch.title), patch);
              setCreating(false);
            }}
          />
        </div>
      )}

      {entries.length === 0 && !creating ? (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
          KB éditoriale vide — crée une première fiche de marque.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => {
            const isEditing = entry.slug === editingSlug;
            return (
              <li
                key={entry.slug}
                className="rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5"
              >
                {isEditing ? (
                  <EntryForm
                    initial={{ title: entry.title, body: entry.body, tags: entry.tags.join(", ") }}
                    submitLabel="enregistrer"
                    onCancel={() => setEditingSlug(null)}
                    onSubmit={(patch) => {
                      onUpsert(entry.slug, patch);
                      setEditingSlug(null);
                    }}
                  />
                ) : (
                  <>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-medium text-argos-fg">
                            {entry.title}
                          </span>
                          {entry.tags.map((t) => (
                            <Badge key={t} tone="neutral">
                              {t}
                            </Badge>
                          ))}
                        </div>
                        <p className="mt-1 line-clamp-3 whitespace-pre-wrap font-mono text-[11px] leading-snug text-argos-fg-secondary">
                          {entry.body}
                        </p>
                        <span className="font-mono text-[10px] text-argos-fg-disabled">
                          maj {shortDate(entry.updated_at)}
                        </span>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <Button size="sm" variant="ghost" onClick={() => setEditingSlug(entry.slug)}>
                          éditer
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          aria-label="supprimer la fiche"
                          disabled={busySlug === entry.slug}
                          onClick={() => onDelete(entry.slug)}
                        >
                          <Trash2 className="inline h-3 w-3" aria-hidden />
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
