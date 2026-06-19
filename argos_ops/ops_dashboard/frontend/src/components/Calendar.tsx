// Calendrier mensuel (grille 6x7, lundi-first) avec events draggables.
// Drag & drop via @dnd-kit/core ; tons couleur mappés sur les tokens Argos.
// Source design : docs/UI_DECISIONS.md + tokens dual light/dark.
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

export interface CalendarEvent {
  id: string;
  date: string; // "YYYY-MM-DD"
  title: string;
  tone?: "neutral" | "healthy" | "info" | "warning" | "danger";
}

export interface CalendarProps {
  events: CalendarEvent[];
  onMoveEvent?: (id: string, toDateISO: string) => void;
  onSelectEvent?: (id: string) => void;
  initialMonth?: string; // "YYYY-MM-01"
  renderEvent?: (e: CalendarEvent) => ReactNode;
}

type Tone = NonNullable<CalendarEvent["tone"]>;

// Chip soft fill + texte ton (cohérent avec tones.ts / StatusPill).
const CHIP_TONE: Record<Tone, string> = {
  neutral: "bg-argos-surface-2 text-argos-fg-secondary border-argos-border-subtle",
  healthy: "bg-argos-healthy/15 text-argos-healthy border-argos-healthy/30",
  info: "bg-argos-info/15 text-argos-info border-argos-info/30",
  warning: "bg-argos-warning/15 text-argos-warning border-argos-warning/30",
  danger: "bg-argos-danger/15 text-argos-danger border-argos-danger/30",
};

const WEEKDAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"] as const;
const MONTHS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
] as const;

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}

function isoDay(year: number, month0: number, day: number): string {
  return `${year}-${pad2(month0 + 1)}-${pad2(day)}`;
}

// Index lundi-first : JS getDay() => 0=dim..6=sam ; on veut 0=lun..6=dim.
function mondayIndex(jsDay: number): number {
  return (jsDay + 6) % 7;
}

interface GridCell {
  iso: string;
  day: number;
  inMonth: boolean;
  isToday: boolean;
}

function buildGrid(anchor: Date, todayIso: string): GridCell[] {
  const year = anchor.getFullYear();
  const month0 = anchor.getMonth();
  const firstOfMonth = new Date(year, month0, 1);
  const offset = mondayIndex(firstOfMonth.getDay()); // jours à reculer pour le lundi
  const start = new Date(year, month0, 1 - offset);

  const cells: GridCell[] = [];
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const iso = isoDay(d.getFullYear(), d.getMonth(), d.getDate());
    cells.push({
      iso,
      day: d.getDate(),
      inMonth: d.getMonth() === month0,
      isToday: iso === todayIso,
    });
  }
  return cells;
}

function parseAnchor(initialMonth: string | undefined): Date {
  if (initialMonth) {
    const m = /^(\d{4})-(\d{2})/.exec(initialMonth);
    if (m) {
      return new Date(Number(m[1]), Number(m[2]) - 1, 1);
    }
  }
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1);
}

interface ChipProps {
  event: CalendarEvent;
  draggable: boolean;
  onSelect?: (id: string) => void;
  render?: (e: CalendarEvent) => ReactNode;
}

function EventChip({ event, draggable, onSelect, render }: ChipProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: event.id,
    disabled: !draggable,
  });

  const tone: Tone = event.tone ?? "neutral";
  const body: ReactNode = render ? render(event) : event.title;

  const base =
    "w-full text-left truncate rounded px-1.5 py-0.5 text-[11px] leading-tight border transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg";
  const cursor = draggable ? "cursor-grab active:cursor-grabbing" : "cursor-pointer";

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : undefined,
    touchAction: "none",
  };

  return (
    <button
      ref={setNodeRef}
      type="button"
      style={style}
      className={`${base} ${cursor} ${CHIP_TONE[tone]}`}
      onClick={() => onSelect?.(event.id)}
      title={event.title}
      {...(draggable ? listeners : {})}
      {...attributes}
    >
      {body}
    </button>
  );
}

