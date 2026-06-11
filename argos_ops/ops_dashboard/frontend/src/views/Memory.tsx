// Vue Mémoire — le « Memory Hub » de la flotte (raccourci 8).
//
// Toute la mémoire de flotte, tous bots confondus, en un seul espace de
// contrôle : recherche fulltext + filtres (bot / kind / statut / épinglés),
// et actions manuelles sur chaque fait — épingler (jamais nettoyé par
// MemoryCurator), archiver (soft delete), restaurer, supprimer (hard delete,
// confirmation 2 temps). L'ajout d'un fait se fait ici aussi, pour n'importe
// quel bot du catalogue.

import {
  Archive,
  ArchiveRestore,
  Brain,
  History,
  Pin,
  PinOff,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FactRow, FleetMemoryView } from "../api";
import {
  appendAgentFact,
  archiveAgentFact,
  deleteFleetFact,
  fetchFleetMemory,
  pinFleetFact,
  restoreFleetFact,
} from "../api";
import { EmptyState } from "../components/EmptyState";
import { FactProvenanceModal } from "../components/FactProvenanceModal";
import { SkeletonList } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { Badge, Button, Flash } from "../components/ui";
import { flattenActiveAgents } from "../lib/agentCatalog";
import { factFreshness, formatRelativeTime } from "../lib/format";
import { KpiCard } from "./bot/shared";

type StatusFilter = "all" | "active" | "archived" | "pinned";

const STATUS_LABELS: Record<StatusFilter, string> = {
  all: "Tous",
  active: "Actifs",
  archived: "Archivés",
  pinned: "Épinglés",
};

