// Onglet Travail (IN → OUT) du détail bot — montre concrètement le travail
// d'un bot run par run : ce qu'il a regardé (IN) → ce qu'il a trouvé / produit
// (OUT). Quand un run n'est pas instrumenté (inputs/outputs null), on retombe
// sur une vue dérivée (config + résumé) signalée honnêtement.

import {
  ArrowRight,
  Database,
  FileText,
  Globe,
  Inbox as InboxIcon,
  Mail,
  MessageSquare,
  Search,
  Workflow,
} from "lucide-react";
import { useMemo, useState } from "react";
import type {
  AgentPerfStats,
  AgentRunRow,
  InboxDraft,
  RunIOItem,
} from "../../api";
import { EmptyState } from "../../components/EmptyState";
import { SkeletonList } from "../../components/Skeleton";
import { Badge } from "../../components/ui";
import type { BotMetadata } from "../../lib/botMetadata";
import {
  formatAbsoluteTime,
  formatDuration,
  statusBgColor,
  statusColor,
} from "../../lib/format";
import { SectionHeader } from "./shared";

// Icône par kind d'IOItem.
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

interface TravailTabProps {
  runs: AgentRunRow[] | null;
  perf: AgentPerfStats | null;
  drafts: InboxDraft[];
  meta: BotMetadata;
  onOpenInbox: () => void;
}

