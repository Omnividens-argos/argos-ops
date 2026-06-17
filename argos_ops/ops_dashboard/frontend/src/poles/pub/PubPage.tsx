// Page du pôle Pub (archi v2, S3). Branche le shell poles.html sur le backend
// (GET /api/poles/pub/overview + mutations) : dashboard campagnes, jauge budget +
// alerte breaker ad_spend_runaway, recos chiffrées « appliquer » (shadow),
// validation de créas A/B côte à côte, simulateur de budget. Réutilise le thème
// et les composants partagés, et suit le même pattern que MarketingPage.

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  type AdRecommendation,
  type PubOverview,
  applyRecommendation,
  fetchPubOverview,
  goliveCreative,
  rejectCreative,
  resetPubBreaker,
  setPubBudget,
  simulatePubBudget,
  validateCreative,
} from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { ABComparison } from "./ABComparison.tsx";
import { AdRecommendations } from "./AdRecommendations.tsx";
import { BreakerAlert } from "./BreakerAlert.tsx";
import { BudgetGauge } from "./BudgetGauge.tsx";
import { BudgetSimulator } from "./BudgetSimulator.tsx";
import { CampaignTable } from "./CampaignTable.tsx";
import { CreativeQueue } from "./CreativeQueue.tsx";
import { eur } from "./lib.ts";

type Tab = "campaigns" | "creatives" | "simulator";

const TABS: { id: Tab; label: string }[] = [
  { id: "campaigns", label: "Campagnes" },
  { id: "creatives", label: "Créas" },
  { id: "simulator", label: "Simulateur" },
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

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex flex-col">
      <span className={`font-mono text-base font-medium ${tone}`}>{value}</span>
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        {label}
      </span>
    </div>
  );
}

export function PubPage() {
  const [overview, setOverview] = useState<PubOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [tab, setTab] = useState<Tab>("campaigns");
  const [selectedCreativeId, setSelectedCreativeId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchPubOverview(controller.signal)
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
    (id: string) => runMutation(id, () => validateCreative(id), "Créa validée."),
    [runMutation],
  );
  const onReject = useCallback(
    (id: string) => runMutation(id, () => rejectCreative(id), "Créa rejetée."),
    [runMutation],
  );
  const onGoLive = useCallback(
    (id: string) => runMutation(id, () => goliveCreative(id), "Créa en ligne (shadow)."),
    [runMutation],
  );
  const onSetBudget = useCallback(
    (value: number) => runMutation("__budget__", () => setPubBudget(value), "Budget enregistré."),
    [runMutation],
  );
  const onResetBreaker = useCallback(
    () => runMutation("__breaker__", () => resetPubBreaker(), "Breaker réarmé (reset)."),
    [runMutation],
  );
  const onApply = useCallback(
    (rec: AdRecommendation) =>
      runMutation(
        rec.id,
        () =>
          applyRecommendation({
            platform: rec.platform,
            campaign: rec.campaign,
            action: rec.action,
            eur_delta_week: rec.eur_delta_week,
            rationale: rec.rationale,
          }),
        "Reco appliquée (shadow).",
      ),
    [runMutation],
  );

  const selectedCreative = useMemo(() => {
    if (!overview) return null;
    return (
      overview.creatives.find((c) => c.id === selectedCreativeId) ?? overview.creatives[0] ?? null
    );
  }, [overview, selectedCreativeId]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 3/8</span>
            <Badge tone="info">PubAgent</Badge>
            <Badge tone="neutral">lit Veille · Marketing · Finance</Badge>
            <Badge tone="warning">shadow</Badge>
          </div>
          <Button size="sm" variant="ghost" onClick={reload}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Pub</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">
          Acquisition payante : l'optimiseur chiffre les recos, vous appliquez (shadow), le breaker
          ad_spend_runaway tranche, les créas A/B passent par votre validation avant la mise en
          ligne. Aucune dépense réelle tant que le mode live n'est pas armé (D-026).
        </p>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat label="à valider" value={String(overview.counts.draft)} tone="text-argos-warning" />
            <Stat
              label="en ligne"
              value={String(overview.counts.live)}
              tone="text-argos-healthy"
            />
            <Stat
              label="reco critiques"
              value={String(overview.counts.critical)}
              tone="text-argos-danger"
            />
            <Stat
              label="économies pot. /sem"
              value={eur(overview.counts.potential_savings_week_eur)}
              tone="text-argos-healthy"
            />
          </div>
        )}
      </header>

      {flash && (
        <Flash variant={flash.variant} message={flash.message} onDismiss={() => setFlash(null)} />
      )}

      {loading && (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-8 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Chargement du pôle Pub…
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

          {tab === "campaigns" && (
            <>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Section title="Jauge budget">
                  <BudgetGauge
                    budget={overview.budget}
                    busy={busy === "__budget__"}
                    onSetBudget={onSetBudget}
                  />
                </Section>
                <Section title="Circuit breaker ad_spend_runaway">
                  <BreakerAlert
                    budget={overview.budget}
                    busy={busy === "__breaker__"}
                    onReset={onResetBreaker}
                  />
                </Section>
              </div>

              <Section
                title="Recommandations chiffrées"
                hint={`${overview.counts.recommendations} reco · ${overview.counts.applied} appliquée(s)`}
              >
                <AdRecommendations
                  recommendations={overview.recommendations}
                  platforms={overview.platforms}
                  busyId={busy}
                  onApply={onApply}
                />
              </Section>

              <Section title="Performance des campagnes" hint={`${overview.campaigns.length} campagne(s)`}>
                <CampaignTable campaigns={overview.campaigns} platforms={overview.platforms} />
              </Section>
            </>
          )}

          {tab === "creatives" && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_minmax(0,520px)]">
              <Section title="File de créas à valider" hint={`${overview.creatives.length} créa(s)`}>
                <CreativeQueue
                  creatives={overview.creatives}
                  platforms={overview.platforms}
                  selectedId={selectedCreative?.id ?? null}
                  busyId={busy}
                  breakerTripped={overview.budget.breaker_tripped}
                  onSelect={setSelectedCreativeId}
                  onValidate={onValidate}
                  onReject={onReject}
                  onGoLive={onGoLive}
                />
              </Section>
              <Section title="Comparaison A/B">
                <ABComparison creative={selectedCreative} platforms={overview.platforms} />
              </Section>
            </div>
          )}

          {tab === "simulator" && (
            <Section title="Simulateur de budget" hint="projection au CPA observé">
              <BudgetSimulator
                platforms={overview.platforms}
                budget={overview.budget}
                onSimulate={simulatePubBudget}
              />
            </Section>
          )}
        </>
      )}
    </div>
  );
}
