import {
  CheckCircle2,
  FileSignature,
  FileText,
  Mail,
  Megaphone,
  PenLine,
  Share2,
  Sparkles,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import {
  fetchInboxDrafts,
  rejectInboxDraft,
  validateInboxDraft,
  type InboxDraft,
  type InboxKind,
} from "../api";
import { EmptyState } from "../components/EmptyState";
import { SkeletonList } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { Badge, Button, Flash, TextInput } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { useDensityClasses } from "../hooks/useUserPrefs";
import { formatRelativeTime } from "../lib/format";

// Vue Inbox — file unifiée des drafts en attente de validation humaine.
// Source backend : GET /api/inbox/drafts (filesystem scan côté Python).
// Catégories alignées sur les agents qui produisent (content/seo/outbound/...).
//
// L'UI fonctionne même si l'API renvoie [] : on affiche un empty state
// "Inbox vide ✨" — le ton positif est volontaire (cf. UX guideline #62).

interface KindMeta {
  id: InboxKind;
  label: string;
  icon: LucideIcon;
  agentHint: string;
  description: string;
}

const KINDS: KindMeta[] = [
  {
    id: "email",
    label: "Emails à envoyer",
    icon: Mail,
    agentHint: "EmailBot · OutboundBot · DemoFollowupBot",
    description: "Réponses inbound + cold emails outbound + récap post-démo.",
  },
  {
    id: "social",
    label: "Posts sociaux",
    icon: Share2,
    agentHint: "ContentBot · ReplyBot",
    description: "LinkedIn + Mastodon — drafts à valider avant publication.",
  },
  {
    id: "proposal",
    label: "Devis & contrats",
    icon: FileSignature,
    agentHint: "ProposalBot · ContractGenerator",
    description: "Devis en cours et contrats CGV/MSA générés depuis les deals pipe.",
  },
  {
    id: "seo",
    label: "Briefs SEO & contenu long",
    icon: FileText,
    agentHint: "SEOBot · TrendSpotter",
    description: "Briefs blog SEO en cours de drafting.",
  },
  {
    id: "press",
    label: "Communiqués & relations presse",
    icon: Megaphone,
    agentHint: "PressMonitor (drafters presse retirés — D-030)",
    description: "Catégorie conservée pour les anciens drafts presse.",
  },
  {
    id: "doc",
    label: "Documentation interne",
    icon: PenLine,
    agentHint: "ADRWriter · ReleaseNotesBot · KBUpdater",
    description: "ADRs, release notes et updates KB à relire.",
  },
];

interface InboxProps {
  filterByAgent?: string | null;
}

export function Inbox({ filterByAgent }: InboxProps = {}) {
  const drafts = usePolling(useCallback((s) => fetchInboxDrafts(s), []), 10000);
  const toast = useToast();
  const [openKind, setOpenKind] = useState<InboxKind | "all">("all");
  // IDs déjà traités côté UI — masque optimistement les rows en attendant
  // que le poll suivant rafraîchisse la liste serveur (10 s).
  const [processedIds, setProcessedIds] = useState<Set<string>>(new Set());
  const markProcessed = (id: string) =>
    setProcessedIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });

  const visibleDrafts = useMemo(() => {
    const all = drafts.data ?? [];
    return all.filter((d) => {
      if (processedIds.has(d.id)) return false;
      if (filterByAgent && d.agent_name !== filterByAgent) return false;
      return true;
    });
  }, [drafts.data, processedIds, filterByAgent]);

  const byKind = useMemo(() => {
    const map: Record<InboxKind, InboxDraft[]> = {
      email: [],
      social: [],
      proposal: [],
      seo: [],
      press: [],
      doc: [],
      other: [],
    };
    for (const draft of visibleDrafts) {
      (map[draft.kind] ?? map.other).push(draft);
    }
    return map;
  }, [visibleDrafts]);

  const totalCount = visibleDrafts.length;
  const isLoading = drafts.data === null && drafts.error === null;
  const isEmpty = drafts.data !== null && totalCount === 0;
  const isBackendMissing =
    drafts.error !== null && drafts.error.message.includes("404");

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <header className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-argos-fg">Inbox</h1>
          <p className="text-sm text-argos-fg-secondary mt-1">
            Tous les drafts que les bots ont produits et qui attendent ta
            validation, regroupés en un seul endroit.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={totalCount > 0 ? "info" : "healthy"}>
            {totalCount} en attente
          </Badge>
        </div>
      </header>


      {/* Tabs catégorie */}
      <nav
        className="flex items-center gap-1.5 flex-wrap"
        aria-label="Filtrer par catégorie"
      >
        <TabChip
          active={openKind === "all"}
          onClick={() => setOpenKind("all")}
          label={`Tous · ${totalCount}`}
        />
        {KINDS.map((k) => {
          const count = byKind[k.id]?.length ?? 0;
          return (
            <TabChip
              key={k.id}
              active={openKind === k.id}
              onClick={() => setOpenKind(k.id)}
              label={`${k.label} · ${count}`}
              muted={count === 0}
            />
          );
        })}
      </nav>

      {/* Body */}
      {isBackendMissing ? (
        <EmptyState
          tone="neutral"
          icon={Sparkles}
          title="Inbox en cours de raccordement"
          body="L'endpoint backend /api/inbox/drafts n'est pas encore exposé. Le frontend est prêt et se peuplera automatiquement dès que le scan filesystem sera branché (Phase 2)."
        />
      ) : isLoading ? (
        <SkeletonList count={4} />
      ) : isEmpty ? (
        <EmptyState
          tone="celebrate"
          icon={CheckCircle2}
          title="Inbox vide — bravo ✨"
          body="Aucun draft en attente. Soit tu viens de tout valider, soit la flotte est calme. Profite."
        />
      ) : (
        <div className="space-y-5">
          {KINDS.map((kind) => {
            if (openKind !== "all" && openKind !== kind.id) return null;
            const items = byKind[kind.id] ?? [];
            if (items.length === 0 && openKind === "all") return null;
            return (
              <KindSection
                key={kind.id}
                meta={kind}
                items={items}
                onProcessed={markProcessed}
                toast={toast}
              />
            );
          })}
          {/* "Autre" si présent. */}
          {(byKind.other?.length ?? 0) > 0 &&
            (openKind === "all" || openKind === "other") && (
              <KindSection
                meta={{
                  id: "other",
                  label: "Autres drafts",
                  icon: FileText,
                  agentHint: "—",
                  description: "Drafts non catégorisés.",
                }}
                items={byKind.other ?? []}
                onProcessed={markProcessed}
                toast={toast}
              />
            )}
        </div>
      )}

      {drafts.error && !isBackendMissing && (
        <Flash
          variant="error"
          message={`Impossible de charger l'inbox : ${drafts.error.message}`}
        />
      )}
    </div>
  );
}