export function TravailTab({ runs, perf, drafts, meta, onOpenInbox }: TravailTabProps) {
  const [statusFilter, setStatusFilter] = useState<
    "all" | "success" | "failed" | "skipped"
  >("all");

  const filtered = useMemo(() => {
    if (!runs) return [];
    if (statusFilter === "all") return runs;
    if (statusFilter === "skipped")
      return runs.filter((r) => (r.status ?? "").startsWith("skipped_"));
    return runs.filter((r) => r.status === statusFilter);
  }, [runs, statusFilter]);

  return (
    <div className="space-y-5">
      {/* Bandeau récap */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <SectionHeader
          title="Travail du bot"
          subtitle="Ce qu'il regarde (IN) → ce qu'il produit (OUT), run par run"
          icon={ArrowRight}
        />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Runs 7 j" value={perf ? `${perf.total_runs}` : "—"} tone="neutral" />
          <Stat
            label="Succès"
            value={perf ? `${perf.success_count}` : "—"}
            tone="healthy"
          />
          <Stat
            label="Erreurs"
            value={perf ? `${perf.failed_count}` : "—"}
            tone={perf && perf.failed_count > 0 ? "danger" : "neutral"}
          />
          <Stat
            label="Skipped"
            value={perf ? `${perf.skipped_count}` : "—"}
            tone="neutral"
          />
        </div>
      </section>

      {/* Productions (OUT agrégé) — drafts du bot */}
      {drafts.length > 0 && (
        <section className="rounded-md border border-argos-info/30 bg-argos-info/5 p-5">
          <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
            <div className="flex items-center gap-2">
              <InboxIcon size={14} strokeWidth={2} className="text-argos-info" />
              <h2 className="text-sm font-semibold text-argos-fg">
                Productions en attente
              </h2>
              <Badge tone="info">{drafts.length}</Badge>
            </div>
            <button
              type="button"
              onClick={onOpenInbox}
              className="font-mono text-[11px] text-argos-info hover:underline flex items-center gap-1"
            >
              Voir dans l'Inbox
              <ArrowRight size={11} strokeWidth={2} />
            </button>
          </div>
          <ul className="space-y-1.5">
            {drafts.slice(0, 5).map((d) => (
              <li
                key={d.id}
                className="rounded-md bg-argos-surface px-3 py-2 flex items-start justify-between gap-3 border border-argos-border-subtle"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-argos-fg truncate">
                    {d.title}
                  </div>
                  <div className="font-mono text-[10px] text-argos-fg-tertiary truncate">
                    {d.file_path}
                  </div>
                </div>
                <Badge tone="info">{d.status}</Badge>
              </li>
            ))}
            {drafts.length > 5 && (
              <li className="font-mono text-[10px] text-argos-fg-tertiary text-center pt-1">
                +{drafts.length - 5} de plus — voir Inbox
              </li>
            )}
          </ul>
        </section>
      )}

      {/* Timeline IN → OUT par run */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <Workflow size={14} strokeWidth={2} className="text-argos-fg-tertiary" />
          <h2 className="text-sm font-semibold text-argos-fg">Flux IN → OUT</h2>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            (50 derniers runs)
          </span>
          <div className="ml-auto flex items-center gap-1.5">
            {(["all", "success", "failed", "skipped"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStatusFilter(s)}
                className={`font-mono text-[10px] px-2 py-0.5 rounded border transition-colors ${
                  statusFilter === s
                    ? "bg-argos-info/15 border-argos-info/40 text-argos-info"
                    : "bg-argos-surface border-argos-border-subtle text-argos-fg-tertiary hover:text-argos-fg"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {runs === null && <SkeletonList count={3} />}
        {runs?.length === 0 && (
          <EmptyState
            tone="neutral"
            title="Pas encore de run"
            body="Lance ce bot via « Run now » ou attends son créneau cron pour voir son flux IN → OUT."
            compact
          />
        )}
        {runs && runs.length > 0 && filtered.length === 0 && (
          <EmptyState
            tone="neutral"
            title="Aucun run ne correspond"
            body="Le filtre statut exclut tout l'historique. Repasse sur « all »."
            compact
          />
        )}
        <div className="space-y-3">
          {filtered.map((run) => (
            <RunIOCard key={run.id} run={run} meta={meta} />
          ))}
        </div>
      </section>
    </div>
  );
}

function RunIOCard({ run, meta }: { run: AgentRunRow; meta: BotMetadata }) {
  const hasRealIO =
    (run.inputs && run.inputs.length > 0) || (run.outputs && run.outputs.length > 0);

  // Fallback dérivé quand le bot n'est pas instrumenté.
  const derivedInputs: RunIOItem[] = hasRealIO
    ? run.inputs ?? []
    : buildDerivedInputs(meta);
  const derivedOutputs: RunIOItem[] = hasRealIO
    ? run.outputs ?? []
    : buildDerivedOutputs(run);

  return (
    <div className={`rounded-md border ${statusBgColor(run.status)} p-3`}>
      <div className="flex items-center justify-between gap-3 mb-2.5 text-xs">
        <div className={`font-mono ${statusColor(run.status)} truncate`}>
          #{run.id} · {run.status ?? "?"}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {!hasRealIO && <Badge tone="neutral">vue dérivée</Badge>}
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
        <IOColumn title="IN" tone="info" items={derivedInputs} emptyHint="aucune source identifiée" />
        <div className="hidden md:flex items-center justify-center text-argos-fg-tertiary">
          <ArrowRight size={16} strokeWidth={2} />
        </div>
        <IOColumn
          title="OUT"
          tone="healthy"
          items={derivedOutputs}
          emptyHint="rien produit"
          extra={
            run.error ? (
              <div className="mt-1.5 font-mono text-[11px] text-argos-danger break-words whitespace-pre-wrap">
                {run.error}
              </div>
            ) : undefined
          }
        />
      </div>
    </div>
  );
}

function IOColumn({
  title,
  tone,
  items,
  emptyHint,
  extra,
}: {
  title: string;
  tone: "info" | "healthy";
  items: RunIOItem[];
  emptyHint: string;
  extra?: React.ReactNode;
}) {
  const accent = tone === "info" ? "text-argos-info" : "text-argos-healthy";
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2">
      <div
        className={`font-mono text-[10px] uppercase tracking-widest ${accent} mb-1.5`}
      >
        {title}
      </div>
      {items.length === 0 ? (
        <div className="font-mono text-[11px] text-argos-fg-tertiary">{emptyHint}</div>
      ) : (
        <ul className="space-y-1.5">
          {items.map((it, i) => (
            <IORow key={`${it.label}-${i}`} item={it} />
          ))}
        </ul>
      )}
      {extra}
    </div>
  );
}

function IORow({ item }: { item: RunIOItem }) {
  const Icon = KIND_ICON[item.kind] ?? KIND_ICON.other;
  return (
    <li className="flex items-start gap-2">
      <Icon size={13} strokeWidth={2} className="text-argos-fg-tertiary shrink-0 mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-argos-fg break-words">{item.label}</span>
          {item.count !== null && <Badge tone="neutral">{item.count}</Badge>}
        </div>
        {item.detail && (
          <div className="font-mono text-[10px] text-argos-fg-tertiary break-words">
            {item.ref && item.ref.startsWith("http") ? (
              <a
                href={item.ref}
                target="_blank"
                rel="noreferrer"
                className="text-argos-info hover:underline"
              >
                {item.detail}
              </a>
            ) : (
              item.detail
            )}
          </div>
        )}
      </div>
    </li>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "healthy" | "danger" | "neutral";
}) {
  const fg =
    tone === "healthy"
      ? "text-argos-healthy"
      : tone === "danger"
        ? "text-argos-danger"
        : "text-argos-fg";
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </div>
      <div className={`mt-0.5 text-lg font-mono font-medium ${fg}`}>{value}</div>
    </div>
  );
}

// === Fallback dérivé (bot non instrumenté) ===
function buildDerivedInputs(meta: BotMetadata): RunIOItem[] {
  const items: RunIOItem[] = [];
  if (meta.configFile) {
    items.push({
      label: "Fichier de config / données",
      kind: "file",
      detail: meta.configFile,
      ref: meta.configFile,
      count: null,
    });
  }
  for (const skill of meta.skills ?? []) {
    items.push({ label: `Skill ${skill}`, kind: "kb", detail: null, ref: null, count: null });
  }
  return items;
}

function buildDerivedOutputs(run: AgentRunRow): RunIOItem[] {
  if (!run.output_summary) return [];
  return [
    {
      label: "Résumé du run",
      kind: "other",
      detail: run.output_summary,
      ref: null,
      count: null,
    },
  ];
}
