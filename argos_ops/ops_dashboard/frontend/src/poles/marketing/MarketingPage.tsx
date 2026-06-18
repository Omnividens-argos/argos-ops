// Page du pôle Marketing (archi v2, S2). Branche le shell poles.html sur le
// backend (GET /api/poles/marketing/overview + mutations) : recommandations
// éditoriales (synthèse Veille cross-pôle), file de drafts à valider inline,
// calendrier éditorial drag-and-drop, preview par canal, KB éditable, éditeur de
// charte/ton, stats engagement. Réutilise le thème et les composants partagés.

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  type MarketingCharter,
  type MarketingOverview,
  editDraft,
  deleteKB,
  fetchMarketingOverview,
  rejectDraft,
  saveCharter,
  scheduleDraft,
  upsertKB,
  validateDraft,
} from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { CharterEditor } from "./CharterEditor.tsx";
import { ChannelPreview } from "./ChannelPreview.tsx";
import { DraftQueue } from "./DraftQueue.tsx";
import { EditorialCalendar } from "./EditorialCalendar.tsx";
import { EngagementStats } from "./EngagementStats.tsx";
import { KBEditor } from "./KBEditor.tsx";
import { RecommendationFeed } from "./RecommendationFeed.tsx";

type Tab = "editorial" | "calendar" | "kb" | "charter" | "stats";

const TABS: { id: Tab; label: string }[] = [
  { id: "editorial", label: "Éditorial" },
  { id: "calendar", label: "Calendrier" },
  { id: "kb", label: "KB" },
  { id: "charter", label: "Charte / ton" },
  { id: "stats", label: "Engagement" },
];

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {title}
        </h2>
        {hint && <span className="font-mono text-[10px] text-argos-fg-disabled">{hint}</span>}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex flex-col">
      <span className={`font-mono text-base font-medium ${tone}`}>{value}</span>
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        {label}
      </span>
    </div>
  );
}

export function MarketingPage() {
  const [overview, setOverview] = useState<MarketingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [tab, setTab] = useState<Tab>("editorial");
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; message: string } | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchMarketingOverview(controller.signal)
      .then((data) => setOverview(data))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  // Wrapper commun des mutations : busy + flash + reload.
  const runMutation = useCallback(
    async (key: string, fn: () => Promise<unknown>, okMsg: string) => {
      setBusy(key);
      setFlash(null);
      try {
        await fn();
        setFlash({ variant: "success", message: okMsg });
        reload();
      } catch (err: unknown) {
        setFlash({
          variant: "error",
          message: err instanceof Error ? err.message : "Échec de l'action.",
        });
      } finally {
        setBusy(null);
      }
    },
    [reload],
  );

  const onValidate = useCallback(
    (id: string) => runMutation(id, () => validateDraft(id), "Draft validé."),
    [runMutation],
  );
  const onReject = useCallback(
    (id: string) => runMutation(id, () => rejectDraft(id), "Draft rejeté."),
    [runMutation],
  );
  const onEditDraft = useCallback(
    (id: string, patch: { title: string; body: string }) =>
      runMutation(id, () => editDraft(id, patch), "Draft mis à jour."),
    [runMutation],
  );
  const onSchedule = useCallback(
    (id: string, iso: string | null) =>
      runMutation(id, () => scheduleDraft(id, iso), iso ? "Draft planifié." : "Draft déplanifié."),
    [runMutation],
  );
  const onUpsertKB = useCallback(
    (slug: string, patch: { title: string; body: string; tags: string[] }) =>
      runMutation(slug, () => upsertKB(slug, patch), "Fiche KB enregistrée."),
    [runMutation],
  );
  const onDeleteKB = useCallback(
    (slug: string) => runMutation(slug, () => deleteKB(slug), "Fiche KB supprimée."),
    [runMutation],
  );
  const onSaveCharter = useCallback(
    (charter: MarketingCharter) =>
      runMutation("__charter__", () => saveCharter(charter), "Charte enregistrée."),
    [runMutation],
  );

  const selectedDraft = useMemo(() => {
    if (!overview) return null;
    return overview.drafts.find((d) => d.id === selectedDraftId) ?? overview.drafts[0] ?? null;
  }, [overview, selectedDraftId]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 2/8</span>
            <Badge tone="info">MarketingAgent</Badge>
            <Badge tone="neutral">lit la Veille</Badge>
          </div>
          <Button size="sm" variant="ghost" onClick={reload}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Marketing &amp; Comm</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">
          Acquisition organique : la Veille nourrit l'angle, l'agent recommande, les writers
          draftent, vous validez, le calendrier planifie, ContentBot publie.
        </p>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat label="à valider" value={overview.counts.pending} tone="text-argos-warning" />
            <Stat label="validés" value={overview.counts.validated} tone="text-argos-info" />
            <Stat label="publiés" value={overview.counts.published} tone="text-argos-healthy" />
            <Stat
              label="reco critiques"
              value={overview.counts.critical}
              tone="text-argos-danger"
            />
          </div>
        )}
      </header>

      {flash && (
        <Flash variant={flash.variant} message={flash.message} onDismiss={() => setFlash(null)} />
      )}

      {loading && (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-8 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Chargement du pôle Marketing…
        </div>
      )}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {overview && !loading && (
        <>
          {/* Onglets internes du pôle */}
          <nav className="flex flex-wrap gap-1.5">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                aria-current={tab === t.id ? "page" : undefined}
                className={`rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors ${
                  tab === t.id
                    ? "border-argos-info/40 bg-argos-info/15 text-argos-info"
                    : "border-argos-border-subtle bg-argos-surface-2 text-argos-fg-tertiary hover:text-argos-fg"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>

          {tab === "editorial" && (
            <>
              <Section
                title="Recommandations éditoriales (Veille)"
                hint={`${overview.recommendations.length} reco`}
              >
                <RecommendationFeed
                  recommendations={overview.recommendations}
                  channels={overview.channels}
                />
              </Section>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_minmax(0,440px)]">
                <Section title="File de drafts à valider" hint={`${overview.drafts.length} draft(s)`}>
                  <DraftQueue
                    drafts={overview.drafts}
                    channels={overview.channels}
                    selectedId={selectedDraft?.id ?? null}
                    busyId={busy}
                    onSelect={setSelectedDraftId}
                    onValidate={onValidate}
                    onReject={onReject}
                    onEdit={onEditDraft}
                  />
                </Section>
                <Section title="Preview par canal">
                  <ChannelPreview draft={selectedDraft} channels={overview.channels} />
                </Section>
              </div>
            </>
          )}

          {tab === "calendar" && (
            <Section
              title="Calendrier éditorial (glisser-déposer)"
              hint={`${overview.counts.scheduled} planifié(s)`}
            >
              <EditorialCalendar
                drafts={overview.drafts}
                channels={overview.channels}
                busyId={busy}
                onSchedule={onSchedule}
              />
            </Section>
          )}

          {tab === "kb" && (
            <Section title="KB éditoriale">
              <KBEditor
                entries={overview.kb}
                busySlug={busy}
                onUpsert={onUpsertKB}
                onDelete={onDeleteKB}
              />
            </Section>
          )}

          {tab === "charter" && (
            <Section title="Charte / ton de marque">
              <CharterEditor
                charter={overview.charter}
                saving={busy === "__charter__"}
                onSave={onSaveCharter}
              />
            </Section>
          )}

          {tab === "stats" && (
            <Section title="Engagement social (7 jours)">
              <EngagementStats engagement={overview.engagement} />
            </Section>
          )}
        </>
      )}
    </div>
  );
}
