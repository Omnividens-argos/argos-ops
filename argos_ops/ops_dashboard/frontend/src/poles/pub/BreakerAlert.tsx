// Carte d'alerte du circuit breaker ad_spend_runaway. Armé (latch) → rouge +
// bouton reset (humain) ; au-dessus du seuil mais pas encore armé → avertissement
// (relancer ads_optimizer) ; sinon vert. Réutilise AlertCard partagé.

import type { PubBudget } from "../api.ts";
import { AlertCard } from "../components/index.ts";
import { Button } from "../../components/ui.tsx";
import { eur, shortDate } from "./lib.ts";

export interface BreakerAlertProps {
  budget: PubBudget;
  busy: boolean;
  onReset: () => void;
}

export function BreakerAlert({ budget, busy, onReset }: BreakerAlertProps) {
  if (budget.breaker_tripped) {
    return (
      <div className="flex flex-col gap-2">
        <AlertCard
          tone="danger"
          title="Breaker ad_spend_runaway ARMÉ"
          detail={budget.breaker_reason ?? "Dépense au-dessus du seuil d'emballement."}
          time={budget.breaker_tripped_at ? shortDate(budget.breaker_tripped_at) : undefined}
        />
        <div className="flex items-center gap-2">
          <Button size="sm" variant="danger" disabled={busy} onClick={onReset}>
            reset le breaker
          </Button>
          <span className="font-mono text-[10px] text-argos-fg-tertiary">
            mise en ligne et scale gelés tant que le breaker est armé
          </span>
        </div>
      </div>
    );
  }

  if (budget.over_threshold) {
    return (
      <AlertCard
        tone="warning"
        title="Dépense au-dessus du seuil d'emballement"
        detail={`${eur(budget.spent_per_day_eur)}/j > ${eur(budget.runaway_threshold_eur)}/j — relancer ads_optimizer armera le breaker.`}
      />
    );
  }

  return (
    <AlertCard
      tone="healthy"
      title="Breaker ad_spend_runaway OK"
      detail="La dépense reste sous le seuil d'emballement — rien ne requiert d'attention."
    />
  );
}
