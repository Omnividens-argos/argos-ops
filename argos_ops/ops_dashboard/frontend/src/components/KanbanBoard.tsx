// KanbanBoard — tableau Kanban générique, accessible et drag & drop (@dnd-kit).
// Contrôlé : le parent détient l'état (optimiste). Aucune mutation interne.
// Clavier : Tab pour focus une carte, Espace pour saisir, flèches pour cibler
// une colonne, Espace/Entrée pour déposer (KeyboardSensor @dnd-kit).

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
import type { ReactNode } from "react";

import { Badge } from "./ui.tsx";

// =============================================================================
// Types publics
// =============================================================================
export type KanbanAccent =
  | "neutral"
  | "healthy"
  | "info"
  | "warning"
  | "danger";

export interface KanbanColumn {
  id: string;
  title: string;
  accent?: KanbanAccent;
}

export interface KanbanItem {
  id: string;
  columnId: string;
}

export interface KanbanBoardProps<T extends KanbanItem> {
  columns: KanbanColumn[];
  items: T[];
  renderCard: (item: T) => ReactNode;
  onMove: (itemId: string, toColumnId: string) => void;
}

// =============================================================================
// Mapping accent -> tone du Badge (le Badge partage le même vocabulaire).
// =============================================================================
const ACCENT_TONE: Record<
  KanbanAccent,
  "neutral" | "healthy" | "info" | "warning" | "danger"
> = {
  neutral: "neutral",
  healthy: "healthy",
  info: "info",
  warning: "warning",
  danger: "danger",
};

// Liseré coloré en tête de colonne, par accent.
const ACCENT_RAIL: Record<KanbanAccent, string> = {
  neutral: "bg-argos-border",
  healthy: "bg-argos-healthy",
  info: "bg-argos-info",
  warning: "bg-argos-warning",
  danger: "bg-argos-danger",
};

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg";

// =============================================================================
// DraggableCard — une carte saisissable
// =============================================================================
function DraggableCard({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform) }}
      className={`rounded-md border border-argos-border-subtle bg-argos-surface p-2 cursor-grab active:cursor-grabbing transition-shadow ${FOCUS_RING} ${
        isDragging
          ? "opacity-60 shadow-lg ring-1 ring-argos-info/40"
          : "hover:border-argos-border"
      }`}
      {...listeners}
      {...attributes}
      aria-roledescription="carte déplaçable"
    >
      {children}
    </div>
  );
}

// =============================================================================
// Column — zone de dépôt qui liste ses cartes
// =============================================================================
function Column<T extends KanbanItem>({
  column,
  items,
  renderCard,
}: {
  column: KanbanColumn;
  items: T[];
  renderCard: (item: T) => ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const accent = column.accent ?? "neutral";
  const cards = items.filter((item) => item.columnId === column.id);

  return (
    <section
      aria-label={`Colonne ${column.title}, ${cards.length} carte${
        cards.length === 1 ? "" : "s"
      }`}
      className="flex min-w-[16rem] max-w-[18rem] flex-shrink-0 flex-col rounded-lg border border-argos-border bg-argos-surface-2"
    >
      <header className="flex items-center gap-2 border-b border-argos-border-subtle px-3 py-2">
        <span
          aria-hidden="true"
          className={`h-3 w-1 flex-shrink-0 rounded-full ${ACCENT_RAIL[accent]}`}
        />
        <h3 className="flex-1 truncate text-xs font-medium text-argos-fg">
          {column.title}
        </h3>
        <Badge tone={ACCENT_TONE[accent]}>{cards.length}</Badge>
      </header>

      <div
        ref={setNodeRef}
        className={`flex flex-1 flex-col gap-2 p-2 transition-colors ${
          isOver ? "bg-argos-info/10" : ""
        }`}
      >
        {cards.length === 0 ? (
          <div
            className={`flex flex-1 items-center justify-center rounded-md border border-dashed px-3 py-6 text-center font-mono text-[11px] transition-colors ${
              isOver
                ? "border-argos-info/60 text-argos-info"
                : "border-argos-border-subtle text-argos-fg-tertiary"
            }`}
          >
            {isOver ? "Déposer ici" : "Vide"}
          </div>
        ) : (
          cards.map((item) => (
            <DraggableCard key={item.id} id={item.id}>
              {renderCard(item)}
            </DraggableCard>
          ))
        )}
      </div>
    </section>
  );
}

// =============================================================================
// KanbanBoard — composant exporté
// =============================================================================
export function KanbanBoard<T extends KanbanItem>({
  columns,
  items,
  renderCard,
  onMove,
}: KanbanBoardProps<T>) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || typeof over.id !== "string") return;

    const itemId = String(active.id);
    const toColumnId = String(over.id);
    const source = items.find((item) => item.id === itemId);
    // Pas de déplacement si la carte est déjà dans la colonne cible.
    if (source && source.columnId === toColumnId) return;

    onMove(itemId, toColumnId);
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {columns.map((column) => (
          <Column
            key={column.id}
            column={column}
            items={items}
            renderCard={renderCard}
          />
        ))}
      </div>
    </DndContext>
  );
}