interface DayCellProps {
  cell: GridCell;
  events: CalendarEvent[];
  draggable: boolean;
  onSelect?: (id: string) => void;
  render?: (e: CalendarEvent) => ReactNode;
}

function DayCell({ cell, events, draggable, onSelect, render }: DayCellProps) {
  const { setNodeRef, isOver } = useDroppable({ id: cell.iso });

  const ring = cell.isToday ? "ring-1 ring-argos-info/40" : "";
  const over = isOver ? "bg-argos-info/10" : "";
  const dayColor = cell.inMonth ? "text-argos-fg-secondary" : "text-argos-fg-disabled";

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[88px] border-r border-b border-argos-border-subtle p-1 last:border-r-0 bg-argos-surface transition-colors duration-150 ${ring} ${over}`}
      aria-label={cell.iso}
    >
      <div className={`mb-1 px-0.5 text-right font-mono text-[11px] tabular-nums ${dayColor}`}>
        {pad2(cell.day)}
      </div>
      <div className="flex flex-col gap-0.5">
        {events.map((ev) => (
          <EventChip
            key={ev.id}
            event={ev}
            draggable={draggable}
            onSelect={onSelect}
            render={render}
          />
        ))}
      </div>
    </div>
  );
}

export function Calendar({
  events,
  onMoveEvent,
  onSelectEvent,
  initialMonth,
  renderEvent,
}: CalendarProps) {
  const [anchor, setAnchor] = useState<Date>(() => parseAnchor(initialMonth));

  const now = new Date();
  const todayIso = isoDay(now.getFullYear(), now.getMonth(), now.getDate());
  const grid = buildGrid(anchor, todayIso);
  const draggable = Boolean(onMoveEvent);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  const eventsByDay = new Map<string, CalendarEvent[]>();
  for (const ev of events) {
    const bucket = eventsByDay.get(ev.date);
    if (bucket) {
      bucket.push(ev);
    } else {
      eventsByDay.set(ev.date, [ev]);
    }
  }

  const goPrev = () => setAnchor((a) => new Date(a.getFullYear(), a.getMonth() - 1, 1));
  const goNext = () => setAnchor((a) => new Date(a.getFullYear(), a.getMonth() + 1, 1));

  const handleDragEnd = (e: DragEndEvent) => {
    if (!onMoveEvent) return;
    const activeId = String(e.active.id);
    const over = e.over;
    if (!over) return;
    const toDateISO = String(over.id);
    onMoveEvent(activeId, toDateISO);
  };

  const monthLabel = `${MONTHS[anchor.getMonth()]} ${anchor.getFullYear()}`;
  const navBtn =
    "inline-flex h-8 w-8 items-center justify-center rounded-md border border-argos-border text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg";

  return (
    <div className="rounded-md border border-argos-border bg-argos-bg">
      <header className="flex items-center justify-between gap-2 px-3 py-2.5">
        <h2 className="font-sans text-sm font-medium capitalize text-argos-fg">{monthLabel}</h2>
        <div className="flex items-center gap-1">
          <button type="button" className={navBtn} onClick={goPrev} aria-label="Mois précédent">
            <ChevronLeft size={16} strokeWidth={2.25} />
          </button>
          <button type="button" className={navBtn} onClick={goNext} aria-label="Mois suivant">
            <ChevronRight size={16} strokeWidth={2.25} />
          </button>
        </div>
      </header>

      <div
        className="grid grid-cols-7 border-t border-argos-border-subtle bg-argos-surface-2"
        role="row"
      >
        {WEEKDAYS.map((wd) => (
          <div
            key={wd}
            role="columnheader"
            className="border-b border-argos-border-subtle px-1 py-1.5 text-center font-sans text-[11px] font-medium uppercase tracking-wide text-argos-fg-tertiary"
          >
            {wd}
          </div>
        ))}
      </div>

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-7 border-l border-argos-border-subtle">
          {grid.map((cell) => (
            <DayCell
              key={cell.iso}
              cell={cell}
              events={eventsByDay.get(cell.iso) ?? []}
              draggable={draggable}
              onSelect={onSelectEvent}
              render={renderEvent}
            />
          ))}
        </div>
      </DndContext>
    </div>
  );
}
