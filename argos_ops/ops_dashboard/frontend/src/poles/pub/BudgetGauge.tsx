// Jauge budget : dépensé/jour vs enveloppe journalière, avec repère du seuil
// d'emballement (× multiplicateur). Photo du moment (recalculée depuis le dernier
// CSV côté backend). Réglage de l'enveloppe inline. Miroir de pub/budget.py.

import { useEffect, useState } from "react";
import type { PubBudget } from "../api.ts";
import { Badge, Button } from "../../components/ui.tsx";
import { eur, pct } from "./lib.ts";

export interface BudgetGaugeProps {
  budget: PubBudget;
  busy: boolean;
  onSetBudget: (eur: number) => void;
}

export function BudgetGauge({ budget, busy, onSetBudget }: BudgetGaugeProps) {
  const [draft, setDraft] = useState<string>(String(budget.daily_budget_eur));
  // Resynchronise le champ après un enregistrement (ou un changement hors bande)
  // — le prefill useState n'est pris en compte qu'au montage.
  useEffect(() => {
    setDraft(String(budget.daily_budget_eur));
  }, [budget.daily_budget_eur]);

  const unset = budget.daily_budget_eur <= 0;
  // Échelle de la barre : on cale le 100% sur le seuil d'emballement (= budget ×
  // multiplicateur) pour que le repère « seuil » et la zone rouge soient lisibles.
  const scaleMax = unset ? 1 : budget.runaway_threshold_eur;
  const spentPct = unset ? 0 : Math.min(100, (budget.spent_per_day_eur / scaleMax) * 100);
  const budgetMarkPct = unset ? 0 : Math.min(100, (budget.daily_budget_eur / scaleMax) * 100);

  const barColor = budget.over_threshold
    ? "bg-argos-danger"
    : budget.utilization >= 1
      ? "bg-argos-warning"
      : "bg-argos-healthy";

  return (
    <div className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-lg font-medium text-argos-fg">
            {eur(budget.spent_per_day_eur)}
          </span>
          <span className="font-mono text-[11px] text-argos-fg-tertiary">
            / {unset ? "budget non réglé" : `${eur(budget.daily_budget_eur)} par jour`}
          </span>
        </div>
        {!unset && (
          <Badge tone={budget.over_threshold ? "danger" : budget.utilization >= 1 ? "warning" : "healthy"}>
            {pct(budget.utilization)} du budget
          </Badge>
        )}
      </div>

      {/* Barre avec repère budget (trait) + zone seuil d'emballement (fin de barre) */}
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-argos-surface-2">
        <div
          className={`h-full rounded-full ${barColor} transition-all`}
          style={{ width: `${spentPct}%` }}
        />
        {!unset && (
          <div
            className="absolute top-0 h-full w-0.5 bg-argos-fg"
            style={{ left: `${budgetMarkPct}%` }}
            title={`Budget : ${eur(budget.daily_budget_eur)}/j`}
            aria-hidden
          />
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[10px] text-argos-fg-tertiary">
        <span>
          dépensé {eur(budget.spent_window_eur)} sur {budget.window_days} j
        </span>
        {!unset && (
          <span>
            seuil emballement (×{budget.runaway_multiplier}) :{" "}
            <span className="text-argos-danger">{eur(budget.runaway_threshold_eur)}/j</span>
          </span>
        )}
      </div>

      {/* Réglage de l'enveloppe */}
      <div className="flex items-center gap-2 border-t border-argos-border-subtle pt-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          budget /jour
        </span>
        <input
          type="number"
          min={0}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="w-24 rounded-md border border-argos-border-subtle bg-argos-bg px-2 py-1 font-mono text-[11px] text-argos-fg focus:border-argos-info/60 focus:outline-none"
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={busy || draft === "" || Number(draft) < 0}
          onClick={() => onSetBudget(Number(draft))}
        >
          enregistrer
        </Button>
      </div>
    </div>
  );
}
