// Calendrier éditorial drag-and-drop (HTML5 natif, zéro dépendance). On glisse un
// draft depuis la colonne « à planifier » vers un jour pour le programmer, ou
// d'un jour vers « à planifier » pour le déprogrammer. Seuls les drafts VALIDÉS
// sont planifiables — cohérent avec ContentBot (qui ne publie que les validés
// échus) et avec le compteur counts.scheduled (validés + planifiés). Les drafts
// validés planifiés HORS de la fenêtre de 7 jours (futurs lointains ou en retard
// non encore publiés) restent visibles et manipulables via le bac « hors fenêtre ».

import { useState } from "react";
import { CalendarClock, History } from "lucide-react";
import type { MarketingChannel, MarketingDraft } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { STATUS_TONE, channelLabel, dayKey, dayLabel, scheduleAt, upcomingDays } from "./lib.ts";

const DAYS = 7;
const UNPLANNED = "__unplanned__";

export interface EditorialCalendarProps {
  drafts: MarketingDraft[];
  channels: MarketingChannel[];
  busyId: string | null;
  onSchedule: (id: string, scheduledFor: string | null) => void;
}

function DraftChip({
  draft,
  channels,
  busy,
}: {
  draft: MarketingDraft;
  channels: MarketingChannel[];
  busy: boolean;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", draft.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      className={`cursor-grab rounded-md border border-argos-border-subtle bg-argos-surface px-2 py-1.5 active:cursor-grabbing ${
        busy ? "opacity-50" : ""
      }`}
    >
      <div className="flex items-center gap-1.5">
        <Badge tone={STATUS_TONE[draft.status]}>{channelLabel(channels, draft.channel)}</Badge>
      </div>
      <p className="mt-1 line-clamp-2 font-mono text-[10px] leading-snug text-argos-fg">
        {draft.title}
      </p>
    </div>
  );
}

export function EditorialCalendar({
  drafts,
  channels,
  busyId,
  onSchedule,
}: EditorialCalendarProps) {
  const [overKey, setOverKey] = useState<string | null>(null);

  // Seuls les drafts validés sont planifiables (ContentBot ne publie que ceux-là).
  const schedulable = drafts.filter((d) => d.status === "validated");
  const days = upcomingDays(DAYS);
  const dayKeys = new Set(days.map(dayKey));

  const unplanned = schedulable.filter((d) => !d.scheduled_for);
  const outOfWindow = schedulable.filter(
    (d) => d.scheduled_for && !dayKeys.has(dayKey(new Date(d.scheduled_for))),
  );

  const byDay = new Map<string, MarketingDraft[]>();
  for (const d of schedulable) {
    if (!d.scheduled_for) continue;
    const key = dayKey(new Date(d.scheduled_for));
    if (!dayKeys.has(key)) continue; // hors fenêtre → bac dédié
    const list = byDay.get(key) ?? [];
    list.push(d);
    byDay.set(key, list);
  }

  const handleDrop = (e: React.DragEvent, target: string) => {
    e.preventDefault();
    setOverKey(null);
    const id = e.dataTransfer.getData("text/plain");
    if (!id) return;
    if (target === UNPLANNED) {
      onSchedule(id, null);
      return;
    }
    const day = days.find((d) => dayKey(d) === target);
    if (day) onSchedule(id, scheduleAt(day));
  };

  const dropProps = (key: string) => ({
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      if (overKey !== key) setOverKey(key);
    },
    onDragLeave: () => setOverKey((k) => (k === key ? null : k)),
    onDrop: (e: React.DragEvent) => handleDrop(e, key),
  });

  const cellHighlight = (key: string) =>
    overKey === key ? "border-argos-info/60 bg-argos-info/10" : "border-argos-border-subtle";

  if (schedulable.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucun draft validé à planifier. Valide un draft dans la file pour le programmer ici.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-[200px_1fr]">
      {/* À planifier + hors fenêtre */}
      <div className="flex flex-col gap-3">
        <div
          {...dropProps(UNPLANNED)}
          className={`flex min-h-[120px] flex-col gap-2 rounded-md border bg-argos-surface px-2.5 py-2.5 ${cellHighlight(
            UNPLANNED,
          )}`}
        >
          <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            <CalendarClock className="h-3 w-3" aria-hidden /> à planifier ({unplanned.length})
          </div>
          {unplanned.length === 0 ? (
            <p className="font-mono text-[10px] text-argos-fg-disabled">
              Glisse un draft d'un jour ici pour le déprogrammer.
            </p>
          ) : (
            unplanned.map((d) => (
              <DraftChip key={d.id} draft={d} channels={channels} busy={busyId === d.id} />
            ))
          )}
        </div>

        {outOfWindow.length > 0 && (
          <div className="flex flex-col gap-2 rounded-md border border-argos-warning/40 bg-argos-warning/5 px-2.5 py-2.5">
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-argos-warning">
              <History className="h-3 w-3" aria-hidden /> hors fenêtre / en retard (
              {outOfWindow.length})
            </div>
            {outOfWindow.map((d) => (
              <DraftChip key={d.id} draft={d} channels={channels} busy={busyId === d.id} />
            ))}
          </div>
        )}
      </div>

      {/* Semaine */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {days.map((day) => {
          const key = dayKey(day);
          const items = byDay.get(key) ?? [];
          return (
            <div
              key={key}
              {...dropProps(key)}
              className={`flex min-h-[120px] flex-col gap-1.5 rounded-md border bg-argos-surface px-1.5 py-1.5 ${cellHighlight(
                key,
              )}`}
            >
              <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
                {dayLabel(day)}
              </div>
              {items.map((d) => (
                <DraftChip key={d.id} draft={d} channels={channels} busy={busyId === d.id} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
