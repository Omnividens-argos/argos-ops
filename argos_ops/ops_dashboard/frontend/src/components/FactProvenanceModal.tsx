// Modale « D'où vient ce souvenir ? » — remonte d'un fait mémoire au travail
// (run) qui l'a produit : quel run, quand, et surtout SES SOURCES (IN — où le
// bot a récupéré l'information) puis ce qu'il en a produit (OUT). Ouverte
// depuis le Memory Hub et l'onglet Mémoire du détail bot.
//
// Un fait sans run_id (ajout manuel admin_panel / atelier) affiche simplement
// l'origine déclarée — il n'y a pas de run à remonter.

import {
  ArrowRight,
  Database,
  ExternalLink,
  FileText,
  Globe,
  History,
  Mail,
  MessageSquare,
  Search,
  Workflow,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { AgentRunRow, FactRow, RunIOItem } from "../api";
import { fetchRun } from "../api";
import { formatAbsoluteTime, formatDuration, statusColor } from "../lib/format";
import { EmptyState } from "./EmptyState";
import { Badge, Flash } from "./ui";

const KIND_ICON: Record<string, typeof Database> = {
  db: Database,
  imap: Mail,
  email: Mail,
  kb: Search,
  memory: Workflow,
  file: FileText,
  http: Globe,
  api: Globe,
  discord: MessageSquare,
  draft: FileText,
  other: ArrowRight,
};

export function FactProvenanceModal({
  fact,
  onClose,
}: {
  fact: FactRow;
  onClose: () => void;
}) {
  const [run, setRun] = useState<AgentRunRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (fact.run_id === null) return;
    const controller = new AbortController();
    fetchRun(fact.run_id, controller.signal)
      .then(setRun)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError((e as Error).message);
      });
    return () => controller.abort();
  }, [fact.run_id]);

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
              <History size={13} strokeWidth={2} className="text-argos-info" />
              <h2 className="text-sm font-semibold text-argos-fg">
                D'où vient ce souvenir ?
              </h2>
              <Badge tone="info">{fact.bot}</Badge>
              <Badge tone="neutral">{fact.kind}</Badge>
            </div>
            <p className="text-xs text-argos-fg-secondary leading-relaxed break-words line-clamp-2">
              {fact.body}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 font-mono text-[11px] text-argos-fg-tertiary hover:text-argos-fg flex items-center gap-1"
          >
            <X size={12} strokeWidth={2} />
            esc
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Fait manuel : pas de run derrière */}
          {fact.run_id === null && (
            <EmptyState
              tone="neutral"
              icon={History}
              title="Ajout manuel — pas de run derrière"
              body={`Ce fait a été saisi directement (origine : ${fact.source ?? "inconnue"}), il ne provient pas du travail automatique d'un bot.`}
              compact
            />
          )}

          {fact.run_id !== null && error && (
            <Flash
              variant="error"
              message={`Run #${fact.run_id} : ${error} (probablement purgé de l'historique)`}
            />
          )}
          {fact.run_id !== null && !error && run === null && (
            <EmptyState tone="loading" title={`Chargement du run #${fact.run_id}…`} compact />
          )}

          {run && (
            <>
              {/* Bandeau run */}
              <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
                <div className={`font-mono text-xs ${statusColor(run.status)}`}>
                  run #{run.id} · {run.status ?? "?"}
                  {run.command ? ` · ${run.command}` : ""}
                </div>
                <div className="font-mono text-[10px] text-argos-fg-tertiary">
                  {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
                </div>
              </div>

              {/* IN → OUT */}
              <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
                <ProvenanceColumn
                  title="IN — où il a récupéré l'info"
                  tone="info"
                  items={run.inputs ?? []}
                  emptyHint="run non instrumenté — sources non tracées"
                />
                <div className="hidden md:flex items-center justify-center text-argos-fg-tertiary">
                  <ArrowRight size={16} strokeWidth={2} />
                </div>
                <ProvenanceColumn
                  title="OUT — ce qu'il en a produit"
                  tone="healthy"
                  items={run.outputs ?? []}
                  emptyHint="aucune production tracée"
                />
              </div>

              {run.output_summary && (
                <div className="font-mono text-[11px] text-argos-fg-tertiary break-words">
                  résumé : {run.output_summary}
                </div>
              )}
            </>
          )}
        </div>

        <footer className="px-5 py-2 border-t border-argos-border-subtle bg-argos-surface-2/40 font-mono text-[10px] text-argos-fg-tertiary flex items-center gap-1.5">
          <Workflow size={11} strokeWidth={2} />
          {fact.source ? `source déclarée : ${fact.source}` : "lecture seule depuis le panel"}
        </footer>
      </div>
    </div>
  );
}

function ProvenanceColumn({
  title,
  tone,
  items,
  emptyHint,
}: {
  title: string;
  tone: "info" | "healthy";
  items: RunIOItem[];
  emptyHint: string;
}) {
  const accent = tone === "info" ? "text-argos-info" : "text-argos-healthy";
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2">
      <div className={`font-mono text-[10px] uppercase tracking-widest ${accent} mb-1.5`}>
        {title}
      </div>
      {items.length === 0 ? (
        <div className="font-mono text-[11px] text-argos-fg-tertiary">{emptyHint}</div>
      ) : (
        <ul className="space-y-1.5">
          {items.map((it, i) => {
            const Icon = KIND_ICON[it.kind] ?? KIND_ICON.other;
            const isUrl = !!it.ref && /^https?:\/\//i.test(it.ref);
            return (
              <li key={`${it.label}-${i}`} className="flex items-start gap-2">
                <Icon
                  size={13}
                  strokeWidth={2}
                  className="text-argos-fg-tertiary shrink-0 mt-0.5"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs text-argos-fg break-words">{it.label}</span>
                    {it.count !== null && <Badge tone="neutral">{it.count}</Badge>}
                  </div>
                  {it.detail && (
                    <div className="font-mono text-[10px] text-argos-fg-tertiary break-words">
                      {it.detail}
                    </div>
                  )}
                  {it.ref &&
                    (isUrl ? (
                      <a
                        href={it.ref}
                        target="_blank"
                        rel="noreferrer"
                        className="font-mono text-[10px] text-argos-info hover:underline inline-flex items-center gap-1 break-all"
                      >
                        {it.ref}
                        <ExternalLink size={9} strokeWidth={2} className="shrink-0" />
                      </a>
                    ) : (
                      <div className="font-mono text-[10px] text-argos-fg-tertiary break-all">
                        {it.ref}
                      </div>
                    ))}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