export function Memory({ onOpenBot }: { onOpenBot: (name: string) => void }) {
  const [data, setData] = useState<FleetMemoryView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [query, setQuery] = useState("");
  const [botFilter, setBotFilter] = useState<string>("all");
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [addOpen, setAddOpen] = useState(false);
  const [provenance, setProvenance] = useState<FactRow | null>(null);
  const toast = useToast();

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    fetchFleetMemory(controller.signal)
      .then(setData)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError((e as Error).message);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const reload = () => setReloadKey((k) => k + 1);

  const facts = data?.facts ?? [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return facts.filter((f) => {
      if (botFilter !== "all" && f.bot !== botFilter) return false;
      if (kindFilter !== "all" && f.kind !== kindFilter) return false;
      if (statusFilter === "active" && f.status !== "active") return false;
      if (statusFilter === "archived" && f.status !== "archived") return false;
      if (statusFilter === "pinned" && !f.pinned) return false;
      if (q !== "") {
        const hay = `${f.body} ${f.bot} ${f.kind} ${f.tags.join(" ")} ${f.source ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [facts, query, botFilter, kindFilter, statusFilter]);

  const mutate = async (label: string, action: () => Promise<unknown>) => {
    try {
      await action();
      toast.success(label);
      reload();
    } catch (e) {
      toast.error(`${label} : ${(e as Error).message}`);
    }
  };

  const hasFilters =
    query !== "" || botFilter !== "all" || kindFilter !== "all" || statusFilter !== "all";

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-argos-fg flex items-center gap-2">
            <Brain size={22} strokeWidth={1.5} className="text-argos-info" />
            Mémoire de flotte
          </h1>
          <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
            Tout ce que les bots ont retenu, en un seul endroit. Épingle ce qui
            compte (jamais nettoyé), archive ce qui ne sert plus, supprime ce
            qui est faux. MemoryCurator applique les TTL chaque lundi.
          </p>
        </div>
        <Button variant="primary" onClick={() => setAddOpen((o) => !o)}>
          <span className="inline-flex items-center gap-1.5">
            <Plus size={12} strokeWidth={2} />
            {addOpen ? "Fermer" : "Ajouter un fait"}
          </span>
        </Button>
      </header>

      {error && <Flash variant="error" message={`Mémoire : ${error}`} />}

      {/* Stats */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard
            label="Faits actifs"
            value={String(data.stats.active)}
            tone={data.stats.active > 0 ? "healthy" : "neutral"}
            sub={`${data.stats.total} au total`}
          />
          <KpiCard
            label="Épinglés"
            value={String(data.stats.pinned)}
            tone="neutral"
            sub="protégés du nettoyage"
          />
          <KpiCard
            label="Archivés"
            value={String(data.stats.archived)}
            tone="neutral"
            sub="purgés après 90 j"
          />
          <KpiCard
            label="Bots avec mémoire"
            value={String(data.stats.bots)}
            tone="neutral"
            sub="dossiers data/fleet_memory/"
          />
        </div>
      )}

      {/* Add fact */}
      {addOpen && (
        <AddFactPanel
          bots={data?.bots ?? []}
          onAdd={async (bot, payload) => {
            await mutate("Fait ajouté", () => appendAgentFact(bot, payload));
            setAddOpen(false);
          }}
        />
      )}

      {/* Search */}
      <div className="flex items-center gap-2 bg-argos-surface border border-argos-border-subtle rounded-md px-3 py-2">
        <Search size={14} strokeWidth={2} className="text-argos-fg-tertiary shrink-0" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Cherche dans le contenu, les tags, la source, le bot…"
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
        {(data?.bots.length ?? 0) > 0 && (
          <FilterRow label="Bot">
            <Chip
              label="Tous les bots"
              active={botFilter === "all"}
              onClick={() => setBotFilter("all")}
            />
            {(data?.bots ?? []).map((b) => {
              const count = facts.filter((f) => f.bot === b).length;
              return (
                <Chip
                  key={b}
                  label={`${b} · ${count}`}
                  active={botFilter === b}
                  onClick={() => setBotFilter(b)}
                />
              );
            })}
          </FilterRow>
        )}
        {(data?.kinds.length ?? 0) > 0 && (
          <FilterRow label="Type">
            <Chip
              label="Tous"
              active={kindFilter === "all"}
              onClick={() => setKindFilter("all")}
            />
            {(data?.kinds ?? []).map((k) => (
              <Chip
                key={k}
                label={k}
                active={kindFilter === k}
                onClick={() => setKindFilter(k)}
              />
            ))}
          </FilterRow>
        )}
      </div>

      {/* Facts */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
        <header className="px-4 py-2.5 border-b border-argos-border-subtle font-mono text-[11px] text-argos-fg-tertiary flex items-center justify-between">
          <span>
            {filtered.length} fait{filtered.length > 1 ? "s" : ""}
            {filtered.length < facts.length && ` sur ${facts.length} au total`}
          </span>
          {hasFilters && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setBotFilter("all");
                setKindFilter("all");
                setStatusFilter("all");
              }}
              className="text-argos-info hover:underline"
            >
              Réinitialiser les filtres
            </button>
          )}
        </header>

        {data === null && error === null && (
          <div className="p-4">
            <SkeletonList count={4} />
          </div>
        )}
        {data !== null && filtered.length === 0 && (
          <div className="p-4">
            <EmptyState
              tone="neutral"
              icon={Brain}
              title={hasFilters ? "Aucun fait ne matche ces filtres" : "La mémoire est vide"}
              body={
                hasFilters
                  ? "Élargis la recherche ou réinitialise les filtres."
                  : "Les bots écrivent leurs faits en fin de run — ou ajoute le premier à la main."
              }
              compact
            />
          </div>
        )}
        {filtered.length > 0 && (
          <ul className="divide-y divide-argos-border-subtle">
            {filtered.map((f) => (
              <FleetFactRow
                key={`${f.bot}-${f.id}`}
                fact={f}
                onOpenBot={onOpenBot}
                onProvenance={() => setProvenance(f)}
                onPin={() =>
                  mutate(f.pinned ? "Fait désépinglé" : "Fait épinglé", () =>
                    pinFleetFact(f.bot, f.id, !f.pinned),
                  )
                }
                onArchive={() => mutate("Fait archivé", () => archiveAgentFact(f.bot, f.id))}
                onRestore={() => mutate("Fait restauré", () => restoreFleetFact(f.bot, f.id))}
                onDelete={() =>
                  mutate("Fait supprimé définitivement", () => deleteFleetFact(f.bot, f.id))
                }
              />
            ))}
          </ul>
        )}
      </section>

      {provenance && (
        <FactProvenanceModal fact={provenance} onClose={() => setProvenance(null)} />
      )}
    </div>
  );
}

// =============================================================================
// Ligne d'un fait — bord gauche = fraîcheur, actions à droite
// =============================================================================
function FleetFactRow({
  fact,
  onOpenBot,
  onProvenance,
  onPin,
  onArchive,
  onRestore,
  onDelete,
}: {
  fact: FactRow;
  onOpenBot: (name: string) => void;
  onProvenance: () => void;
  onPin: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onDelete: () => void;
}) {
  const fresh = factFreshness(fact);
  const confTone: Record<string, "healthy" | "info" | "neutral"> = {
    high: "healthy",
    medium: "info",
    low: "neutral",
  };
  const archived = fact.status === "archived";

  return (
    <li
      className={`border-l-2 ${fresh.border} px-4 py-3 flex items-start justify-between gap-4 ${
        archived ? "opacity-60" : ""
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap mb-1">
          <span
            className={`size-1.5 rounded-full ${fresh.dot}`}
            title={`Fraîcheur : ${fresh.label}`}
          />
          <button
            type="button"
            onClick={() => onOpenBot(fact.bot)}
            title={`Ouvrir la page de ${fact.bot}`}
            className="font-mono text-[11px] text-argos-info hover:underline"
          >
            {fact.bot}
          </button>
          <Badge tone="neutral">{fact.kind}</Badge>
          <Badge tone={confTone[fact.confidence] ?? "neutral"}>{fact.confidence}</Badge>
          {fact.pinned && (
            <Badge tone="warning">
              <Pin size={9} strokeWidth={2} />
              pinned
            </Badge>
          )}
          {archived && <Badge tone="neutral">archivé</Badge>}
          {fact.tags.map((t) => (
            <span key={t} className="font-mono text-[10px] text-argos-fg-tertiary">
              #{t}
            </span>
          ))}
        </div>
        <p className="text-xs text-argos-fg-secondary leading-relaxed break-words">
          {fact.body}
        </p>
        <div className="mt-1 font-mono text-[10px] text-argos-fg-tertiary truncate">
          <span className={fresh.text}>{fresh.label}</span> · {fact.id}
          {fact.source ? (
            <>
              {" · "}
              <button
                type="button"
                onClick={onProvenance}
                title="Voir le travail qui a produit ce souvenir (sources IN → OUT)"
                className="text-argos-info hover:underline"
              >
                {fact.source}
              </button>
            </>
          ) : null}
          {" · "}
          {formatRelativeTime(fact.created_at)}
          {fact.ttl_days !== null ? ` · TTL ${fact.ttl_days}j` : " · sans TTL"}
        </div>
      </div>

      <div className="shrink-0 flex items-center gap-1">
        <IconAction
          title="D'où vient ce souvenir ? (run + sources)"
          onClick={onProvenance}
          hoverClass="hover:text-argos-info"
        >
          <History size={13} strokeWidth={2} />
        </IconAction>
        <IconAction
          title={fact.pinned ? "Désépingler (redevient nettoyable)" : "Épingler (jamais nettoyé)"}
          onClick={onPin}
          hoverClass="hover:text-argos-warning"
        >
          {fact.pinned ? (
            <PinOff size={13} strokeWidth={2} />
          ) : (
            <Pin size={13} strokeWidth={2} />
          )}
        </IconAction>
        {archived ? (
          <IconAction
            title="Restaurer (redevient actif)"
            onClick={onRestore}
            hoverClass="hover:text-argos-healthy"
          >
            <ArchiveRestore size={13} strokeWidth={2} />
          </IconAction>
        ) : (
          <IconAction
            title="Archiver (soft delete, réversible)"
            onClick={onArchive}
            hoverClass="hover:text-argos-warning"
          >
            <Archive size={13} strokeWidth={2} />
          </IconAction>
        )}
        <DeleteAction onConfirm={onDelete} />
      </div>
    </li>
  );
}

function IconAction({
  title,
  onClick,
  hoverClass,
  children,
}: {
  title: string;
  onClick: () => void;
  hoverClass: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`p-1.5 rounded-md text-argos-fg-tertiary transition-colors hover:bg-argos-surface-2 ${hoverClass}`}
    >
      {children}
    </button>
  );
}

// Suppression dure en 2 temps : 1er clic arme, 2e clic (sous 4 s) confirme.
function DeleteAction({ onConfirm }: { onConfirm: () => void }) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(timer);
  }, [armed]);

  if (armed) {
    return (
      <button
        type="button"
        onClick={() => {
          setArmed(false);
          onConfirm();
        }}
        className="px-2 py-1 rounded-md font-mono text-[10px] bg-argos-danger/15 border border-argos-danger/40 text-argos-danger hover:bg-argos-danger/25 transition-colors"
        title="Clique pour confirmer la suppression définitive"
      >
        confirmer ?
      </button>
    );
  }
  return (
    <IconAction
      title="Supprimer définitivement (irréversible)"
      onClick={() => setArmed(true)}
      hoverClass="hover:text-argos-danger"
    >
      <Trash2 size={13} strokeWidth={2} />
    </IconAction>
  );
}

