// Page du pôle Mémoire (archi v2, S7). Concierge de la mémoire de flotte :
// navigateur par pôle/script + recherche + toggle `important`, PREVIEW de
// curation (safe-to-delete vs protégés) avant suppression validée, audit du
// câblage reads_cross_pole, activation par pôle, et historique des passages.
// Branche le shell poles.html sur GET /api/poles/memoire/*.

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { type MemoireOverview, fetchMemoireOverview } from "../api.ts";
import { Badge, Button, Flash } from "../../components/ui.tsx";
import { MemoryBrowser } from "./MemoryBrowser.tsx";
import { CurationPreview } from "./CurationPreview.tsx";
import { WiringBoard } from "./WiringBoard.tsx";
import { PolicyConfig } from "./PolicyConfig.tsx";
import { HistoryList } from "./HistoryList.tsx";

type Tab = "browse" | "curation" | "wiring" | "policy" | "history";

const TABS: { id: Tab; label: string }[] = [
  { id: "browse", label: "Navigateur" },
  { id: "curation", label: "Curation" },
  { id: "wiring", label: "Câblage" },
  { id: "policy", label: "Activation" },
  { id: "history", label: "Historique" },
];

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

export function MemoirePage() {
  const [overview, setOverview] = useState<MemoireOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("browse");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchMemoireOverview(controller.signal)
      .then(setOverview)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Erreur de chargement");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);

  const facetPoles = overview?.poles.map((p) => p.pole) ?? [];
  const curatablePoles = overview?.poles.map((p) => ({ pole: p.pole, active: p.active })) ?? [];

  function renderTab(): ReactNode {
    if (!overview) return null;
    switch (tab) {
      case "browse":
        return <MemoryBrowser poles={facetPoles} />;
      case "curation":
        return <CurationPreview poles={curatablePoles} onChanged={refresh} />;
      case "wiring":
        return <WiringBoard wiring={overview.wiring} />;
      case "policy":
        return (
          <PolicyConfig policy={overview.policy} poles={overview.poles} onChanged={refresh} />
        );
      case "history":
        return <HistoryList history={overview.history} />;
      default:
        return null;
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle 7/8</span>
            <Badge tone="info">MemoireAgent</Badge>
            <Badge tone="neutral">déclenché par script</Badge>
          </div>
          <Button size="sm" variant="ghost" onClick={refresh}>
            <RefreshCw className="mr-1 inline h-3 w-3" aria-hidden /> rafraîchir
          </Button>
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">Mémoire</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">
          Concierge de la mémoire de flotte : protège l'important, propose le périmé/stale à
          supprimer (jamais sans validation), et audite le câblage inter-pôles. Seul pôle
          autorisé à supprimer un fait.
        </p>
        {overview && (
          <div className="flex flex-wrap items-center gap-6">
            <Stat label="faits" value={overview.counts.facts_total} tone="text-argos-fg" />
            <Stat
              label="importants"
              value={overview.counts.important_total}
              tone="text-argos-warning"
            />
            <Stat
              label="safe-to-delete"
              value={overview.counts.candidates_total}
              tone="text-argos-danger"
            />
            <Stat
              label="pôles actifs"
              value={overview.counts.poles_active}
              tone="text-argos-healthy"
            />
            <Stat
              label="câblage warn"
              value={overview.counts.wiring_warnings}
              tone={
                overview.counts.wiring_warnings > 0 ? "text-argos-warning" : "text-argos-fg"
              }
            />
          </div>
        )}
      </header>

      <nav className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 font-mono text-xs transition-colors ${
              tab === t.id
                ? "bg-argos-info/15 text-argos-info"
                : "text-argos-fg-secondary hover:bg-argos-surface-2 hover:text-argos-fg"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {loading && (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-8 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Chargement de la mémoire de flotte…
        </div>
      )}

      {error && !loading && (
        <Flash
          variant="error"
          message={`Backend injoignable (${error}). Lancer le cockpit : uv run python scripts/run_ops_dashboard.py`}
        />
      )}

      {overview && !loading && <div>{renderTab()}</div>}
    </div>
  );
}
