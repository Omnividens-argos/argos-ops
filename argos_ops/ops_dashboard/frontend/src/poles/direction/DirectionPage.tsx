// Page du pôle Direction (archi v2, S6). Chef d'orchestre de la flotte. Onglets :
// Synthèse (garde-fou publication + synthèse semaine + santé flotte + KPI), OKR
// (progression vs prorata, édition de l'actual), Board (métriques board pack +
// génération + export + preview docs), Publications (journal des décisions +
// changelog + roadmap + release notes, gelés si bug P0 / pôle critique), Flotte
// (drill-down par pôle + bugs + feedback + plan d'oversight). Branché sur
// /api/poles/direction. Garde-fou « gel de publication » = bannière rouge +
// boutons de publication désactivés (« Python tranche »).

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import {
  type DirectionOverview,
  type KeyResultOut,
  addDecision,
  directionDocPdfUrl,
  exportBoard,
  fetchDirectionDoc,
  fetchDirectionOverview,
  generateDirectionDoc,
  updateOkr,
} from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import {
  DOC_KIND_LABEL,
  HEALTH_TONE,
  OKR_STATUS_TONE,
  SEVERITY_TONE,
  eur,
  healthIcon,
  months,
  okrBarWidth,
  okrRatioToPct,
  pct,
  shortDate,
} from "./lib.ts";

type Tab = "synthese" | "okr" | "board" | "publications" | "flotte";

const TABS: { id: Tab; label: string }[] = [
  { id: "synthese", label: "Synthèse" },
  { id: "okr", label: "OKR" },
  { id: "board", label: "Board" },
  { id: "publications", label: "Publications" },
  { id: "flotte", label: "Flotte" },
];

type BadgeTone = "neutral" | "info" | "healthy" | "warning" | "danger";

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

const HEALTH_DOT: Record<string, string> = {
  critical: "text-argos-danger",
  warning: "text-argos-warning",
  healthy: "text-argos-healthy",
  idle: "text-argos-fg-disabled",
};

// Retourne `true` si la mutation a réussi (pour ne réinitialiser un formulaire
// qu'en succès — runMutation absorbe toujours l'erreur, jamais de rejet).
type MutFn = (key: string, fn: () => Promise<unknown>, okMsg: string) => Promise<boolean>;

export function DirectionPage() {
  const [overview, setOverview] = useState<DirectionOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("synthese");
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; message: string } | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchDirectionOverview(controller.signal)
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
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 6/8</span>
            <Badge tone="info">DirectionAgent</Badge>
            {counts?.release_blocking && <Badge tone="danger">publication gelée</Badge>}
          </div>
          <Button size="sm" variant="ghost" onClick={reload}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Direction</h1>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat
              label="Pôles actifs"
              value={`${overview.fleet.poles_active}/${overview.fleet.poles.length}`}
            />
            <Stat
              label="Pôles rouges"
              value={String(overview.fleet.poles_red)}
              tone={overview.fleet.poles_red > 0 ? "text-argos-danger" : "text-argos-fg"}
            />
            <Stat
              label="Faits critiques"
              value={String(overview.fleet.total_critical)}
              tone={overview.fleet.total_critical > 0 ? "text-argos-warning" : "text-argos-fg"}
            />
            <Stat
              label="Bugs P0"
              value={String(overview.bugs.p0)}
              tone={overview.bugs.p0 > 0 ? "text-argos-danger" : "text-argos-fg"}
            />
            <Stat
              label="Actions critiques"
              value={String(overview.counts.actions_critical)}
              tone={overview.counts.actions_critical > 0 ? "text-argos-danger" : "text-argos-fg"}
            />
          </div>
        )}
      </header>

      {flash && (
        <Flash variant={flash.variant} message={flash.message} onDismiss={() => setFlash(null)} />
      )}

      {loading && <Empty>Chargement du pôle Direction…</Empty>}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {overview && !loading && (
        <>
          {overview.release_blocking && (
            <div className="flex items-start gap-3 rounded-md border border-argos-danger/50 bg-argos-danger/15 px-4 py-3">
              <span className="font-mono text-base leading-none text-argos-danger">⛔</span>
              <div className="flex flex-col gap-1">
                <span className="font-mono text-xs font-medium uppercase tracking-widest text-argos-danger">
                  Publication gelée
                </span>
                <span className="font-mono text-[11px] leading-relaxed text-argos-danger">
                  {overview.release_reason} — la génération de roadmap / changelog / release notes
                  est bloquée (Python tranche).
                </span>
              </div>
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

          {tab === "synthese" && <SyntheseTab overview={overview} />}
          {tab === "okr" && <OkrTab overview={overview} busy={busy} runMutation={runMutation} />}
          {tab === "board" && (
            <BoardTab overview={overview} busy={busy} runMutation={runMutation} setFlash={setFlash} />
          )}
          {tab === "publications" && (
            <PublicationsTab overview={overview} busy={busy} runMutation={runMutation} />
          )}
          {tab === "flotte" && <FlotteTab overview={overview} />}
        </>
      )}
    </div>
  );
}