// =============================================================================
// Tab chip
// =============================================================================
function TabChip({
  active,
  onClick,
  label,
  muted,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  muted?: boolean;
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
// Section par catégorie
// =============================================================================
function KindSection({
  meta,
  items,
  onProcessed,
  toast,
}: {
  meta: KindMeta;
  items: InboxDraft[];
  onProcessed: (id: string) => void;
  toast: ReturnType<typeof useToast>;
}) {
  const Icon = meta.icon;
  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
      <header className="px-4 py-3 border-b border-argos-border-subtle flex items-start gap-3">
        <Icon
          size={16}
          strokeWidth={2}
          className="text-argos-fg-secondary shrink-0 mt-0.5"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-argos-fg">{meta.label}</h2>
            <span className="font-mono text-[10px] text-argos-fg-tertiary">
              {items.length}
            </span>
          </div>
          <div className="font-mono text-[10px] text-argos-fg-tertiary">
            {meta.description} · produit par {meta.agentHint}
          </div>
        </div>
      </header>

      {items.length === 0 ? (
        <div className="px-4 py-5 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Aucun draft dans cette catégorie ✨
        </div>
      ) : (
        <ul className="divide-y divide-argos-border-subtle">
          {items.map((item) => (
            <DraftRow
              key={item.id}
              draft={item}
              onProcessed={onProcessed}
              toast={toast}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

// =============================================================================
// Draft row
// =============================================================================
function DraftRow({
  draft,
  onProcessed,
  toast,
}: {
  draft: InboxDraft;
  onProcessed: (id: string) => void;
  toast: ReturnType<typeof useToast>;
}) {
  const { rowPaddingY } = useDensityClasses();
  const [pending, setPending] = useState<"validate" | "reject" | null>(null);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const copyPath = () => {
    navigator.clipboard
      .writeText(draft.file_path)
      .then(() => toast.success("Chemin copié"))
      .catch(() => toast.error("Impossible de copier le chemin"));
  };

  const handleValidate = async () => {
    setPending("validate");
    try {
      await validateInboxDraft(draft.id);
      toast.success(`${draft.title} → validé`);
      onProcessed(draft.id);
    } catch (e) {
      toast.error(`Validation : ${(e as Error).message}`);
    } finally {
      setPending(null);
    }
  };

  const handleReject = async () => {
    setPending("reject");
    try {
      await rejectInboxDraft(draft.id, {
        reason: rejectReason.trim() || null,
      });
      toast.success(
        `${draft.title} → rejeté${
          rejectReason ? ` (${rejectReason.slice(0, 40)}…)` : ""
        }`,
      );
      onProcessed(draft.id);
    } catch (e) {
      toast.error(`Reject : ${(e as Error).message}`);
    } finally {
      setPending(null);
      setShowRejectForm(false);
      setRejectReason("");
    }
  };

  return (
    <li className={`px-4 ${rowPaddingY} hover:bg-argos-surface-2/50 transition-colors`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm text-argos-fg truncate font-medium">
            {draft.title}
          </div>
          {draft.summary && (
            <div className="mt-1 text-xs text-argos-fg-secondary line-clamp-2">
              {draft.summary}
            </div>
          )}
          <div className="mt-1.5 flex items-center gap-2 flex-wrap font-mono text-[10px] text-argos-fg-tertiary">
            <span>{formatRelativeTime(draft.created_at)}</span>
            <span>·</span>
            <span className="truncate">{draft.file_path}</span>
            {draft.agent_name && (
              <>
                <span>·</span>
                <span>{draft.agent_name}</span>
              </>
            )}
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-1.5">
          <Badge tone={statusTone(draft.status)}>{draft.status}</Badge>
        </div>
      </div>

      {/* Action bar — toujours visible, séparée du body pour clarté */}
      <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
        <Button
          size="sm"
          variant="primary"
          onClick={handleValidate}
          disabled={pending !== null}
        >
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 size={11} strokeWidth={2} />
            {pending === "validate" ? "Validation…" : "Valider"}
          </span>
        </Button>
        {!showRejectForm ? (
          <Button
            size="sm"
            variant="danger"
            onClick={() => setShowRejectForm(true)}
            disabled={pending !== null}
          >
            <span className="inline-flex items-center gap-1">
              <X size={11} strokeWidth={2} />
              Rejeter
            </span>
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          onClick={copyPath}
          title="Copier le chemin du fichier"
        >
          copier path
        </Button>
      </div>

      {showRejectForm && (
        <div className="mt-2 rounded-md border border-argos-danger/30 bg-argos-danger/5 p-3 space-y-2">
          <TextInput
            label="Raison du rejet (optionnel, archivée dans le frontmatter)"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="ex. ton trop FUD, hallucination prix, RGPD risqué…"
            autoFocus
          />
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              variant="danger"
              onClick={handleReject}
              disabled={pending !== null}
            >
              {pending === "reject" ? "Rejet…" : "Confirmer le rejet"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setShowRejectForm(false);
                setRejectReason("");
              }}
              disabled={pending !== null}
            >
              Annuler
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

function statusTone(status: string): "healthy" | "warning" | "info" | "neutral" {
  switch (status) {
    case "validated":
      return "healthy";
    case "pending_review":
      return "warning";
    case "draft":
    case "drafted":
      return "info";
    default:
      return "neutral";
  }
}
