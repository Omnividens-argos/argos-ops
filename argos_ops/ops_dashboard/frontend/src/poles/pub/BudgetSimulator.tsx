// Simulateur de budget : on alloue une enveloppe journalière par plateforme, le
// backend projette dépense/semaine + leads (au CPA observé du dernier CSV) et
// signale si l'allocation dépasse le budget ou armerait le breaker. Miroir de
// pub/budget.simulate_budget.

import { useState } from "react";
import type { AdPlatform, PubBudget, Simulation } from "../api.ts";
import { Badge, Button } from "../../components/ui.tsx";
import { eur } from "./lib.ts";

export interface BudgetSimulatorProps {
  platforms: AdPlatform[];
  budget: PubBudget;
  onSimulate: (payload: {
    per_platform_daily: Record<string, number>;
    daily_budget_eur?: number;
  }) => Promise<Simulation>;
}

export function BudgetSimulator({ platforms, budget, onSimulate }: BudgetSimulatorProps) {
  // Pré-remplit avec la dépense/jour observée par plateforme (sur la fenêtre).
  const initial: Record<string, number> = {};
  for (const p of platforms) {
    const windowSpend = budget.by_platform[p.id] ?? 0;
    initial[p.id] = Math.round(windowSpend / Math.max(1, budget.window_days));
  }
  const [alloc, setAlloc] = useState<Record<string, number>>(initial);
  const [result, setResult] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalDaily = Object.values(alloc).reduce((s, v) => s + (v || 0), 0);
  // Borne haute du curseur : assez large pour le budget ET pour toute allocation
  // pré-remplie (sinon le thumb se cale au max et n'égale plus la valeur affichée).
  const sliderMax = Math.max(
    500,
    Math.round(budget.daily_budget_eur * 1.5),
    ...Object.values(alloc).map((v) => v || 0),
  );

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await onSimulate({ per_platform_daily: alloc }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de la simulation");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-4 py-3">
        {platforms.map((p) => (
          <div key={p.id} className="flex items-center gap-3">
            <span className="w-44 shrink-0 font-mono text-[11px] text-argos-fg">{p.label}</span>
            <input
              type="range"
              min={0}
              max={sliderMax}
              step={10}
              value={alloc[p.id] ?? 0}
              onChange={(e) => setAlloc((a) => ({ ...a, [p.id]: Number(e.target.value) }))}
              className="h-1 flex-1 cursor-pointer appearance-none rounded-lg bg-argos-surface-2 accent-argos-info"
            />
            <span className="w-20 shrink-0 text-right font-mono text-[11px] text-argos-fg-secondary">
              {eur(alloc[p.id] ?? 0)}/j
            </span>
          </div>
        ))}
        <div className="flex items-center justify-between border-t border-argos-border-subtle pt-2">
          <span className="font-mono text-[11px] text-argos-fg-tertiary">
            total {eur(totalDaily)}/j · budget {eur(budget.daily_budget_eur)}/j
          </span>
          <Button size="sm" variant="primary" disabled={busy} onClick={run}>
            simuler
          </Button>
        </div>
      </div>

      {error && <span className="font-mono text-[11px] text-argos-danger">{error}</span>}

      {result && (
        <div className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {result.would_trip ? (
              <Badge tone="danger">armerait le breaker</Badge>
            ) : result.exceeds_budget ? (
              <Badge tone="warning">dépasse le budget</Badge>
            ) : (
              <Badge tone="healthy">dans l'enveloppe</Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-2">
            <Metric label="dépense / sem" value={eur(result.weekly_spend_eur)} />
            <Metric label="leads / sem" value={result.weekly_leads.toFixed(1)} />
            <Metric
              label="CPA combiné"
              value={result.blended_cpa_eur > 0 ? eur(result.blended_cpa_eur) : "—"}
            />
            <Metric label="total / jour" value={`${eur(result.total_daily_eur)}/j`} />
          </div>
          <table className="w-full border-collapse font-mono text-[11px]">
            <thead>
              <tr className="border-b border-argos-border-subtle text-argos-fg-tertiary">
                <th className="px-2 py-1.5 text-left font-normal">Plateforme</th>
                <th className="px-2 py-1.5 text-right font-normal">€/j</th>
                <th className="px-2 py-1.5 text-right font-normal">CPA obs.</th>
                <th className="px-2 py-1.5 text-right font-normal">€/sem</th>
                <th className="px-2 py-1.5 text-right font-normal">leads/sem</th>
              </tr>
            </thead>
            <tbody>
              {result.allocations.map((a) => (
                <tr key={a.platform} className="border-b border-argos-border-subtle/50 last:border-0">
                  <td className="px-2 py-1.5 text-left text-argos-fg-secondary">{a.platform}</td>
                  <td className="px-2 py-1.5 text-right text-argos-fg-secondary">{eur(a.daily_eur)}</td>
                  <td className="px-2 py-1.5 text-right text-argos-fg-secondary">
                    {a.cpa_eur > 0 ? eur(a.cpa_eur) : "—"}
                  </td>
                  <td className="px-2 py-1.5 text-right text-argos-fg-secondary">
                    {eur(a.weekly_spend_eur)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-argos-fg-secondary">
                    {a.weekly_leads.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-base font-medium text-argos-fg">{value}</span>
      <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
        {label}
      </span>
    </div>
  );
}
