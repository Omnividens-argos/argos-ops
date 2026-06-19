// Page du pôle Finance & Conformité (archi v2, S5). Onglets : Trésorerie (graphes
// MRR/forecast/burn/runway), Flux (tableur éditable), Facturation (impayés +
// dunning), Documents (génération CA3/devis/contrat + preview PDF + upload + export
// comptable), Conformité (échéancier fiscal + registres RGPD/AI Act + contrats +
// incidents). Branché sur /api/poles/finance. Garde-fou conformité = bannière +
// génération de devis/contrat gelée (« Python tranche »).

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import {
  type FinanceFlow,
  type FinanceOverview,
  addFlow,
  deleteFlow,
  draftDunning,
  exportAccounting,
  fetchDoc,
  fetchFinanceOverview,
  financeDocPdfUrl,
  generateDoc,
  updateFlow,
  uploadDoc,
  uploadDocFile,
} from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { FileUpload } from "../../components/FileUpload.tsx";
import { BarChart, DivergingBars, Gauge } from "./charts.tsx";
import {
  AI_ACT_TONE,
  CONTRACT_TONE,
  DOC_KIND_LABEL,
  DUNNING_TONE,
  FISCAL_LABEL,
  deadlineTone,
  eur,
  eur2,
  months,
  shortDate,
  signedEur,
} from "./lib.ts";

type Tab = "tresorerie" | "flux" | "facturation" | "documents" | "conformite";

const TABS: { id: Tab; label: string }[] = [
  { id: "tresorerie", label: "Trésorerie" },
  { id: "flux", label: "Flux" },
  { id: "facturation", label: "Facturation" },
  { id: "documents", label: "Documents" },
  { id: "conformite", label: "Conformité" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {label}
      </span>
      <span className={`font-mono text-lg font-medium ${tone ?? "text-argos-fg"}`}>{value}</span>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
      {children}
    </div>
  );
}

const CARD =
  "flex flex-col gap-1.5 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5";
const ROW =
  "flex items-center justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2";

// Retourne `true` si la mutation a réussi (pour ne réinitialiser un formulaire
// qu'en succès — runMutation absorbe toujours l'erreur, jamais de rejet).
type MutFn = (key: string, fn: () => Promise<unknown>, okMsg: string) => Promise<boolean>;

export function FinancePage() {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("tresorerie");
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; message: string } | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchFinanceOverview(controller.signal)
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

  const runMutation = useCallback<MutFn>(
    async (key, fn, okMsg) => {
      setBusy(key);
      setFlash(null);
      try {
        await fn();
        setFlash({ variant: "success", message: okMsg });
        reload();
        return true;
      } catch (err: unknown) {
        setFlash({
          variant: "error",
          message: err instanceof Error ? err.message : "Échec de l'action.",
        });
        return false;
      } finally {
        setBusy(null);
      }
    },
    [reload],
  );

  const counts = overview?.counts;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 5/8</span>
            <Badge tone="info">FinanceAgent</Badge>
            {counts?.compliance_blocking && <Badge tone="danger">onboarding gelé</Badge>}
          </div>
          <Button size="sm" variant="ghost" onClick={reload}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Finance & Conformité</h1>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat label="MRR" value={eur(overview.billing.mrr_eur)} />
            <Stat label="ARR" value={eur(overview.billing.arr_eur)} />
            <Stat
              label="Runway"
              value={months(overview.treasury.runway_months)}
              tone={
                overview.treasury.severity === "alert"
                  ? "text-argos-danger"
                  : overview.treasury.severity === "warn"
                    ? "text-argos-warning"
                    : "text-argos-fg"
              }
            />
            <Stat
              label="Impayés"
              value={`${overview.billing.n_open_invoices} · ${eur(overview.billing.open_amount_eur)}`}
              tone={overview.billing.n_open_invoices > 0 ? "text-argos-warning" : "text-argos-fg"}
            />
            <Stat
              label="Échéance fiscale"
              value={
                counts?.fiscal_next_days != null ? `J-${counts.fiscal_next_days}` : "—"
              }
              tone={
                counts?.fiscal_next_days != null && counts.fiscal_next_days <= 7
                  ? "text-argos-danger"
                  : "text-argos-fg"
              }
            />
          </div>
        )}
      </header>

      {flash && (
        <Flash variant={flash.variant} message={flash.message} onDismiss={() => setFlash(null)} />
      )}

      {loading && <Empty>Chargement du pôle Finance…</Empty>}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {overview && !loading && (
        <>
          {overview.compliance_blocking ? (
            <Flash
              variant="error"
              message={`Conformité bloquante — ${overview.compliance_reason} L'onboarding d'un nouveau client (devis/contrat) est gelé (Python tranche).`}
            />
          ) : overview.rgpd.should_alert || overview.ai_act.should_alert ? (
            <div className="rounded-md border border-argos-warning/30 bg-argos-warning/10 px-3 py-2 font-mono text-[11px] text-argos-warning">
              Conformité non bloquante mais à régulariser — RGPD : {overview.rgpd.summary} · AI
              Act : {overview.ai_act.summary}
            </div>
          ) : (
            <div className="rounded-md border border-argos-healthy/30 bg-argos-healthy/10 px-3 py-2 font-mono text-[11px] text-argos-healthy">
              Conformité OK — RGPD : {overview.rgpd.summary} · AI Act : {overview.ai_act.summary}
            </div>
          )}

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

          {tab === "tresorerie" && <TresorerieTab overview={overview} />}
          {tab === "flux" && <FluxTab overview={overview} busy={busy} runMutation={runMutation} />}
          {tab === "facturation" && (
            <FacturationTab overview={overview} busy={busy} runMutation={runMutation} />
          )}
          {tab === "documents" && (
            <DocumentsTab overview={overview} busy={busy} runMutation={runMutation} setFlash={setFlash} />
          )}
          {tab === "conformite" && <ConformiteTab overview={overview} />}
        </>
      )}
    </div>
  );
}