// =============================================================================
// Ajout manuel d'un fait — pour n'importe quel bot du catalogue
// =============================================================================
function AddFactPanel({
  bots,
  onAdd,
}: {
  bots: string[];
  onAdd: (
    bot: string,
    payload: {
      body: string;
      kind: string;
      ttl_days: number | null;
      pinned: boolean;
      confidence: "low" | "medium" | "high";
    },
  ) => Promise<void>;
}) {
  // Bots du catalogue + bots ayant déjà une mémoire (au cas où hors catalogue).
  const allBots = useMemo(() => {
    const set = new Set<string>(bots);
    for (const a of flattenActiveAgents()) set.add(a.name);
    return Array.from(set).sort();
  }, [bots]);

  const [bot, setBot] = useState(bots[0] ?? allBots[0] ?? "");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState("note");
  const [ttl, setTtl] = useState<string>("180");
  const [confidence, setConfidence] = useState<"low" | "medium" | "high">("medium");
  const [pinned, setPinned] = useState(false);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!body.trim() || !bot) return;
    setSaving(true);
    try {
      await onAdd(bot, {
        body: body.trim(),
        kind: kind.trim() || "note",
        ttl_days: pinned || ttl.trim() === "" ? null : Number(ttl),
        pinned,
        confidence,
      });
      setBody("");
    } finally {
      setSaving(false);
    }
  };

  const selectClass =
    "bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg focus:outline-none focus:border-argos-info/60";

  return (
    <section className="rounded-md border border-argos-info/30 bg-argos-info/5 p-4 space-y-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        Nouveau fait
      </div>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={2}
        placeholder="Ce que le bot doit retenir (ex. objection client récurrente, heuristique validée, contrainte découverte…)"
        className="w-full bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60 resize-y"
      />
      <div className="flex items-end gap-3 flex-wrap">
        <LabeledField label="Bot">
          <select value={bot} onChange={(e) => setBot(e.target.value)} className={selectClass}>
            {allBots.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </LabeledField>
        <LabeledField label="Type">
          <input
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            placeholder="note"
            className={`${selectClass} w-32`}
          />
        </LabeledField>
        <LabeledField label="Confiance">
          <select
            value={confidence}
            onChange={(e) => setConfidence(e.target.value as "low" | "medium" | "high")}
            className={selectClass}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </LabeledField>
        <LabeledField label="TTL (jours)">
          <input
            value={pinned ? "" : ttl}
            onChange={(e) => setTtl(e.target.value.replace(/[^0-9]/g, ""))}
            disabled={pinned}
            placeholder={pinned ? "—" : "180"}
            className={`${selectClass} w-24 disabled:opacity-40`}
          />
        </LabeledField>
        <label className="flex items-center gap-1.5 font-mono text-[11px] text-argos-fg-secondary cursor-pointer pb-1.5">
          <input
            type="checkbox"
            checked={pinned}
            onChange={(e) => setPinned(e.target.checked)}
            className="accent-argos-warning"
          />
          <Pin size={11} strokeWidth={2} />
          épingler
        </label>
        <Button
          variant="primary"
          onClick={submit}
          disabled={saving || !body.trim() || !bot}
          className="ml-auto"
        >
          {saving ? "Ajout…" : "Ajouter"}
        </Button>
      </div>
    </section>
  );
}

function LabeledField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </span>
      {children}
    </div>
  );
}

// =============================================================================
// Filtres (même pattern que Outputs.tsx)
// =============================================================================
function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary pt-1.5 w-14 shrink-0">
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
      className={`px-2.5 py-1 rounded-md border font-mono text-[11px] transition-colors ${
        active
          ? "bg-argos-info/15 border-argos-info/40 text-argos-info"
          : muted
            ? "border-argos-border-subtle text-argos-fg-disabled hover:text-argos-fg-tertiary"
            : "border-argos-border-subtle text-argos-fg-secondary hover:text-argos-fg hover:border-argos-border"
      }`}
    >
      {label}
    </button>
  );
}
