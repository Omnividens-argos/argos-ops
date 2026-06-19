// DataTable<T> — table générique triable, paginée ou virtualisée.
//
// Une seule abstraction de tableau pour tout le cockpit (runs, leads, deals,
// factures, mémoire de flotte…). Tri par colonne (numérique ou localeCompare),
// pagination classique OU virtualisation react-window pour les grosses listes,
// états loading (Skeleton) et vide (EmptyState) intégrés.
//
// Accessibilité : <table> sémantique en mode paginé (aria-sort sur les <th>
// triables, header bouton clavier-navigable). En mode virtualisé on bascule
// sur des role="row"/"cell" car react-window impose des <div> positionnés.

import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { ArrowUpDown, ChevronDown, ChevronUp } from "lucide-react";
import { FixedSizeList } from "react-window";
import { SkeletonList } from "./Skeleton.tsx";
import { EmptyState } from "./EmptyState.tsx";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  align?: "left" | "right";
  mono?: boolean;
  className?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  onRowClick?: (row: T) => void;
  initialSortKey?: string;
  pageSize?: number;
  virtualize?: boolean;
  rowHeight?: number;
  loading?: boolean;
  emptyTitle?: string;
  emptyBody?: string;
  ariaLabel?: string;
}

type SortDir = "asc" | "desc";

const HEADER_CLASS =
  "font-mono text-[11px] uppercase tracking-wider text-argos-fg-tertiary " +
  "sticky top-0 bg-argos-surface";

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg";