// =============================================================================
// Trésorerie (graphes MRR / forecast / burn / runway)
// =============================================================================
function TresorerieTab({ overview }: { overview: FinanceOverview }) {
  const { forecast, treasury, ledger } = overview;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Forecast cash flow (rentrées attendues)">
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-3">
            <BarChart
              format={eur}
              data={[
                { label: "J+30", value: forecast.expected_30d_eur, tone: "healthy" },
                { label: "J+60", value: forecast.expected_60d_eur, tone: "info" },
                { label: "J+90", value: forecast.expected_90d_eur, tone: "info" },
              ]}
            />
          </div>
        </Section>

        <Section title="Burn vs revenu mensuel">
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-3">
            {treasury.present ? (
              <BarChart
                format={eur}
                data={[
                  { label: "Burn", value: treasury.monthly_burn_eur ?? 0, tone: "danger" },
                  { label: "Revenu", value: treasury.monthly_revenue_eur ?? 0, tone: "healthy" },
                ]}
              />
            ) : (
              <Empty>treasury/state.yaml non renseigné.</Empty>
            )}
          </div>
        </Section>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Runway">
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-3">
            <Gauge
              value={treasury.runway_months}
              max={12}
              alert={6}
              warn={9}
              label="mois de trésorerie restants"
              caption={treasury.summary}
            />
          </div>
        </Section>

        <Section title="Cash net par mois (tableur)">
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-3">
            {ledger.by_month.length === 0 ? (
              <Empty>Aucun flux.</Empty>
            ) : (
              <DivergingBars
                format={(v) => eur(v)}
                data={ledger.by_month.map((m) => ({
                  id: m.month,
                  label: m.month.slice(5),
                  value: m.net_eur,
                }))}
              />
            )}
          </div>
        </Section>
      </div>

      <Section title="Synthèse">
        <div className="flex flex-wrap items-center gap-6">
          <Stat label="MRR" value={eur2(overview.billing.mrr_eur)} />
          <Stat label="ARR" value={eur2(overview.billing.arr_eur)} />
          <Stat
            label="Subs actives"
            value={`${overview.billing.n_active_subs}/${overview.billing.n_subs}`}
          />
          <Stat
            label="Net burn"
            value={eur2(treasury.net_burn_eur)}
            tone={treasury.net_burn_eur > 0 ? "text-argos-warning" : "text-argos-healthy"}
          />
          <Stat
            label="Cash"
            value={treasury.cash_balance_eur != null ? eur(treasury.cash_balance_eur) : "—"}
          />
        </div>
      </Section>

      <AuditSection overview={overview} />
    </div>
  );
}

