import { Archive, FileText, Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchAllOutputs,
  fetchOutputContent,
  type InboxDraft,
  type InboxKind,
} from "../api";
import { EmptyState } from "../components/EmptyState";
import { MarkdownPreview } from "../components/MarkdownPreview";
import { SkeletonList } from "../components/Skeleton";
import { Badge, Button, Flash } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { useDensityClasses } from "../hooks/useUserPrefs";
import { formatAbsoluteTime, formatRelativeTime } from "../lib/format";

// Vue Outputs library — bibliothèque consultable de TOUS les drafts produits
// par les bots, peu importe leur statut (pending / validated / rejected /
// posted / sent). Lecture seule — pour réaction immédiate, passer par Inbox.
//
// 3 filtres : kind (catégorie), status, agent (bot). Recherche fulltext sur
// titre + summary + file_path. Click sur une row → modale avec le contenu raw
// du markdown (read-only, frontmatter + body).

type StatusFilter = "all" | "pending" | "validated" | "rejected" | "posted";

const STATUS_LABELS: Record<StatusFilter, string> = {
  all: "Tous",
  pending: "En attente",
  validated: "Validé",
  rejected: "Rejeté",
  posted: "Envoyé / publié",
};

const KIND_LABELS: Record<InboxKind, string> = {
  email: "Email",
  social: "Social",
  proposal: "Devis / contrat",
  seo: "SEO / blog",
  press: "Presse / crisis",
  doc: "Doc interne",
  other: "Autre",
};

