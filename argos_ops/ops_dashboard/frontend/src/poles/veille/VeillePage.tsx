// Page du pôle Veille (archi v2, S1). Branche le shell poles.html sur le backend
// (GET /api/poles/veille/feed) : flux d'insights synthétisés, timeline concurrents,
// carte breaches/CVE, filtres thème/sévérité/date, recherche mémoire, et bouton
// « pousser vers Marketing/Pub/Vente » (POST .../handoff). Réutilise le thème et
// les composants partagés du cockpit (font-mono, tokens argos-*, MemoryTable…).

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { type PoleFeed, fetchPoleFeed, pushHandoff } from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { MemoryTable, type MemoryRow } from "../components/index.ts";
import { CompetitorTimeline } from "./CompetitorTimeline.tsx";
import { FilterBar, type FilterState } from "./FilterBar.tsx";
import { InsightFeed } from "./InsightFeed.tsx";
import { poleLabel } from "./PushControl.tsx";
import { ThreatBoard } from "./ThreatBoard.tsx";
import {
  THREAT_KINDS,
  kindTheme,
  matchesQuery,
  recordSeverity,
  withinRange,
} from "./lib.ts";

const POLE = "veille";

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
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

const EMPTY_FILTER: FilterState = {
  query: "",
  themes: new Set<string>(),
  severity: "all",
  range: "all",
};

export function VeillePage() {
  const [feed, setFeed] = useState<PoleFeed | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [filter, setFilter] = useState<FilterState>(EMPTY_FILTER);
  const [pushed, setPushed] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; message: string } | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchPoleFeed(POLE, controller.signal)
      .then((data) => setFeed(data))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const handlePush = useCallback(async (recordId: string, pole: string) => {
    const key = `${recordId}:${pole}`;
    setBusy(key);
    setFlash(null);
    try {
      await pushHandoff(POLE, { record_id: recordId, target_pole: pole });
      setPushed((prev) => new Set(prev).add(key));
      setFlash({ variant: "success", message: `Signal poussé vers ${poleLabel(pole)}.` });
    } catch (err: unknown) {
      setFlash({
        variant: "error",
        message: err instanceof Error ? err.message : "Échec du handoff.",
      });
    } finally {
      setBusy(null);
    }
  }, []);

  const filteredRecords = useMemo(() => {
    if (!feed) return [];
    return feed.records.filter(
      (r) =>
        matchesQuery(r, filter.query) &&
        (filter.themes.size === 0 || filter.themes.has(kindTheme(r.kind))) &&
        (filter.severity === "all" || recordSeverity(r) === filter.severity) &&
        withinRange(r.created_at, filter.range),
    );
  }, [feed, filter]);

  const filteredInsights = useMemo(() => {
    if (!feed) return [];
    return feed.insights.filter(
      (i) =>
        (filter.themes.size === 0 || filter.themes.has(i.theme)) &&
        (filter.severity === "all" || i.severity === filter.severity),
    );
  }, [feed, filter]);

  const threats = filteredRecords.filter((r) => THREAT_KINDS.has(r.kind));
  const competitors = filteredRecords.filter((r) => r.kind === "competitor");
  const rows: MemoryRow[] = filteredRecords.map((r) => ({
    id: r.id,
    pole: r.pole,
    script: r.script,
    kind: r.kind,
    important: r.important,
    createdAt: r.created_at,
    body: r.body,
  }));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 1/8</span>
            <Badge tone="info">VeilleAgent</Badge>
            <Badge tone="neutral">en amont</Badge>
          </div>
          <Button size="sm" variant="ghost" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Veille</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">
          Signaux marché, tech, concurrents et menaces, synthétisés en insights routés vers
          Marketing, Pub et Vente.
        </p>
        {feed && (
          <div className="flex items-center gap-6">
            <Stat label="signaux" value={feed.counts.total} tone="text-argos-fg" />
            <Stat label="importants" value={feed.counts.important} tone="text-argos-warning" />
            <Stat label="critiques" value={feed.counts.critical} tone="text-argos-danger" />
          </div>
        )}
      </header>

      {flash && (
        <Flash variant={flash.variant} message={flash.message} onDismiss={() => setFlash(null)} />
      )}

      {loading && (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-8 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Chargement de la mémoire de veille…
        </div>
      )}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {feed && !loading && (
        <>
          <FilterBar
            availableThemes={feed.themes}
            state={filter}
            onChange={setFilter}
          />

          <Section
            title="Flux d'insights"
            hint={`${filteredInsights.length} insight(s)`}
          >
            <InsightFeed
              insights={filteredInsights}
              pushed={pushed}
              busy={busy}
              onPush={handlePush}
            />
          </Section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Section title="Menaces (breaches · CVE · dark web)" hint={`${threats.length}`}>
              <ThreatBoard facts={threats} />
            </Section>
            <Section title="Timeline concurrents" hint={`${competitors.length}`}>
              <CompetitorTimeline facts={competitors} />
            </Section>
          </div>

          <Section title="Mémoire de veille" hint={`${rows.length}/${feed.counts.total} fait(s)`}>
            <MemoryTable rows={rows} />
          </Section>
        </>
      )}
    </div>
  );
}