function cellClass<T>(col: Column<T>): string {
  const align = col.align === "right" ? "text-right" : "text-left";
  const mono = col.mono ? "font-mono tabular-nums" : "";
  return `px-3 py-2 text-sm ${align} ${mono} ${col.className ?? ""}`.trim();
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  onRowClick,
  initialSortKey,
  pageSize = 25,
  virtualize = false,
  rowHeight = 40,
  loading = false,
  emptyTitle,
  emptyBody,
  ariaLabel,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | undefined>(initialSortKey);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return rows;
    const getValue = col.sortValue;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = getValue(a);
      const vb = getValue(b);
      if (typeof va === "number" && typeof vb === "number") {
        return (va - vb) * dir;
      }
      return String(va).localeCompare(String(vb)) * dir;
    });
  }, [rows, columns, sortKey, sortDir]);

  const toggleSort = (col: Column<T>) => {
    if (!col.sortValue) return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col.key);
      setSortDir("asc");
    }
    setPage(0);
  };

  const ariaSortFor = (col: Column<T>): "ascending" | "descending" | "none" => {
    if (!col.sortValue || sortKey !== col.key) return "none";
    return sortDir === "asc" ? "ascending" : "descending";
  };

  const handleRowKeyDown = (
    event: React.KeyboardEvent<HTMLElement>,
    row: T,
  ) => {
    if (!onRowClick) return;
    if (event.key === "Enter") {
      event.preventDefault();
      onRowClick(row);
    }
  };

  if (loading) {
    return <SkeletonList count={pageSize} />;
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        tone="neutral"
        title={emptyTitle ?? "Aucune donnée"}
        body={emptyBody}
      />
    );
  }

  // Header cell rendered identically for both modes.
  const headerCell = (col: Column<T>) => {
    const align = col.align === "right" ? "text-right" : "text-left";
    const sortable = Boolean(col.sortValue);
    const active = sortKey === col.key;
    const Icon = !active ? ArrowUpDown : sortDir === "asc" ? ChevronUp : ChevronDown;
    if (!sortable) {
      return <span className={`px-3 py-2 inline-block ${align}`}>{col.header}</span>;
    }
    return (
      <button
        type="button"
        onClick={() => toggleSort(col)}
        className={`group inline-flex items-center gap-1 px-3 py-2 w-full rounded-sm uppercase tracking-wider hover:text-argos-fg-secondary transition-colors ${align === "text-right" ? "justify-end" : ""} ${FOCUS_RING}`}
      >
        <span>{col.header}</span>
        <Icon
          size={12}
          strokeWidth={2}
          className={active ? "text-argos-info" : "text-argos-fg-disabled"}
          aria-hidden="true"
        />
      </button>
    );
  };

  // ===========================================================================
  // Virtualized mode — react-window FixedSizeList of role="row" divs.
  // ===========================================================================
  if (virtualize) {
    const listHeight = rowHeight * Math.min(sortedRows.length, 12);
    return (
      <div
        role="table"
        aria-label={ariaLabel}
        aria-rowcount={sortedRows.length}
        className="rounded-md border border-argos-border-subtle overflow-hidden"
      >
        <div
          role="row"
          className={`flex ${HEADER_CLASS} border-b border-argos-border-subtle z-10`}
        >
          {columns.map((col) => (
            <div
              key={col.key}
              role="columnheader"
              aria-sort={ariaSortFor(col)}
              className="flex-1 min-w-0"
            >
              {headerCell(col)}
            </div>
          ))}
        </div>
        <FixedSizeList
          height={listHeight}
          itemSize={rowHeight}
          itemCount={sortedRows.length}
          width="100%"
        >
          {({ index, style }: { index: number; style: CSSProperties }) => {
            const row = sortedRows[index];
            return (
              <div
                role="row"
                key={getRowId(row)}
                style={style}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={(e) => handleRowKeyDown(e, row)}
                className={`flex items-center border-b border-argos-border-subtle text-argos-fg hover:bg-argos-surface-2 transition-colors ${onRowClick ? `cursor-pointer ${FOCUS_RING}` : ""}`}
              >
                {columns.map((col) => (
                  <div
                    key={col.key}
                    role="cell"
                    className={`flex-1 min-w-0 truncate ${cellClass(col)}`}
                  >
                    {col.render ? col.render(row) : null}
                  </div>
                ))}
              </div>
            );
          }}
        </FixedSizeList>
      </div>
    );
  }

  // ===========================================================================
  // Paginated mode — semantic <table>.
  // ===========================================================================
  const total = sortedRows.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const start = safePage * pageSize;
  const end = Math.min(start + pageSize, total);
  const pageRows = sortedRows.slice(start, end);

  return (
    <div className="rounded-md border border-argos-border-subtle overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse" aria-label={ariaLabel}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={ariaSortFor(col)}
                  className={`${HEADER_CLASS} z-10 border-b border-argos-border-subtle p-0 text-left`}
                >
                  {headerCell(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr
                key={getRowId(row)}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={(e) => handleRowKeyDown(e, row)}
                className={`border-b border-argos-border-subtle text-argos-fg hover:bg-argos-surface-2 transition-colors ${onRowClick ? `cursor-pointer ${FOCUS_RING}` : ""}`}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cellClass(col)}>
                    {col.render ? col.render(row) : null}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > pageSize && (
        <div className="flex items-center justify-between gap-3 border-t border-argos-border-subtle bg-argos-surface px-3 py-2">
          <span className="font-mono text-[11px] tabular-nums text-argos-fg-tertiary">
            {start + 1}–{end} / {total}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={safePage <= 0}
              onClick={() => setPage(safePage - 1)}
              className={`font-mono text-[11px] rounded-md border border-argos-border-subtle bg-argos-surface-2 px-2 py-1 text-argos-fg-secondary transition-colors hover:text-argos-fg disabled:opacity-40 disabled:cursor-not-allowed ${FOCUS_RING}`}
            >
              ‹ Préc.
            </button>
            <button
              type="button"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage(safePage + 1)}
              className={`font-mono text-[11px] rounded-md border border-argos-border-subtle bg-argos-surface-2 px-2 py-1 text-argos-fg-secondary transition-colors hover:text-argos-fg disabled:opacity-40 disabled:cursor-not-allowed ${FOCUS_RING}`}
            >
              Suiv. ›
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
