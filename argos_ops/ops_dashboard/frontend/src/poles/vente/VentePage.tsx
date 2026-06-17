// Page du pôle Vente & RC (archi v2, S4). Onglets : Pipeline (Kanban + risque +
// devis/contrats), Inbox (tri + gate AI Act), Comptes (santé/churn/upsell +
// tickets SLA), Outbound (Bloctel + leads + séquences + upload CSV), RDV (iCal).
// Branché sur /api/poles/vente. Garde-fou Bloctel = bannière + actions gelées.

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  type VenteOverview,
  bookMeeting,
  draftInboxReply,
  draftProposal,
  fetchVenteOverview,
  scaffoldSequence,
  uploadLeads,
} from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import {
  BAND_TONE,
  CATEGORY_LABEL,
  CATEGORY_TONE,
  PRIORITY_TONE,
  dateTime,
  eur,
  pct,
  riskTone,
  shortDate,
  stageLabel,
} from "./lib.ts";

type Tab = "pipeline" | "inbox" | "comptes" | "outbound" | "rdv";

const TABS: { id: Tab; label: string }[] = [
  { id: "pipeline", label: "Pipeline" },
  { id: "inbox", label: "Inbox" },
  { id: "comptes", label: "Comptes & support" },
  { id: "outbound", label: "Outbound" },
  { id: "rdv", label: "RDV" },
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

export function VentePage() {
  const [overview, setOverview] = useState<VenteOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("pipeline");
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; message: string } | null>(
    null,
  );
  const [csv, setCsv] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchVenteOverview(controller.signal)
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

  const onUploadCsv = useCallback(() => {
    const rows = csv
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#") && !l.toLowerCase().startsWith("full_name"))
      .map((l) => {
        const [full_name, domain, title_hint, linkedin_url] = l.split(",").map((c) => c.trim());
        return { full_name, domain, title_hint, linkedin_url };
      })
      .filter((r) => r.full_name && r.domain);
    if (rows.length === 0) {
      setFlash({ variant: "error", message: "Aucune ligne valide (format : nom,domaine,titre)." });
      return;
    }
    setBusy("__csv__");
    setFlash(null);
    uploadLeads(rows)
      .then((res) => {
        setFlash({
          variant: "success",
          message: `${res.added} lead(s) ajouté(s), ${res.skipped} ignoré(s) (doublon/invalide).`,
        });
        setCsv("");
        reload();
      })
      .catch((err: unknown) => {
        setFlash({
          variant: "error",
          message: err instanceof Error ? err.message : "Échec de l'import.",
        });
      })
      .finally(() => setBusy(null));
  }, [csv, reload]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 4/8</span>
            <Badge tone="info">VenteAgent</Badge>
            {overview?.counts.outbound_frozen && <Badge tone="danger">outbound gelé</Badge>}
          </div>
          <Button size="sm" variant="ghost" onClick={reload}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Vente & Relation Client</h1>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat label="Pipe actif" value={eur(overview.counts.pipeline_value_eur)} />
            <Stat
              label="Stalled"
              value={String(overview.counts.stalled)}
              tone={overview.counts.stalled > 0 ? "text-argos-warning" : "text-argos-fg"}
            />
            <Stat
              label="Tickets P0"
              value={String(overview.counts.p0)}
              tone={overview.counts.p0 > 0 ? "text-argos-danger" : "text-argos-fg"}
            />
            <Stat
              label="Churn urgent"
              value={String(overview.counts.churn_urgent)}
              tone={overview.counts.churn_urgent > 0 ? "text-argos-danger" : "text-argos-fg"}
            />
            <Stat
              label="Leads éligibles"
              value={`${overview.counts.eligible_leads}/${overview.counts.leads}`}
            />
          </div>
        )}
      </header>

      {flash && (
        <Flash variant={flash.variant} message={flash.message} onDismiss={() => setFlash(null)} />
      )}

      {loading && <Empty>Chargement du pôle Vente…</Empty>}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {overview && !loading && (
        <>
          {overview.bloctel.should_alert ? (
            <Flash
              variant="error"
              message={`Conformité Bloctel — ${overview.bloctel.summary} L'outbound est gelé (Python tranche).`}
            />
          ) : (
            <div className="rounded-md border border-argos-healthy/30 bg-argos-healthy/10 px-3 py-2 font-mono text-[11px] text-argos-healthy">
              Conformité Bloctel OK — {overview.bloctel.summary}
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

          {tab === "pipeline" && <PipelineTab overview={overview} busy={busy} runMutation={runMutation} />}
          {tab === "inbox" && <InboxTab overview={overview} busy={busy} runMutation={runMutation} />}
          {tab === "comptes" && <ComptesTab overview={overview} />}
          {tab === "outbound" && (
            <OutboundTab
              overview={overview}
              busy={busy}
              runMutation={runMutation}
              csv={csv}
              setCsv={setCsv}
              onUploadCsv={onUploadCsv}
            />
          )}
          {tab === "rdv" && <RdvTab overview={overview} busy={busy} runMutation={runMutation} />}
        </>
      )}
    </div>
  );
}

