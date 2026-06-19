// Page du pôle Veille (archi v2, S1). Branche le shell poles.html sur le backend
// (GET /api/poles/veille/feed) : flux d'insights synthétisés, timeline concurrents,
// carte breaches/CVE, filtres thème/sévérité/date, recherche mémoire, et bouton
// « pousser vers Marketing/Pub/Vente » (POST .../handoff). Réutilise le thème et
// les composants partagés du cockpit (font-mono, tokens argos-*, MemoryTable…).

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Save, X } from "lucide-react";
import { type PoleFeed, type Severity, fetchPoleFeed, pushHandoff } from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { MemoryTable, type MemoryRow } from "../components/index.ts";
import { CompetitorTimeline } from "./CompetitorTimeline.tsx";
import { FilterBar, type FilterState } from "./FilterBar.tsx";
import { InsightFeed } from "./InsightFeed.tsx";
import { poleLabel } from "./PushControl.tsx";
import { ThreatBoard } from "./ThreatBoard.tsx";
import {
  THREAT_KINDS,
  type DateRange,
  kindTheme,
  matchesQuery,
  recordSeverity,
  withinRange,
} from "./lib.ts";

const POLE = "veille";

// Persistance des filtres de veille (local-first, D-017) : le FilterState courant
// survit au reload, et on garde des vues nommées rejouables. `themes` étant un Set,
// on sérialise via une forme plate (themes -> string[]) avant JSON.
const FILTER_STORAGE_KEY = "argos.veille.filter";
const SAVED_VIEWS_STORAGE_KEY = "argos.veille.savedViews";

interface StoredFilter {
  query: string;
  themes: string[];
  severity: Severity | "all";
  range: DateRange;
}

interface SavedView {
  name: string;
  filter: StoredFilter;
}

const SEVERITY_VALUES: ReadonlySet<Severity | "all"> = new Set<Severity | "all">([
  "all",
  "critical",
  "warning",
  "info",
]);
const RANGE_VALUES: ReadonlySet<DateRange> = new Set<DateRange>(["all", "24h", "7d", "30d"]);

function isSeverity(value: unknown): value is Severity | "all" {
  return typeof value === "string" && SEVERITY_VALUES.has(value as Severity | "all");
}

function isRange(value: unknown): value is DateRange {
  return typeof value === "string" && RANGE_VALUES.has(value as DateRange);
}

function serializeFilter(filter: FilterState): StoredFilter {
  return {
    query: filter.query,
    themes: [...filter.themes],
    severity: filter.severity,
    range: filter.range,
  };
}

function deserializeFilter(stored: StoredFilter): FilterState {
  return {
    query: stored.query,
    themes: new Set(stored.themes),
    severity: stored.severity,
    range: stored.range,
  };
}

// Parse défensif d'un StoredFilter venant de localStorage (peut être corrompu).
function parseStoredFilter(raw: unknown): StoredFilter | null {
  if (typeof raw !== "object" || raw === null) return null;
  const candidate = raw as Record<string, unknown>;
  const { query, themes, severity, range } = candidate;
  if (typeof query !== "string") return null;
  if (!Array.isArray(themes) || themes.some((t) => typeof t !== "string")) return null;
  if (!isSeverity(severity) || !isRange(range)) return null;
  return { query, themes: themes as string[], severity, range };
}

