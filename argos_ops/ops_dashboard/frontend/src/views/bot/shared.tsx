// Composants partagés entre les onglets du détail bot (Vue d'ensemble,
// Travail, Mémoire, Historique). Extraits de l'ancien BotDetail.tsx
// monolithique pour rester réutilisables sans duplication.

import { Archive, type BookOpen, Network, Plus } from "lucide-react";
import { useState } from "react";
import type { FactRow } from "../../api";
import { Badge, Button } from "../../components/ui";
import { TooltipIcon } from "../../components/Tooltip";
import { factFreshness, formatRelativeTime } from "../../lib/format";

// =============================================================================
// SectionHeader
// =============================================================================
export interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  icon?: typeof BookOpen;
}

export function SectionHeader({ title, subtitle, icon: Icon }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mb-3 flex-wrap">
      {Icon && <Icon size={14} strokeWidth={2} className="text-argos-fg-tertiary" />}
      <h2 className="text-sm font-semibold text-argos-fg">{title}</h2>
      {subtitle && (
        <span className="font-mono text-[10px] text-argos-fg-tertiary">{subtitle}</span>
      )}
    </div>
  );
}

// =============================================================================
// KpiCard
// =============================================================================
export interface KpiCardProps {
  label: string;
  value: string;
  tooltipTerm?: string;
  tone: "healthy" | "warning" | "danger" | "neutral";
  sub?: string;
}

export function KpiCard({ label, value, tooltipTerm, tone, sub }: KpiCardProps) {
  const palette: Record<
    KpiCardProps["tone"],
    { border: string; valueFg: string; bg: string }
  > = {
    healthy: {
      border: "border-argos-healthy/30",
      valueFg: "text-argos-healthy",
      bg: "bg-argos-healthy/5",
    },
    warning: {
      border: "border-argos-warning/30",
      valueFg: "text-argos-warning",
      bg: "bg-argos-warning/5",
    },
    danger: {
      border: "border-argos-danger/40",
      valueFg: "text-argos-danger",
      bg: "bg-argos-danger/5",
    },
    neutral: {
      border: "border-argos-border-subtle",
      valueFg: "text-argos-fg",
      bg: "bg-argos-surface",
    },
  };
  const p = palette[tone];
  return (
    <div className={`rounded-md border ${p.border} ${p.bg} px-4 py-3`}>
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1">
        {label}
        {tooltipTerm && <TooltipIcon term={tooltipTerm} />}
      </div>
      <div className={`mt-1 text-xl font-mono font-medium ${p.valueFg}`}>{value}</div>
      {sub && (
        <div className="mt-0.5 font-mono text-[10px] text-argos-fg-tertiary truncate">
          {sub}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// FactCard — carte d'un fait mémoire, code couleur fraîcheur (bord gauche +
// pastille). Réutilisé par l'onglet Mémoire (propre = éditable, accessible =
// lecture seule).
// =============================================================================
export function FactCard({ fact, onArchive }: { fact: FactRow; onArchive?: () => void }) {
  const confTone: Record<string, "healthy" | "info" | "neutral"> = {
    high: "healthy",
    medium: "info",
    low: "neutral",
  };
  const fresh = factFreshness(fact);
  return (
    <li
      className={`rounded-md border border-l-2 ${fresh.border} border-argos-border-subtle bg-argos-bg/40 px-3 py-2`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap mb-1">
            <span
              className={`size-1.5 rounded-full ${fresh.dot}`}
              title={`Fraîcheur : ${fresh.label}`}
            />
            <Badge tone="neutral">{fact.kind}</Badge>
            <Badge tone={confTone[fact.confidence] ?? "neutral"}>{fact.confidence}</Badge>
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
            {fact.source ? ` · ${fact.source}` : ""} · {formatRelativeTime(fact.created_at)}
            {fact.ttl_days !== null ? ` · TTL ${fact.ttl_days}j` : ""}
          </div>
        </div>
        {onArchive && fact.status !== "archived" && (
          <button
            type="button"
            onClick={onArchive}
            title="Archiver ce fait (soft delete)"
            className="shrink-0 inline-flex items-center gap-1 font-mono text-[10px] text-argos-fg-tertiary hover:text-argos-warning transition-colors"
          >
            <Archive size={11} strokeWidth={2} />
            archiver
          </button>
        )}
      </div>
    </li>
  );
}

// =============================================================================
// AccessGraphRow — graphe d'accès mémoire (lit / lu par)
// =============================================================================
export function AccessGraphRow({ reads, readBy }: { reads: string[]; readBy: string[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1 mb-1.5">
          <Network size={11} strokeWidth={2} />
          Lit la mémoire de
        </div>
        {reads.length === 0 ? (
          <span className="font-mono text-[11px] text-argos-fg-tertiary">aucun autre bot</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {reads.map((b) => (
              <Badge key={b} tone="info">
                {b}
              </Badge>
            ))}
          </div>
        )}
      </div>
      <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary flex items-center gap-1 mb-1.5">
          <Network size={11} strokeWidth={2} />
          Lu par
        </div>
        {readBy.length === 0 ? (
          <span className="font-mono text-[11px] text-argos-fg-tertiary">aucun autre bot</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {readBy.map((b) => (
              <Badge key={b} tone="neutral">
                {b}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// AddFactForm — ajout manuel d'un fait à la mémoire propre du bot
// =============================================================================
export function AddFactForm({
  onAdd,
}: {
  onAdd: (body: string, kind: string) => Promise<void>;
}) {
  const [body, setBody] = useState("");
  const [kind, setKind] = useState("note");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!body.trim()) return;
    setSaving(true);
    try {
      await onAdd(body.trim(), kind.trim());
      setBody("");
      setKind("note");
    } catch {
      // toast affiché par le parent ; on garde le texte saisi
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 p-3 space-y-2">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={2}
        placeholder="Ajouter un fait que ce bot doit retenir (ex. objection client récurrente, heuristique validée…)"
        className="w-full bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60 resize-y"
      />
      <div className="flex items-center gap-2 flex-wrap">
        <input
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          placeholder="kind (ex. note)"
          className="w-40 bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60"
        />
        <Button variant="primary" size="sm" onClick={submit} disabled={saving || !body.trim()}>
          <span className="inline-flex items-center gap-1.5">
            <Plus size={11} strokeWidth={2} />
            {saving ? "Ajout…" : "Ajouter un fait"}
          </span>
        </Button>
      </div>
    </div>
  );
}