type MutFn = (key: string, fn: () => Promise<unknown>, okMsg: string) => Promise<void>;

// =============================================================================
// Pipeline (Kanban + devis/contrats)
// =============================================================================
function PipelineTab({
  overview,
  busy,
  runMutation,
}: {
  overview: VenteOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  const stages = overview.stage_order.filter((s) => s !== "lost");
  return (
    <div className="flex flex-col gap-6">
      <Section title="Pipeline (Kanban)">
        <div className="flex gap-3 overflow-x-auto pb-2">
          {stages.map((stage) => {
            const deals = overview.pipeline.filter((d) => d.stage === stage);
            return (
              <div key={stage} className="flex w-56 shrink-0 flex-col gap-2">
                <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
                  <span>{stageLabel(stage)}</span>
                  <span>{deals.length}</span>
                </div>
                {deals.length === 0 ? (
                  <div className="rounded-md border border-dashed border-argos-border-subtle px-2 py-3 text-center font-mono text-[10px] text-argos-fg-disabled">
                    —
                  </div>
                ) : (
                  deals.map((d) => (
                    <div key={d.deal_id} className={CARD}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-mono text-xs text-argos-fg">{d.company}</span>
                        <Badge tone={riskTone(d.risk_score)}>{d.risk_score}</Badge>
                      </div>
                      <span className="font-mono text-[11px] text-argos-fg-secondary">
                        {eur(d.amount_eur)}/an · {d.days_since_activity}j
                      </span>
                      {d.is_stalled && (
                        <span className="font-mono text-[10px] text-argos-warning">⚠ stalled</span>
                      )}
                    </div>
                  ))
                )}
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Devis & contrats">
        {overview.proposals.length === 0 ? (
          <Empty>Aucun deal devis (data/poles/vente/proposals/&lt;deal&gt;/context.yaml).</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {overview.proposals.map((p) => (
              <div key={p.deal_id} className="flex items-center justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2">
                <div className="flex flex-col">
                  <span className="font-mono text-xs text-argos-fg">
                    {p.company} · {p.plan} · {eur(p.monthly_price_eur)}/mois
                  </span>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">{p.deal_id}</span>
                </div>
                <div className="flex items-center gap-2">
                  {p.has_contract && <Badge tone="healthy">contrat</Badge>}
                  {p.has_proposal && <Badge tone="info">devis</Badge>}
                  <Badge tone={p.proposal_status === "sent" ? "healthy" : "neutral"}>
                    {p.proposal_status}
                  </Badge>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busy === p.deal_id}
                    onClick={() =>
                      runMutation(p.deal_id, () => draftProposal(p.deal_id), "Devis drafté.")
                    }
                  >
                    drafter devis
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// =============================================================================
// Inbox (tri + gate AI Act)
// =============================================================================
function InboxTab({
  overview,
  busy,
  runMutation,
}: {
  overview: VenteOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  if (overview.inbox.length === 0) return <Empty>Inbox vide.</Empty>;
  return (
    <Section title={`Inbox triée (${overview.inbox.length})`}>
      <div className="flex flex-col gap-2">
        {overview.inbox.map((m) => (
          <div key={m.id} className="flex items-start justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5">
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={CATEGORY_TONE[m.category] ?? "neutral"}>
                  {CATEGORY_LABEL[m.category] ?? m.category}
                </Badge>
                {m.human_requested && <Badge tone="danger">réponse humaine (AI Act)</Badge>}
                {m.status !== "new" && <Badge tone="neutral">{m.status}</Badge>}
                <span className="font-mono text-[10px] text-argos-fg-tertiary">
                  {shortDate(m.received_at)}
                </span>
              </div>
              <span className="truncate font-mono text-xs text-argos-fg">{m.subject}</span>
              <span className="truncate font-mono text-[10px] text-argos-fg-tertiary">
                {m.from_name} &lt;{m.from_email}&gt;
              </span>
            </div>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy === m.id || m.human_requested || m.category === "spam"}
              title={
                m.human_requested
                  ? "Réponse humaine exigée — drafting IA gelé (AI Act)"
                  : m.category === "spam"
                    ? "Spam — pas de réponse"
                    : "Drafter une réponse"
              }
              onClick={() => runMutation(m.id, () => draftInboxReply(m.id), "Réponse draftée.")}
            >
              drafter
            </Button>
          </div>
        ))}
      </div>
    </Section>
  );
}

// =============================================================================
// Comptes & support (santé / churn / upsell / tickets)
// =============================================================================
function ComptesTab({ overview }: { overview: VenteOverview }) {
  return (
    <div className="flex flex-col gap-6">
      <Section title={`Santé des comptes (${overview.health.length})`}>
        {overview.health.length === 0 ? (
          <Empty>Aucun compte.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {overview.health.map((h) => (
              <div key={h.customer_id} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-argos-fg">{h.customer_id}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-argos-fg-secondary">{h.score}/100</span>
                    <Badge tone={BAND_TONE[h.band] ?? "neutral"}>{h.band}</Badge>
                  </div>
                </div>
                <span className="font-mono text-[10px] text-argos-fg-tertiary">
                  {h.drivers.join(" · ")}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Section title={`Churn (${overview.churn.length})`}>
          {overview.churn.length === 0 ? (
            <Empty>Aucun signal.</Empty>
          ) : (
            overview.churn.map((c) => (
              <div key={c.customer_id} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-argos-fg">{c.customer_id}</span>
                  <Badge tone={c.urgent ? "danger" : "warning"}>{c.risk_score}/100</Badge>
                </div>
                <span className="font-mono text-[10px] text-argos-fg-tertiary">
                  {c.signals.join(" · ")}
                </span>
              </div>
            ))
          )}
        </Section>

        <Section title={`Upsell (${overview.upsell.length})`}>
          {overview.upsell.length === 0 ? (
            <Empty>Aucun candidat.</Empty>
          ) : (
            overview.upsell.map((u) => (
              <div key={u.customer_id} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-argos-fg">{u.customer_id}</span>
                  <Badge tone="info">{pct(u.usage_ratio)} → {u.suggested_plan}</Badge>
                </div>
                <span className="font-mono text-[10px] text-argos-fg-tertiary">{u.reason}</span>
              </div>
            ))
          )}
        </Section>
      </div>

      <Section title={`Tickets support (${overview.tickets.length})`}>
        {overview.tickets.length === 0 ? (
          <Empty>Aucun ticket ouvert.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {overview.tickets.map((t) => (
              <div key={t.ticket_id} className="flex items-center justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2">
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-mono text-xs text-argos-fg">{t.subject}</span>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">
                    {t.customer_id} · SLA {t.sla_response_hours}h
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {t.sla_breached && <Badge tone="danger">SLA dépassé</Badge>}
                  <Badge tone={PRIORITY_TONE[t.priority] ?? "neutral"}>{t.priority}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// =============================================================================
// Outbound (Bloctel + leads + séquences + upload CSV)
// =============================================================================
function OutboundTab({
  overview,
  busy,
  runMutation,
  csv,
  setCsv,
  onUploadCsv,
}: {
  overview: VenteOverview;
  busy: string | null;
  runMutation: MutFn;
  csv: string;
  setCsv: (v: string) => void;
  onUploadCsv: () => void;
}) {
  const frozen = overview.counts.outbound_frozen;
  return (
    <div className="flex flex-col gap-6">
      <Section title="Importer des leads (CSV)">
        <div className="flex flex-col gap-2">
          <textarea
            value={csv}
            onChange={(e) => setCsv(e.target.value)}
            rows={3}
            placeholder="full_name,domain,title_hint&#10;Claire Moreau,secure-corp.fr,RSSI"
            className="rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:border-argos-info/60 focus:outline-none"
          />
          <div>
            <Button size="sm" variant="primary" disabled={busy === "__csv__" || !csv.trim()} onClick={onUploadCsv}>
              importer
            </Button>
          </div>
        </div>
      </Section>

      <Section title={`Leads enrichis (${overview.leads.length})`}>
        {overview.leads.length === 0 ? (
          <Empty>Aucun lead (data/poles/vente/outbound/inbox/leads.csv).</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {overview.leads.map((l) => (
              <div key={l.slug} className="flex items-start justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5">
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-argos-fg">{l.full_name}</span>
                    <Badge tone="neutral">{l.persona}</Badge>
                    <Badge tone={l.bant_total >= 40 ? "healthy" : "warning"}>BANT {l.bant_total}</Badge>
                    {l.eligible ? (
                      <Badge tone="healthy">éligible</Badge>
                    ) : (
                      <Badge tone="danger">inéligible</Badge>
                    )}
                  </div>
                  <span className="truncate font-mono text-[10px] text-argos-fg-tertiary">
                    {l.best_email ?? l.domain} — {l.eligibility_reason}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy === l.slug || !l.eligible || frozen}
                  title={
                    frozen
                      ? "Outbound gelé (Bloctel)"
                      : !l.eligible
                        ? l.eligibility_reason
                        : "Lancer une séquence outbound"
                  }
                  onClick={() => runMutation(l.slug, () => scaffoldSequence(l.slug), "Séquence créée.")}
                >
                  lancer séquence
                </Button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Séquences (${overview.sequences.length})`}>
        {overview.sequences.length === 0 ? (
          <Empty>Aucune séquence scaffoldée.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {overview.sequences.map((s) => (
              <div key={s.slug} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-argos-fg">{s.full_name}</span>
                  <Badge tone="neutral">{s.sequence_status}</Badge>
                </div>
                <div className="flex flex-wrap gap-1">
                  {s.touches.map((t) => (
                    <span
                      key={t.step}
                      className="rounded border border-argos-border-subtle px-1.5 py-0.5 font-mono text-[9px] text-argos-fg-tertiary"
                    >
                      T{t.step} {shortDate(t.scheduled_date)} · {t.status}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// =============================================================================
// RDV (calendrier + book iCal)
// =============================================================================
function RdvTab({
  overview,
  busy,
  runMutation,
}: {
  overview: VenteOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  if (overview.meetings.length === 0) return <Empty>Aucune demande de RDV.</Empty>;
  return (
    <Section title={`Calendrier RDV (${overview.meetings.length})`}>
      <div className="flex flex-col gap-2">
        {overview.meetings.map((m) => (
          <div key={m.request_id} className="flex items-center justify-between gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5">
            <div className="flex min-w-0 flex-col">
              <span className="font-mono text-xs text-argos-fg">
                {dateTime(m.starts_at)} · {m.duration_minutes} min
              </span>
              <span className="truncate font-mono text-[10px] text-argos-fg-tertiary">
                {m.attendee_name} ({m.company}) · {m.location}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={m.status === "pending" ? "warning" : "healthy"}>{m.status}</Badge>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy === m.request_id || m.status !== "pending"}
                onClick={() =>
                  runMutation(m.request_id, () => bookMeeting(m.request_id), "RDV drafté (iCal).")
                }
              >
                drafter (iCal)
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