function loadStoredFilter(): FilterState | null {
  try {
    const raw = window.localStorage.getItem(FILTER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = parseStoredFilter(JSON.parse(raw));
    return parsed ? deserializeFilter(parsed) : null;
  } catch {
    return null;
  }
}

function loadSavedViews(): SavedView[] {
  try {
    const raw = window.localStorage.getItem(SAVED_VIEWS_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const views: SavedView[] = [];
    for (const entry of parsed) {
      if (typeof entry !== "object" || entry === null) continue;
      const { name, filter } = entry as Record<string, unknown>;
      const storedFilter = parseStoredFilter(filter);
      if (typeof name === "string" && name !== "" && storedFilter) {
        views.push({ name, filter: storedFilter });
      }
    }
    return views;
  } catch {
    return [];
  }
}

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

  const [filter, setFilter] = useState<FilterState>(() => loadStoredFilter() ?? EMPTY_FILTER);
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => loadSavedViews());
  const [pushed, setPushed] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkTarget, setBulkTarget] = useState<string>("");
  const [bulkBusy, setBulkBusy] = useState(false);
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

  // Persiste le filtre courant à chaque changement (rehydraté au mount via useState).
  useEffect(() => {
    try {
      window.localStorage.setItem(
        FILTER_STORAGE_KEY,
        JSON.stringify(serializeFilter(filter)),
      );
    } catch {
      // localStorage indisponible (mode privé / quota) : on dégrade silencieusement.
    }
  }, [filter]);

  // Persiste la liste des vues nommées à chaque mutation.
  useEffect(() => {
    try {
      window.localStorage.setItem(SAVED_VIEWS_STORAGE_KEY, JSON.stringify(savedViews));
    } catch {
      // idem : pas de blocage si le stockage n'est pas accessible.
    }
  }, [savedViews]);

  const saveCurrentView = useCallback(() => {
    const name = window.prompt("Nom de la vue à enregistrer ?")?.trim();
    if (!name) return;
    const stored = serializeFilter(filter);
    setSavedViews((prev) => {
      const without = prev.filter((v) => v.name !== name);
      return [...without, { name, filter: stored }];
    });
  }, [filter]);

  const applyView = useCallback((view: SavedView) => {
    setFilter(deserializeFilter(view.filter));
  }, []);

  const deleteView = useCallback((name: string) => {
    setSavedViews((prev) => prev.filter((v) => v.name !== name));
  }, []);

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

  const toggleSelected = useCallback((recordId: string) => {
    if (recordId === "") return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(recordId)) next.delete(recordId);
      else next.add(recordId);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelected(new Set());
  }, []);

  // Push groupé : pousse chaque record sélectionné vers le pôle aval choisi en une
  // action, en réutilisant le même endpoint que le push unitaire (await all).
  const handleBulkPush = useCallback(async () => {
    if (bulkTarget === "" || selected.size === 0) return;
    const ids = [...selected];
    setBulkBusy(true);
    setFlash(null);
    try {
      await Promise.all(
        ids.map((recordId) =>
          pushHandoff(POLE, { record_id: recordId, target_pole: bulkTarget }),
        ),
      );
      setPushed((prev) => {
        const next = new Set(prev);
        for (const recordId of ids) next.add(`${recordId}:${bulkTarget}`);
        return next;
      });
      setSelected(new Set());
      setFlash({
        variant: "success",
        message: `${ids.length} élément(s) poussé(s) vers ${poleLabel(bulkTarget)}.`,
      });
    } catch (err: unknown) {
      setFlash({
        variant: "error",
        message: err instanceof Error ? err.message : "Échec du push groupé.",
      });
    } finally {
      setBulkBusy(false);
    }
  }, [bulkTarget, selected]);

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

  // Cibles possibles pour le push groupé : union des pôles aval suggérés par les
  // insights affichés, avec un repli sur les 3 pôles de routage par défaut.
  const bulkPoles = useMemo(() => {
    const union = new Set<string>();
    for (const insight of filteredInsights) {
      for (const pole of insight.suggested_poles) union.add(pole);
    }
    return union.size > 0 ? [...union] : ["marketing", "pub", "vente"];
  }, [filteredInsights]);

  // Garde une cible valide : sélectionne la première dispo, ré-aligne si la cible
  // courante n'est plus proposée (changement de filtre).
  useEffect(() => {
    setBulkTarget((current) =>
      current !== "" && bulkPoles.includes(current) ? current : (bulkPoles[0] ?? ""),
    );
  }, [bulkPoles]);

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
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
              vues
            </span>
            {savedViews.length === 0 && (
              <span className="font-mono text-[10px] text-argos-fg-disabled">
                aucune vue enregistrée
              </span>
            )}
            {savedViews.map((view) => (
              <span
                key={view.name}
                className="inline-flex items-center gap-1 rounded-md border border-argos-border-subtle bg-argos-surface-2 pl-2 pr-1 py-1 font-mono text-[10px] text-argos-fg-tertiary"
              >
                <button
                  type="button"
                  onClick={() => applyView(view)}
                  className="uppercase tracking-widest transition-colors hover:text-argos-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
                >
                  {view.name}
                </button>
                <button
                  type="button"
                  onClick={() => deleteView(view.name)}
                  aria-label={`Supprimer la vue ${view.name}`}
                  className="rounded text-argos-fg-disabled transition-colors hover:text-argos-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ))}
            <Button size="sm" variant="ghost" onClick={saveCurrentView}>
              <Save className="mr-1 inline h-3 w-3" aria-hidden /> enregistrer la vue
            </Button>
          </div>

          <FilterBar
            availableThemes={feed.themes}
            state={filter}
            onChange={setFilter}
          />

          <Section
            title="Flux d'insights"
            hint={`${filteredInsights.length} insight(s)`}
          >
            {selected.size > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-md border border-argos-info/40 bg-argos-info/15 px-3 py-2">
                <span className="font-mono text-[11px] text-argos-info">
                  {selected.size} sélectionné(s)
                </span>
                <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
                  pousser vers
                </span>
                <label className="sr-only" htmlFor="veille-bulk-target">
                  Pôle aval cible du push groupé
                </label>
                <select
                  id="veille-bulk-target"
                  value={bulkTarget}
                  onChange={(e) => setBulkTarget(e.target.value)}
                  disabled={bulkBusy}
                  className="rounded-md border border-argos-border-subtle bg-argos-bg px-2 py-1 font-mono text-[11px] text-argos-fg focus:outline-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg disabled:opacity-40"
                >
                  {bulkPoles.map((p) => (
                    <option key={p} value={p}>
                      {poleLabel(p)}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="primary"
                  disabled={bulkBusy || bulkTarget === "" || selected.size === 0}
                  onClick={handleBulkPush}
                >
                  {bulkBusy ? "…" : `pousser ${selected.size} élément(s)`}
                </Button>
                <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={clearSelection}>
                  effacer
                </Button>
              </div>
            )}
            <InsightFeed
              insights={filteredInsights}
              pushed={pushed}
              busy={busy}
              onPush={handlePush}
              selected={selected}
              onToggleSelect={toggleSelected}
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