export function Outputs() {
  const outputs = usePolling(useCallback((s) => fetchAllOutputs(s), []), 30000);
  const { rowPaddingY } = useDensityClasses();
  const [kindFilter, setKindFilter] = useState<InboxKind | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [agentFilter, setAgentFilter] = useState<string | "all">("all");
  const [query, setQuery] = useState("");
  const [openItem, setOpenItem] = useState<InboxDraft | null>(null);

  const allAgents = useMemo(() => {
    const set = new Set<string>();
    for (const d of outputs.data ?? []) {
      if (d.agent_name) set.add(d.agent_name);
    }
    return Array.from(set).sort();
  }, [outputs.data]);

  const filtered = useMemo(() => {
    const all = outputs.data ?? [];
    const q = query.trim().toLowerCase();
    return all.filter((d) => {
      if (kindFilter !== "all" && d.kind !== kindFilter) return false;
      if (statusFilter !== "all" && !matchStatusFilter(d.status, statusFilter))
        return false;
      if (agentFilter !== "all" && d.agent_name !== agentFilter) return false;
      if (q !== "") {
        const hay = `${d.title} ${d.summary ?? ""} ${d.file_path} ${d.agent_name ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [outputs.data, kindFilter, statusFilter, agentFilter, query]);

  const totalCount = outputs.data?.length ?? 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-argos-fg flex items-center gap-2">
          <Archive size={22} strokeWidth={1.5} className="text-argos-info" />
          Outputs library
        </h1>
        <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
          Tout ce que les bots ont produit — drafts en attente, validés,
          rejetés, envoyés. Recherche fulltext + filtres pour retrouver un
          contenu en quelques secondes.
        </p>
      </header>

      {outputs.error && (
        <Flash
          variant="error"
          message={`Impossible de charger les outputs : ${outputs.error.message}`}
        />
      )}

      {/* Search */}
      <div className="flex items-center gap-2 bg-argos-surface border border-argos-border-subtle rounded-md px-3 py-2">
        <Search size={14} strokeWidth={2} className="text-argos-fg-tertiary shrink-0" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Cherche dans le titre, le résumé, le path, le bot…"
          className="flex-1 bg-transparent text-sm text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none"
        />
        {query !== "" && (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="font-mono text-[10px] text-argos-fg-tertiary hover:text-argos-fg"
          >
            effacer
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="space-y-2">
        <FilterRow label="Catégorie">
          <Chip
            label={`Tous · ${totalCount}`}
            active={kindFilter === "all"}
            onClick={() => setKindFilter("all")}
          />
          {(Object.keys(KIND_LABELS) as InboxKind[]).map((k) => {
            const count = (outputs.data ?? []).filter((d) => d.kind === k).length;
            return (
              <Chip
                key={k}
                label={`${KIND_LABELS[k]} · ${count}`}
                active={kindFilter === k}
                muted={count === 0}
                onClick={() => setKindFilter(k)}
              />
            );
          })}
        </FilterRow>

        <FilterRow label="Statut">
          {(Object.keys(STATUS_LABELS) as StatusFilter[]).map((s) => (
            <Chip
              key={s}
              label={STATUS_LABELS[s]}
              active={statusFilter === s}
              onClick={() => setStatusFilter(s)}
            />
          ))}
        </FilterRow>

        {allAgents.length > 0 && (
          <FilterRow label="Bot">
            <Chip
              label="Tous les bots"
              active={agentFilter === "all"}
              onClick={() => setAgentFilter("all")}
            />
            {allAgents.map((name) => (
              <Chip
                key={name}
                label={name}
                active={agentFilter === name}
                onClick={() => setAgentFilter(name)}
              />
            ))}
          </FilterRow>
        )}
      </div>

      {/* Result list */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
        <header className="px-4 py-2.5 border-b border-argos-border-subtle font-mono text-[11px] text-argos-fg-tertiary flex items-center justify-between">
          <span>
            {filtered.length} résultat{filtered.length > 1 ? "s" : ""} affichés
            {filtered.length < totalCount && ` sur ${totalCount} au total`}
          </span>
          {(kindFilter !== "all" ||
            statusFilter !== "all" ||
            agentFilter !== "all" ||
            query !== "") && (
            <button
              type="button"
              onClick={() => {
                setKindFilter("all");
                setStatusFilter("all");
                setAgentFilter("all");
                setQuery("");
              }}
              className="text-argos-info hover:underline"
            >
              Réinitialiser les filtres
            </button>
          )}
        </header>
        {outputs.data === null ? (
          <div className="p-4">
            <SkeletonList count={4} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-6">
            <EmptyState
              tone="neutral"
              icon={Archive}
              title={
                totalCount === 0
                  ? "Aucun output produit pour l'instant"
                  : "Rien ne correspond à ces filtres"
              }
              body={
                totalCount === 0
                  ? "Quand les bots draftent, leurs productions apparaîtront ici (peu importe le statut). En attendant — la flotte est calme."
                  : "Élargis les filtres ou efface la recherche pour voir plus de drafts."
              }
              compact
            />
          </div>
        ) : (
          <ul className="divide-y divide-argos-border-subtle">
            {filtered.map((item) => (
              <OutputRow
                key={item.id}
                item={item}
                rowPaddingY={rowPaddingY}
                onOpen={() => setOpenItem(item)}
              />
            ))}
          </ul>
        )}
      </section>

      {openItem && (
        <OutputModal item={openItem} onClose={() => setOpenItem(null)} />
      )}
    </div>
  );
}

function matchStatusFilter(status: string, filter: StatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "pending") {
    return ["draft", "drafted", "pending", "pending_review", "needs_review", "queued", "scheduled"].includes(
      status,
    );
  }
  if (filter === "validated") return status === "validated";
  if (filter === "rejected") return status === "rejected";
  if (filter === "posted") {
    return ["posted", "sent", "published", "signed"].includes(status);
  }
  return false;
}

// =============================================================================
// Filter row + Chip
// =============================================================================
function FilterRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 flex-wrap">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary pt-1.5 shrink-0">
        {label}
      </span>
      <div className="flex items-center gap-1.5 flex-wrap">{children}</div>
    </div>
  );
}

function Chip({
  label,
  active,
  muted,
  onClick,
}: {
  label: string;
  active: boolean;
  muted?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`font-mono text-[11px] px-2.5 py-1 rounded-md border transition-colors ${
        active
          ? "bg-argos-info/15 border-argos-info/40 text-argos-info"
          : muted
            ? "bg-argos-surface border-argos-border-subtle text-argos-fg-disabled hover:text-argos-fg-tertiary"
            : "bg-argos-surface border-argos-border-subtle text-argos-fg-secondary hover:bg-argos-surface-2"
      }`}
    >
      {label}
    </button>
  );
}

// =============================================================================
// Output row
// =============================================================================
function OutputRow({
  item,
  rowPaddingY,
  onOpen,
}: {
  item: InboxDraft;
  rowPaddingY: string;
  onOpen: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className={`w-full text-left px-4 ${rowPaddingY} hover:bg-argos-surface-2/50 transition-colors`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-sm text-argos-fg truncate font-medium">
              {item.title}
            </div>
            {item.summary && (
              <div className="mt-1 text-xs text-argos-fg-secondary line-clamp-1">
                {item.summary}
              </div>
            )}
            <div className="mt-1.5 flex items-center gap-2 flex-wrap font-mono text-[10px] text-argos-fg-tertiary">
              <span>{KIND_LABELS[item.kind]}</span>
              <span>·</span>
              <span>{formatRelativeTime(item.created_at)}</span>
              <span>·</span>
              <span className="truncate">{item.file_path}</span>
              {item.agent_name && (
                <>
                  <span>·</span>
                  <span>{item.agent_name}</span>
                </>
              )}
            </div>
          </div>
          <Badge tone={statusToTone(item.status)}>{item.status}</Badge>
        </div>
      </button>
    </li>
  );
}

function statusToTone(status: string): "healthy" | "warning" | "info" | "danger" | "neutral" {
  switch (status) {
    case "validated":
    case "posted":
    case "sent":
    case "published":
    case "signed":
      return "healthy";
    case "pending_review":
    case "scheduled":
      return "warning";
    case "rejected":
    case "killed":
      return "danger";
    case "draft":
    case "drafted":
    case "pending":
      return "info";
    default:
      return "neutral";
  }
}

// =============================================================================
// Content modal
// =============================================================================
function OutputModal({
  item,
  onClose,
}: {
  item: InboxDraft;
  onClose: () => void;
}) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Fetch content au mount + esc ferme la modal.
  useEffect(() => {
    const controller = new AbortController();
    fetchOutputContent(item.file_path, controller.signal)
      .then((r) => setContent(r.content))
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError((e as Error).message);
      });
    return () => controller.abort();
  }, [item.file_path]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copyPath = () => {
    navigator.clipboard
      .writeText(item.file_path)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => undefined);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-0 bg-argos-bg/70 backdrop-blur-[2px]" />
      <div
        className="relative w-full max-w-3xl max-h-[85vh] bg-argos-surface border border-argos-border rounded-lg shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-3 border-b border-argos-border-subtle flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <FileText size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
              <h2 className="text-sm font-semibold text-argos-fg truncate">
                {item.title}
              </h2>
              <Badge tone={statusToTone(item.status)}>{item.status}</Badge>
            </div>
            <div className="font-mono text-[10px] text-argos-fg-tertiary truncate">
              {item.file_path} · {item.agent_name ?? "—"} ·{" "}
              {formatAbsoluteTime(item.created_at)}
            </div>
          </div>
          <div className="shrink-0 flex items-center gap-1.5">
            <Button size="sm" variant="ghost" onClick={copyPath}>
              {copied ? "copié ✓" : "copier path"}
            </Button>
            <button
              type="button"
              onClick={onClose}
              className="font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg flex items-center gap-1"
            >
              <X size={12} strokeWidth={2} />
              esc
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          {error ? (
            <div className="p-5">
              <Flash variant="error" message={error} />
            </div>
          ) : content === null ? (
            <div className="p-5">
              <EmptyState tone="loading" title="Lecture du fichier…" compact />
            </div>
          ) : (
            <div className="px-5 py-4">
              <MarkdownPreview content={content} />
            </div>
          )}
        </div>

        <footer className="px-5 py-2 border-t border-argos-border-subtle bg-argos-surface-2/40 font-mono text-[10px] text-argos-fg-tertiary">
          Lecture seule depuis le panel. Pour éditer, ouvre le fichier dans
          ton IDE (chemin ci-dessus).
        </footer>
      </div>
    </div>
  );
}