// =============================================================================
// Audit des dépenses (Qonto) + rapprochement bancaire (Stripe ↔ Qonto)
// =============================================================================
function AuditSection({ overview }: { overview: FinanceOverview }) {
  const { expenses, reconcile } = overview;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title="Audit des dépenses (Qonto)">
        {expenses.severity === "ok" || expenses.anomalies.length === 0 ? (
          <div className="rounded-md border border-argos-healthy/30 bg-argos-healthy/10 px-3 py-2 font-mono text-[11px] text-argos-healthy">
            {expenses.summary}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <Flash variant="error" message={expenses.summary} />
            {expenses.anomalies.map((a) => (
              <div key={`${a.vendor}-${a.settled_on}-${a.kind}`} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-argos-fg">{a.vendor}</span>
                  <Badge tone={a.kind === "new_vendor" ? "warning" : "danger"}>{a.kind}</Badge>
                </div>
                <span className="font-mono text-[10px] text-argos-fg-tertiary">
                  {shortDate(a.settled_on)} · {eur2(a.amount_eur)} · {a.reason}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Rapprochement Stripe ↔ Qonto">
        <div className={CARD}>
          <div className="flex flex-wrap items-center gap-4">
            <Stat label="Matchés" value={String(reconcile.matched)} tone="text-argos-healthy" />
            <Stat
              label="Payouts orphelins"
              value={String(reconcile.orphan_payouts)}
              tone={reconcile.orphan_payouts > 0 ? "text-argos-danger" : "text-argos-fg"}
            />
            <Stat
              label="Crédits orphelins"
              value={String(reconcile.orphan_credits)}
              tone={reconcile.orphan_credits > 0 ? "text-argos-warning" : "text-argos-fg"}
            />
          </div>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">{reconcile.summary}</span>
        </div>
      </Section>
    </div>
  );
}

// =============================================================================
// Flux (tableur éditable)
// =============================================================================
function FluxTab({
  overview,
  busy,
  runMutation,
}: {
  overview: FinanceOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  const { ledger } = overview;
  const [date, setDate] = useState("");
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState("revenue");
  const [direction, setDirection] = useState("in");
  const [amount, setAmount] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [eDate, setEDate] = useState("");
  const [eLabel, setELabel] = useState("");
  const [eCategory, setECategory] = useState("");
  const [eDirection, setEDirection] = useState("in");
  const [eAmount, setEAmount] = useState("");

  const inputCls =
    "rounded-md border border-argos-border-subtle bg-argos-bg px-2 py-1 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:border-argos-info/60 focus:outline-none";

  const startEdit = (f: FinanceFlow) => {
    setEditId(f.id);
    setEDate(f.flow_date.slice(0, 10));
    setELabel(f.label);
    setECategory(f.category);
    setEDirection(f.direction === "out" ? "out" : "in");
    setEAmount(String(f.amount_eur));
  };

  const cancelEdit = () => setEditId(null);

  const onSave = (id: string) => {
    const amt = Number(eAmount.replace(",", "."));
    if (!eDate || !eLabel.trim() || !Number.isFinite(amt) || amt <= 0) {
      runMutation(id, () => Promise.reject(new Error("Ligne incomplète (date, libellé, montant > 0).")), "");
      return;
    }
    runMutation(
      id,
      () =>
        updateFlow(id, {
          flow_date: eDate,
          label: eLabel.trim(),
          category: eCategory.trim() || "autre",
          direction: eDirection,
          amount_eur: amt,
        }),
      "Ligne modifiée.",
    ).then((ok) => {
      if (ok) setEditId(null);
    });
  };

  const onAdd = () => {
    const amt = Number(amount.replace(",", "."));
    if (!date || !label.trim() || !Number.isFinite(amt) || amt <= 0) {
      runMutation("__addflow__", () => Promise.reject(new Error("Ligne incomplète (date, libellé, montant > 0).")), "");
      return;
    }
    runMutation(
      "__addflow__",
      () =>
        addFlow({
          flow_date: date,
          label: label.trim(),
          category: category.trim() || "autre",
          direction,
          amount_eur: amt,
        }),
      "Ligne ajoutée.",
    ).then((ok) => {
      if (ok) {
        setLabel("");
        setAmount("");
      }
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <Section title="Ajouter un flux">
        <div className="flex flex-wrap items-end gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="libellé"
            className={`${inputCls} min-w-[10rem] flex-1`}
          />
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="catégorie"
            className={`${inputCls} w-28`}
          />
          <select value={direction} onChange={(e) => setDirection(e.target.value)} className={inputCls}>
            <option value="in">entrée</option>
            <option value="out">sortie</option>
          </select>
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="montant €"
            inputMode="decimal"
            className={`${inputCls} w-24`}
          />
          <Button size="sm" variant="primary" disabled={busy === "__addflow__"} onClick={onAdd}>
            ajouter
          </Button>
        </div>
      </Section>

      <Section title={`Tableur des flux (${ledger.flows.length})`}>
        {ledger.flows.length === 0 ? (
          <Empty>Aucun flux (data/poles/finance/ledger/flows.yaml).</Empty>
        ) : (
          <div className="overflow-x-auto rounded-md border border-argos-border-subtle">
            <table className="w-full border-collapse font-mono text-[11px]">
              <thead>
                <tr className="bg-argos-surface-2 text-argos-fg-tertiary">
                  <th className="px-2 py-1.5 text-left font-normal">Date</th>
                  <th className="px-2 py-1.5 text-left font-normal">Libellé</th>
                  <th className="px-2 py-1.5 text-left font-normal">Catégorie</th>
                  <th className="px-2 py-1.5 text-right font-normal">Montant</th>
                  <th className="px-2 py-1.5 text-right font-normal">Solde</th>
                  <th className="px-2 py-1.5" />
                </tr>
              </thead>
              <tbody>
                {ledger.flows.map((f) =>
                  editId === f.id ? (
                    <tr key={f.id} className="border-t border-argos-border-subtle bg-argos-info/5">
                      <td className="px-2 py-1.5">
                        <input
                          type="date"
                          value={eDate}
                          onChange={(e) => setEDate(e.target.value)}
                          className={inputCls}
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <input
                          value={eLabel}
                          onChange={(e) => setELabel(e.target.value)}
                          placeholder="libellé"
                          className={`${inputCls} w-full`}
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <input
                          value={eCategory}
                          onChange={(e) => setECategory(e.target.value)}
                          placeholder="catégorie"
                          className={`${inputCls} w-24`}
                        />
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <select
                            value={eDirection}
                            onChange={(e) => setEDirection(e.target.value)}
                            className={inputCls}
                            aria-label="sens"
                          >
                            <option value="in">entrée</option>
                            <option value="out">sortie</option>
                          </select>
                          <input
                            value={eAmount}
                            onChange={(e) => setEAmount(e.target.value)}
                            placeholder="montant €"
                            inputMode="decimal"
                            className={`${inputCls} w-20`}
                          />
                        </div>
                      </td>
                      <td className="px-2 py-1.5 text-right text-argos-fg-tertiary">{eur2(f.balance_eur)}</td>
                      <td className="px-2 py-1.5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            disabled={busy === f.id}
                            onClick={() => onSave(f.id)}
                            className="font-mono text-[10px] text-argos-healthy underline decoration-dotted underline-offset-2 hover:text-argos-healthy disabled:opacity-40"
                          >
                            enregistrer
                          </button>
                          <button
                            type="button"
                            onClick={cancelEdit}
                            className="font-mono text-[10px] text-argos-fg-tertiary underline decoration-dotted underline-offset-2 hover:text-argos-fg"
                          >
                            annuler
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr key={f.id} className="border-t border-argos-border-subtle">
                      <td className="px-2 py-1.5 text-argos-fg-secondary">{shortDate(f.flow_date)}</td>
                      <td className="px-2 py-1.5 text-argos-fg">{f.label}</td>
                      <td className="px-2 py-1.5 text-argos-fg-tertiary">{f.category}</td>
                      <td
                        className={`px-2 py-1.5 text-right ${f.direction === "in" ? "text-argos-healthy" : "text-argos-fg-secondary"}`}
                      >
                        {f.direction === "in" ? "+" : "−"}
                        {eur2(f.amount_eur)}
                      </td>
                      <td className="px-2 py-1.5 text-right text-argos-fg">{eur2(f.balance_eur)}</td>
                      <td className="px-2 py-1.5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            disabled={busy === f.id || editId !== null}
                            onClick={() => startEdit(f)}
                            className="font-mono text-[10px] text-argos-info/80 underline decoration-dotted underline-offset-2 hover:text-argos-info disabled:opacity-40"
                          >
                            éditer
                          </button>
                          <button
                            type="button"
                            disabled={busy === f.id}
                            onClick={() =>
                              runMutation(f.id, () => deleteFlow(f.id), "Ligne supprimée.")
                            }
                            className="font-mono text-[10px] text-argos-danger/80 underline decoration-dotted underline-offset-2 hover:text-argos-danger disabled:opacity-40"
                          >
                            suppr
                          </button>
                        </div>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <div className="flex flex-wrap items-center gap-6">
        <Stat label="Total entrées" value={eur2(ledger.total_in_eur)} tone="text-argos-healthy" />
        <Stat label="Total sorties" value={eur2(ledger.total_out_eur)} tone="text-argos-fg-secondary" />
        <Stat
          label="Net"
          value={signedEur(ledger.net_eur)}
          tone={ledger.net_eur >= 0 ? "text-argos-healthy" : "text-argos-danger"}
        />
      </div>

      {ledger.by_category.length > 0 && (
        <Section title="Net par catégorie">
          <div className="flex flex-wrap gap-2">
            {ledger.by_category.map((c) => (
              <Badge key={c.category} tone={c.net_eur >= 0 ? "healthy" : "neutral"}>
                {c.category} : {signedEur(c.net_eur)}
              </Badge>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

// =============================================================================
// Facturation (impayés + dunning)
// =============================================================================
function FacturationTab({
  overview,
  busy,
  runMutation,
}: {
  overview: FinanceOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  const { billing } = overview;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-6">
        <Stat label="Subs actives" value={`${billing.n_active_subs}/${billing.n_subs}`} />
        <Stat label="Factures impayées" value={String(billing.n_open_invoices)} />
        <Stat label="Montant impayé" value={eur2(billing.open_amount_eur)} tone={billing.open_amount_eur > 0 ? "text-argos-warning" : "text-argos-fg"} />
      </div>

      <Section title={`Relances dunning (${billing.dunning.length})`}>
        {billing.dunning.length === 0 ? (
          <Empty>Aucune facture impayée.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {billing.dunning.map((d) => (
              <div key={d.invoice_id} className={ROW}>
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={DUNNING_TONE[d.level] ?? "neutral"}>{d.level}</Badge>
                    <span className="font-mono text-xs text-argos-fg">{d.customer}</span>
                    {d.drafted && <Badge tone="info">relance draftée</Badge>}
                  </div>
                  <span className="truncate font-mono text-[10px] text-argos-fg-tertiary">
                    {d.invoice_id} · {eur2(d.amount_due_eur)} · échéance {shortDate(d.due_date)}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy === d.invoice_id || d.level === "none"}
                  title={d.level === "none" ? "Pas encore en retard" : "Drafter une relance (shadow)"}
                  onClick={() =>
                    runMutation(
                      d.invoice_id,
                      () => draftDunning(d.invoice_id),
                      "Relance draftée (shadow).",
                    )
                  }
                >
                  drafter relance
                </Button>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// =============================================================================
// Documents (génération + preview + upload + export)
// =============================================================================
function DocumentsTab({
  overview,
  busy,
  runMutation,
  setFlash,
}: {
  overview: FinanceOverview;
  busy: string | null;
  runMutation: MutFn;
  setFlash: (f: { variant: "success" | "error"; message: string } | null) => void;
}) {
  const [preview, setPreview] = useState<{ name: string; content: string } | null>(null);
  const [upName, setUpName] = useState("");
  const [upContent, setUpContent] = useState("");
  const frozen = overview.compliance_blocking;

  const onPreview = (name: string) => {
    setFlash(null);
    fetchDoc(name)
      .then((doc) => setPreview(doc))
      .catch((err: unknown) =>
        setFlash({
          variant: "error",
          message: err instanceof Error ? err.message : "Preview indisponible.",
        }),
      );
  };

  const onExport = () => {
    runMutation("__export__", async () => {
      const res = await exportAccounting();
      try {
        const blob = new Blob([res.csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = res.path;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        /* environnement sans DOM download — le CSV est déjà écrit côté serveur */
      }
    }, "Export comptable généré.");
  };

  return (
    <div className="flex flex-col gap-6">
      <Section title="Générer un document">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            disabled={busy === "ca3"}
            onClick={() => runMutation("ca3", () => generateDoc("ca3"), "CA3 générée.")}
          >
            générer CA3 (TVA)
          </Button>
          <Button size="sm" variant="secondary" disabled={busy === "__export__"} onClick={onExport}>
            export comptable (CSV)
          </Button>
        </div>
        {overview.contexts.length > 0 && (
          <div className="mt-1 flex flex-col gap-2">
            {overview.contexts.map((ctx) => (
              <div key={ctx} className={ROW}>
                <span className="font-mono text-xs text-argos-fg">{ctx}</span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busy === `devis-${ctx}` || frozen}
                    title={frozen ? "Onboarding gelé (conformité)" : "Générer le devis"}
                    onClick={() =>
                      runMutation(`devis-${ctx}`, () => generateDoc("proposal", ctx), "Devis généré.")
                    }
                  >
                    devis
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busy === `contrat-${ctx}` || frozen}
                    title={frozen ? "Onboarding gelé (conformité)" : "Générer le contrat"}
                    onClick={() =>
                      runMutation(`contrat-${ctx}`, () => generateDoc("contract", ctx), "Contrat généré.")
                    }
                  >
                    contrat
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Documents générés (${overview.docs.length})`}>
        {overview.docs.length === 0 ? (
          <Empty>Aucun document. Génère une CA3 ou un devis ci-dessus.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {overview.docs.map((d) => (
              <div key={d.name} className={ROW}>
                <div className="flex items-center gap-2">
                  <Badge tone="neutral">{DOC_KIND_LABEL[d.kind] ?? d.kind}</Badge>
                  <span className="font-mono text-xs text-argos-fg">{d.name}</span>
                  {d.has_pdf ? (
                    <Badge tone="healthy">PDF ✓</Badge>
                  ) : (
                    <Badge tone="neutral">Markdown</Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {d.has_pdf && (
                    <a
                      href={financeDocPdfUrl(d.name)}
                      download
                      className="inline-flex items-center gap-1 rounded-md border border-argos-border-subtle bg-argos-surface-2 px-2.5 py-1 font-mono text-[11px] text-argos-fg-secondary transition-colors hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
                    >
                      <Download className="h-3 w-3" aria-hidden /> PDF
                    </a>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => onPreview(d.name)}>
                    preview
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {preview && (
        <Section title={`Aperçu — ${preview.name}`}>
          <div className="relative">
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="absolute right-2 top-2 font-mono text-[10px] text-argos-fg-tertiary underline decoration-dotted hover:text-argos-fg"
            >
              fermer
            </button>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-argos-border-subtle bg-argos-bg p-3 font-mono text-[11px] leading-relaxed text-argos-fg-secondary">
              {preview.content}
            </pre>
          </div>
        </Section>
      )}

      <Section title="Uploader un document à remplir">
        <FileUpload
          label="Glisser un fichier (PDF, DOCX…) ou cliquer pour parcourir"
          hint="Fichier binaire versionné automatiquement côté serveur (docs/uploads/)."
          maxSizeMb={10}
          onFile={(file) => {
            void runMutation("__upfile__", () => uploadDocFile(file), `Fichier « ${file.name} » uploadé.`);
          }}
        />
        <p className="mt-1 text-[11px] text-argos-fg-tertiary">Ou créer une note texte à remplir :</p>
        <div className="flex flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5">
          <input
            value={upName}
            onChange={(e) => setUpName(e.target.value)}
            placeholder="nom du fichier (ex. kbis-2026.md)"
            className="rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:border-argos-info/60 focus:outline-none"
          />
          <textarea
            value={upContent}
            onChange={(e) => setUpContent(e.target.value)}
            rows={3}
            placeholder="contenu / notes du document à remplir…"
            className="rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:border-argos-info/60 focus:outline-none"
          />
          <div>
            <Button
              size="sm"
              variant="primary"
              disabled={busy === "__upload__" || !upName.trim()}
              onClick={() =>
                runMutation(
                  "__upload__",
                  () => uploadDoc(upName.trim(), upContent),
                  "Document uploadé (docs/uploads/).",
                ).then((ok) => {
                  if (ok) {
                    setUpName("");
                    setUpContent("");
                  }
                })
              }
            >
              uploader
            </Button>
          </div>
        </div>
        {overview.uploads.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {overview.uploads.map((u) => (
              <Badge key={u} tone="neutral">
                {DOC_KIND_LABEL.upload} · {u}
              </Badge>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// =============================================================================
// Conformité (échéancier fiscal + registres RGPD/AI Act + contrats + incidents)
// =============================================================================
function ConformiteTab({ overview }: { overview: FinanceOverview }) {
  const { fiscal, rgpd, ai_act, contracts, incidents } = overview;
  return (
    <div className="flex flex-col gap-6">
      <Section title={`Échéancier fiscal (${fiscal.length})`}>
        {fiscal.length === 0 ? (
          <Empty>Aucune échéance dans les 120 jours.</Empty>
        ) : (
          <div className="flex flex-col gap-1.5">
            {fiscal.map((f) => (
              <div key={`${f.kind}-${f.label}`} className={ROW}>
                <div className="flex items-center gap-2">
                  <Badge tone="neutral">{FISCAL_LABEL[f.kind] ?? f.kind}</Badge>
                  <span className="font-mono text-xs text-argos-fg">{f.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">{shortDate(f.due_date)}</span>
                  <Badge tone={deadlineTone(f.days_until)}>J-{f.days_until}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title={`Registre RGPD (${rgpd.treatments.length})`}>
          {!rgpd.present ? (
            <Flash variant="error" message={rgpd.summary} />
          ) : rgpd.treatments.length === 0 ? (
            <Empty>Registre vide.</Empty>
          ) : (
            <div className="flex flex-col gap-2">
              {rgpd.treatments.map((t) => (
                <div key={t.nom} className={CARD}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs text-argos-fg">{t.nom}</span>
                    <Badge tone={t.conforme ? "healthy" : "danger"}>
                      {t.conforme ? "conforme" : "gap"}
                    </Badge>
                  </div>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">
                    {t.base_legale} · {t.donnees.join(", ")}
                  </span>
                  {t.issues.length > 0 && (
                    <span className="font-mono text-[10px] text-argos-danger">
                      {t.issues.join(" · ")}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title={`Registre AI Act (${ai_act.systems.length})`}>
          {!ai_act.present ? (
            <Flash variant="error" message={ai_act.summary} />
          ) : ai_act.systems.length === 0 ? (
            <Empty>Registre vide.</Empty>
          ) : (
            <div className="flex flex-col gap-2">
              {ai_act.systems.map((s) => (
                <div key={s.nom} className={CARD}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs text-argos-fg">{s.nom}</span>
                    <Badge tone={AI_ACT_TONE[s.risk] ?? "neutral"}>{s.risk}</Badge>
                  </div>
                  {s.role && (
                    <span className="font-mono text-[10px] text-argos-fg-tertiary">{s.role}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title={`Contrats fournisseurs (${contracts.vendors.length})`}>
          {contracts.vendors.length === 0 ? (
            <Empty>Aucun contrat fournisseur.</Empty>
          ) : (
            contracts.vendors.map((c) => (
              <div key={c.vendor} className={ROW}>
                <div className="flex min-w-0 flex-col">
                  <span className="font-mono text-xs text-argos-fg">{c.vendor}</span>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">
                    annulation avant {shortDate(c.deadline_date)} · {eur(c.monthly_cost_eur)}/mois
                  </span>
                </div>
                <Badge tone={CONTRACT_TONE[c.status] ?? "neutral"}>
                  {c.status} (J{c.days_until >= 0 ? "+" : ""}
                  {c.days_until})
                </Badge>
              </div>
            ))
          )}
        </Section>

        <Section title={`Contrats clients (${contracts.clients.length})`}>
          {contracts.clients.length === 0 ? (
            <Empty>Aucun contrat client.</Empty>
          ) : (
            contracts.clients.map((c) => (
              <div key={c.client} className={ROW}>
                <div className="flex min-w-0 flex-col">
                  <span className="font-mono text-xs text-argos-fg">{c.client}</span>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">
                    renouvellement {shortDate(c.next_renewal)}
                  </span>
                </div>
                <Badge tone={CONTRACT_TONE[c.status] ?? "neutral"}>
                  {c.status} (J{c.days_left >= 0 ? "+" : ""}
                  {c.days_left})
                </Badge>
              </div>
            ))
          )}
        </Section>
      </div>

      <Section title={`Incidents (${incidents.length})`}>
        {incidents.length === 0 ? (
          <Empty>Aucun incident enregistré.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {incidents.map((i) => (
              <div key={i.slug} className={ROW}>
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-mono text-xs text-argos-fg">{i.title}</span>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">
                    {i.date} · {i.category}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={i.severity === "P0" || i.severity === "P1" ? "danger" : "warning"}>
                    {i.severity}
                  </Badge>
                  <Badge tone={i.status === "open" ? "warning" : "healthy"}>{i.status}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