// =============================================================================
// Synthèse (garde-fou + synthèse semaine + santé flotte + KPI)
// =============================================================================
function SyntheseTab({ overview }: { overview: DirectionOverview }) {
  const { synthesis, fleet, counts, bugs } = overview;
  return (
    <div className="flex flex-col gap-6">
      <Section title="Synthèse de la semaine">
        <div className={CARD}>
          <span className="font-mono text-sm font-medium text-argos-fg">{synthesis.headline}</span>
          <p className="font-mono text-[11px] leading-relaxed text-argos-fg-secondary">
            {synthesis.narrative}
          </p>
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={`Points forts (${synthesis.highlights.length})`}>
          {synthesis.highlights.length === 0 ? (
            <Empty>Aucun point fort cette semaine.</Empty>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {synthesis.highlights.map((h, i) => (
                <li
                  key={`hl-${i}`}
                  className="flex items-start gap-2 rounded-md border border-argos-healthy/30 bg-argos-healthy/10 px-3 py-1.5 font-mono text-[11px] text-argos-healthy"
                >
                  <span aria-hidden>▸</span>
                  <span className="text-argos-fg-secondary">{h}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title={`Risques (${synthesis.risks.length})`}>
          {synthesis.risks.length === 0 ? (
            <Empty>Aucun risque identifié.</Empty>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {synthesis.risks.map((r, i) => (
                <li
                  key={`rk-${i}`}
                  className="flex items-start gap-2 rounded-md border border-argos-danger/30 bg-argos-danger/10 px-3 py-1.5 font-mono text-[11px] text-argos-danger"
                >
                  <span aria-hidden>▸</span>
                  <span className="text-argos-fg-secondary">{r}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      <Section title={`Santé de la flotte (${fleet.poles.length} pôles)`}>
        {fleet.poles.length === 0 ? (
          <Empty>Aucun pôle dans le snapshot.</Empty>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {fleet.poles.map((p) => (
              <div key={p.pole} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span className={`text-xs leading-none ${HEALTH_DOT[p.health] ?? ""}`} aria-hidden>
                      {healthIcon(p.health)}
                    </span>
                    <span className="truncate font-mono text-xs text-argos-fg">{p.name}</span>
                  </div>
                  <Badge tone={HEALTH_TONE[p.health] ?? "neutral"}>{p.health}</Badge>
                </div>
                <span className="font-mono text-[10px] text-argos-fg-tertiary">
                  {p.n_facts} faits · {p.n_important} importants · {p.n_critical} critiques
                </span>
                {p.headline && (
                  <span className="font-mono text-[10px] leading-snug text-argos-fg-secondary">
                    {p.headline}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Indicateurs flotte">
        <div className="flex flex-wrap items-center gap-6">
          <Stat label="Pôles actifs" value={String(counts.poles_active)} />
          <Stat
            label="Pôles rouges"
            value={String(counts.poles_red)}
            tone={counts.poles_red > 0 ? "text-argos-danger" : "text-argos-healthy"}
          />
          <Stat
            label="Faits critiques"
            value={String(counts.fleet_critical)}
            tone={counts.fleet_critical > 0 ? "text-argos-warning" : "text-argos-fg"}
          />
          <Stat
            label="Bugs P0"
            value={String(bugs.p0)}
            tone={bugs.p0 > 0 ? "text-argos-danger" : "text-argos-healthy"}
          />
          <Stat
            label="Actions critiques"
            value={String(counts.actions_critical)}
            tone={counts.actions_critical > 0 ? "text-argos-danger" : "text-argos-fg"}
          />
        </div>
      </Section>
    </div>
  );
}

// =============================================================================
// OKR (progression vs prorata + édition de l'actual)
// =============================================================================
function OkrTab({
  overview,
  busy,
  runMutation,
}: {
  overview: DirectionOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  const { okr } = overview;
  // Regroupement par objectif (ordre stable d'apparition).
  const objectives: { objective: string; krs: KeyResultOut[] }[] = [];
  for (const kr of okr.key_results) {
    let bucket = objectives.find((o) => o.objective === kr.objective);
    if (!bucket) {
      bucket = { objective: kr.objective, krs: [] };
      objectives.push(bucket);
    }
    bucket.krs.push(kr);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone="info">{okr.quarter}</Badge>
        <span className="font-mono text-[11px] text-argos-fg-secondary">{okr.summary}</span>
      </div>

      {okr.key_results.length === 0 ? (
        <Empty>Aucun OKR défini (data/poles/direction/okr/objectives.yaml).</Empty>
      ) : (
        objectives.map((o) => (
          <Section key={o.objective} title={o.objective}>
            <div className="flex flex-col gap-2">
              {o.krs.map((kr) => (
                <KeyResultRow
                  key={`${kr.objective}::${kr.name}`}
                  kr={kr}
                  busy={busy}
                  runMutation={runMutation}
                />
              ))}
            </div>
          </Section>
        ))
      )}
    </div>
  );
}

function KeyResultRow({
  kr,
  busy,
  runMutation,
}: {
  kr: KeyResultOut;
  busy: string | null;
  runMutation: MutFn;
}) {
  const [actual, setActual] = useState(String(kr.actual));
  // Re-sync l'input quand la valeur serveur bouge (refresh / édition externe) ;
  // une saisie en cours n'est écrasée que si le serveur a réellement changé.
  useEffect(() => setActual(String(kr.actual)), [kr.actual]);
  const key = `okr-${kr.objective}::${kr.name}`;
  // progress_pct / expected_pct sont des RATIOS (0..1) -> on les passe en % (×100).
  const progress = okrBarWidth(kr.progress_pct);
  const expected = okrBarWidth(kr.expected_pct);
  const tone = OKR_STATUS_TONE[kr.status] ?? "neutral";
  const barColor =
    tone === "danger"
      ? "bg-argos-danger/70"
      : tone === "warning"
        ? "bg-argos-warning/70"
        : tone === "info"
          ? "bg-argos-info/70"
          : "bg-argos-healthy/70";

  const onSave = () => {
    const val = Number(actual.replace(",", "."));
    if (!Number.isFinite(val)) {
      runMutation(key, () => Promise.reject(new Error("Valeur « actual » invalide.")), "");
      return;
    }
    runMutation(key, () => updateOkr(kr.objective, kr.name, val), "OKR mis à jour.");
  };

  return (
    <div className={CARD}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-xs text-argos-fg">{kr.name}</span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {kr.actual.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} /{" "}
            {kr.target.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} {kr.unit}
          </span>
          <Badge tone={tone as BadgeTone}>{kr.status}</Badge>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-argos-surface-2">
          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${progress}%` }} />
          {/* Marqueur de prorata temporis (où l'on devrait être). */}
          <div
            className="absolute top-0 h-full w-px bg-argos-fg/70"
            style={{ left: `${expected}%` }}
            title={`prorata attendu ${okrRatioToPct(kr.expected_pct)} %`}
          />
        </div>
        <span className="w-24 text-right font-mono text-[10px] text-argos-fg-tertiary">
          {okrRatioToPct(kr.progress_pct)} % / att. {okrRatioToPct(kr.expected_pct)} %
        </span>
      </div>

      <div className="flex items-center gap-2">
        <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          actual
        </label>
        <input
          value={actual}
          onChange={(e) => setActual(e.target.value)}
          inputMode="decimal"
          className="w-28 rounded-md border border-argos-border-subtle bg-argos-bg px-2 py-1 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:border-argos-info/60 focus:outline-none"
        />
        <Button size="sm" variant="primary" disabled={busy === key} onClick={onSave}>
          enregistrer
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// Board (métriques board pack + génération + export + preview docs)
// =============================================================================
function BoardTab({
  overview,
  busy,
  runMutation,
  setFlash,
}: {
  overview: DirectionOverview;
  busy: string | null;
  runMutation: MutFn;
  setFlash: (f: { variant: "success" | "error"; message: string } | null) => void;
}) {
  const { board, docs } = overview;
  const [preview, setPreview] = useState<{ name: string; content: string } | null>(null);
  const [exported, setExported] = useState<string | null>(null);

  const onPreview = (name: string) => {
    setFlash(null);
    fetchDirectionDoc(name)
      .then((doc) => {
        setExported(null);
        setPreview(doc);
      })
      .catch((err: unknown) =>
        setFlash({
          variant: "error",
          message: err instanceof Error ? err.message : "Preview indisponible.",
        }),
      );
  };

  const onExport = () => {
    runMutation("__export__", async () => {
      const res = await exportBoard();
      setPreview(null);
      setExported(res.markdown);
      try {
        const blob = new Blob([res.markdown], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = res.path;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        /* environnement sans DOM download — le markdown reste affiché ci-dessous */
      }
    }, "Board pack exporté (markdown).");
  };

  return (
    <div className="flex flex-col gap-6">
      <Section title={`Board pack — ${board.period}`}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className={CARD}>
            <Stat label="MRR" value={eur(board.mrr_eur)} />
          </div>
          <div className={CARD}>
            <Stat label="ARR" value={eur(board.arr_eur)} />
          </div>
          <div className={CARD}>
            <Stat
              label="Burn / mois"
              value={eur(board.burn_eur)}
              tone={board.burn_eur != null && board.burn_eur > 0 ? "text-argos-warning" : undefined}
            />
          </div>
          <div className={CARD}>
            <Stat
              label="Runway"
              value={months(board.runway_months)}
              tone={
                board.runway_months != null && board.runway_months < 6
                  ? "text-argos-danger"
                  : board.runway_months != null && board.runway_months < 9
                    ? "text-argos-warning"
                    : undefined
              }
            />
          </div>
          <div className={CARD}>
            <Stat
              label="NRR"
              value={pct(board.nrr_pct)}
              tone={
                board.nrr_pct != null && board.nrr_pct < 100 ? "text-argos-warning" : undefined
              }
            />
          </div>
          <div className={CARD}>
            <Stat label="Faits mémoire (flotte)" value={String(board.runs_month)} />
          </div>
          <div className={CARD}>
            <Stat
              label="Pôles en alerte"
              value={String(board.breakers_tripped)}
              tone={board.breakers_tripped > 0 ? "text-argos-danger" : undefined}
            />
          </div>
          <div className={CARD}>
            <Stat
              label="Incidents (mois)"
              value={String(board.incidents_month)}
              tone={board.incidents_month > 0 ? "text-argos-warning" : undefined}
            />
          </div>
        </div>
      </Section>

      <Section title="Générer / exporter">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            disabled={busy === "board"}
            onClick={() =>
              runMutation("board", () => generateDirectionDoc("board"), "Board pack généré.")
            }
          >
            générer le board pack
          </Button>
          <Button size="sm" variant="secondary" disabled={busy === "__export__"} onClick={onExport}>
            exporter (markdown)
          </Button>
        </div>
      </Section>

      <Section title={`Documents générés (${docs.length})`}>
        {docs.length === 0 ? (
          <Empty>Aucun document. Génère un board pack ci-dessus.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {docs.map((d) => (
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
                      href={directionDocPdfUrl(d.name)}
                      download
                      aria-label={`Télécharger le PDF de ${d.name}`}
                      className="inline-flex items-center gap-1 rounded-md border border-argos-border bg-argos-surface-2 px-2.5 py-1 font-mono text-[11px] text-argos-fg-secondary transition-colors hover:bg-argos-surface hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
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

      {(preview || exported) && (
        <Section title={preview ? `Aperçu — ${preview.name}` : "Board pack exporté"}>
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setPreview(null);
                setExported(null);
              }}
              className="absolute right-2 top-2 font-mono text-[10px] text-argos-fg-tertiary underline decoration-dotted hover:text-argos-fg"
            >
              fermer
            </button>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-argos-border-subtle bg-argos-bg p-3 font-mono text-[11px] leading-relaxed text-argos-fg-secondary">
              {preview ? preview.content : exported}
            </pre>
          </div>
        </Section>
      )}
    </div>
  );
}

// =============================================================================
// Publications (décisions + changelog + roadmap + release notes, gel publication)
// =============================================================================
function PublicationsTab({
  overview,
  busy,
  runMutation,
}: {
  overview: DirectionOverview;
  busy: string | null;
  runMutation: MutFn;
}) {
  const { decisions, changelog, roadmap, release_blocking, release_reason } = overview;
  const frozenTitle = release_blocking
    ? `Publication gelée — ${release_reason}`
    : "Générer (artefact public)";

  const [title, setTitle] = useState("");
  const [partie, setPartie] = useState("direction");
  const [decision, setDecision] = useState("");
  const [pourquoi, setPourquoi] = useState("");

  const inputCls =
    "rounded-md border border-argos-border-subtle bg-argos-bg px-2.5 py-1.5 font-mono text-[11px] text-argos-fg placeholder:text-argos-fg-disabled focus:border-argos-info/60 focus:outline-none";

  const onAddDecision = () => {
    if (!title.trim() || !decision.trim()) {
      runMutation(
        "__decision__",
        () => Promise.reject(new Error("Titre et décision requis.")),
        "",
      );
      return;
    }
    runMutation(
      "__decision__",
      () =>
        addDecision({
          title: title.trim(),
          partie: partie.trim() || "direction",
          decision: decision.trim(),
          pourquoi: pourquoi.trim(),
        }),
      "Décision ajoutée au journal.",
    ).then((ok) => {
      if (ok) {
        setTitle("");
        setDecision("");
        setPourquoi("");
      }
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <Section title={`Journal des décisions (${decisions.length})`}>
        {decisions.length === 0 ? (
          <Empty>Aucune décision enregistrée.</Empty>
        ) : (
          <ol className="flex flex-col gap-2">
            {decisions.map((d) => (
              <li key={d.decision_id} className="flex gap-3">
                <div className="flex flex-col items-center pt-1">
                  <span className="h-2 w-2 rounded-full bg-argos-info" aria-hidden />
                  <span className="mt-0.5 w-px flex-1 bg-argos-border-subtle" aria-hidden />
                </div>
                <div className="flex flex-1 flex-col gap-1 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">{d.decision_id}</Badge>
                    <span className="font-mono text-xs text-argos-fg">{d.title}</span>
                  </div>
                  <span className="font-mono text-[10px] text-argos-fg-tertiary">
                    {shortDate(d.decision_date)} · {d.partie}
                  </span>
                  <span className="font-mono text-[11px] leading-snug text-argos-fg-secondary">
                    {d.decision}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Ajouter une décision">
        <div className="flex flex-col gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5">
          <div className="flex flex-wrap gap-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="titre"
              className={`${inputCls} min-w-[12rem] flex-1`}
            />
            <input
              value={partie}
              onChange={(e) => setPartie(e.target.value)}
              placeholder="partie"
              className={`${inputCls} w-32`}
            />
          </div>
          <textarea
            value={decision}
            onChange={(e) => setDecision(e.target.value)}
            rows={2}
            placeholder="décision actée…"
            className={inputCls}
          />
          <textarea
            value={pourquoi}
            onChange={(e) => setPourquoi(e.target.value)}
            rows={2}
            placeholder="pourquoi (contexte / motivation)…"
            className={inputCls}
          />
          <div>
            <Button
              size="sm"
              variant="primary"
              disabled={busy === "__decision__" || !title.trim() || !decision.trim()}
              onClick={onAddDecision}
            >
              ajouter la décision
            </Button>
          </div>
        </div>
      </Section>

      <Section title="Changelog">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            disabled={busy === "changelog" || release_blocking}
            title={frozenTitle}
            onClick={() =>
              runMutation("changelog", () => generateDirectionDoc("changelog"), "Changelog généré.")
            }
          >
            générer le changelog
          </Button>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {changelog.period_label} · {changelog.n_commits} commits · {changelog.n_sections}{" "}
            sections
          </span>
        </div>
        {changelog.section_counts.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {changelog.section_counts.map((s) => (
              <Badge key={s.type} tone="neutral">
                {s.type} : {s.count}
              </Badge>
            ))}
          </div>
        )}
        {changelog.markdown.trim() ? (
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-argos-border-subtle bg-argos-bg p-3 font-mono text-[11px] leading-relaxed text-argos-fg-secondary">
            {changelog.markdown}
          </pre>
        ) : (
          <Empty>Changelog vide.</Empty>
        )}
      </Section>

      <Section title="Roadmap publique">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            disabled={busy === "roadmap" || release_blocking}
            title={frozenTitle}
            onClick={() =>
              runMutation("roadmap", () => generateDirectionDoc("roadmap"), "Roadmap générée.")
            }
          >
            générer la roadmap
          </Button>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            {roadmap.entries_total} entrées · {roadmap.done} livrées · {roadmap.partial} en cours ·{" "}
            {roadmap.roadmap} à venir
          </span>
        </div>
        {roadmap.markdown.trim() ? (
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-argos-border-subtle bg-argos-bg p-3 font-mono text-[11px] leading-relaxed text-argos-fg-secondary">
            {roadmap.markdown}
          </pre>
        ) : (
          <Empty>Roadmap vide.</Empty>
        )}
      </Section>

      <Section title="Release notes">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            disabled={busy === "release_notes" || release_blocking}
            title={frozenTitle}
            onClick={() =>
              runMutation(
                "release_notes",
                () => generateDirectionDoc("release_notes"),
                "Release notes générées.",
              )
            }
          >
            générer les release notes
          </Button>
          {release_blocking && (
            <span className="font-mono text-[10px] text-argos-danger">
              gelé — {release_reason}
            </span>
          )}
        </div>
      </Section>
    </div>
  );
}

// =============================================================================
// Flotte (drill-down par pôle + bugs + feedback + plan d'oversight)
// =============================================================================
function FlotteTab({ overview }: { overview: DirectionOverview }) {
  const { fleet, bugs, feedback, plan } = overview;
  return (
    <div className="flex flex-col gap-6">
      <Section title={`Détail par pôle (${fleet.poles.length})`}>
        {fleet.poles.length === 0 ? (
          <Empty>Aucun pôle dans le snapshot.</Empty>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {fleet.poles.map((p) => (
              <div key={p.pole} className={CARD}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span className={`text-xs leading-none ${HEALTH_DOT[p.health] ?? ""}`} aria-hidden>
                      {healthIcon(p.health)}
                    </span>
                    <span className="truncate font-mono text-xs text-argos-fg">{p.name}</span>
                  </div>
                  <Badge tone={HEALTH_TONE[p.health] ?? "neutral"}>{p.health}</Badge>
                </div>
                <span className="font-mono text-[10px] text-argos-fg-tertiary">
                  {p.n_facts} faits · {p.n_important} importants · {p.n_critical} critiques ·{" "}
                  {p.n_warning} warnings
                </span>
                <span className="font-mono text-[10px] text-argos-fg-disabled">
                  dernière activité : {shortDate(p.last_activity)}
                </span>
                {p.headline && (
                  <span className="font-mono text-[10px] leading-snug text-argos-fg-secondary">
                    {p.headline}
                  </span>
                )}
                {p.scripts.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {p.scripts.map((s) => (
                      <Badge key={s} tone="neutral">
                        {s}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Triage des bugs (${bugs.issues_total}) — P0 ${bugs.p0} · P1 ${bugs.p1} · P2 ${bugs.p2}`}>
        {bugs.triaged.length === 0 ? (
          <Empty>Aucune issue à trier.</Empty>
        ) : (
          <div className="overflow-x-auto rounded-md border border-argos-border-subtle">
            <table className="w-full border-collapse font-mono text-[11px]">
              <thead>
                <tr className="bg-argos-surface-2 text-argos-fg-tertiary">
                  <th className="px-2 py-1.5 text-left font-normal">#</th>
                  <th className="px-2 py-1.5 text-left font-normal">Sévérité</th>
                  <th className="px-2 py-1.5 text-left font-normal">Titre</th>
                  <th className="px-2 py-1.5 text-left font-normal">Label suggéré</th>
                </tr>
              </thead>
              <tbody>
                {bugs.triaged.map((t) => (
                  <tr key={t.number} className="border-t border-argos-border-subtle">
                    <td className="px-2 py-1.5 text-argos-fg-tertiary">#{t.number}</td>
                    <td className="px-2 py-1.5">
                      <Badge tone={SEVERITY_TONE[t.severity] ?? "neutral"}>{t.severity}</Badge>
                    </td>
                    <td className="px-2 py-1.5 text-argos-fg" title={t.reason}>
                      {t.title}
                    </td>
                    <td className="px-2 py-1.5 text-argos-fg-secondary">{t.suggested_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={`Thèmes de feedback (${feedback.themes.length}) — ${feedback.items_total} items`}>
        {feedback.themes.length === 0 ? (
          <Empty>Aucun feedback agrégé.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {feedback.themes.map((t) => (
              <div key={t.topic} className={ROW}>
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-argos-fg">{t.topic}</span>
                    <Badge tone={t.count >= 3 ? "warning" : "neutral"}>×{t.count}</Badge>
                  </div>
                  <span className="truncate font-mono text-[10px] text-argos-fg-tertiary">
                    sources : {t.sources.join(", ") || "—"} · clients :{" "}
                    {t.customers.join(", ") || "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Plan d'oversight (${plan.length})`}>
        {plan.length === 0 ? (
          <Empty>Aucune action planifiée.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {plan.map((p, i) => (
              <div key={`${p.kind}-${p.pole}-${i}`} className={CARD}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={SEVERITY_TONE[p.severity] ?? "neutral"}>{p.severity}</Badge>
                  <span className="font-mono text-xs text-argos-fg">{p.action}</span>
                  <Badge tone="neutral">{p.kind}</Badge>
                  <Badge tone="neutral">{p.pole}</Badge>
                  {p.suppressed_by_release && <Badge tone="danger">GELÉ publication</Badge>}
                </div>
                {p.detail && (
                  <span className="font-mono text-[10px] leading-snug text-argos-fg-tertiary">
                    {p.detail}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
