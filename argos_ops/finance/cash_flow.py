"""Forecast cash flow 30 / 60 / 90 jours (InvoicePredictor — Sprint 10).

Hypothèses :
- Une subscription Stripe ``active`` ou ``trialing`` génère un revenu
  attendu = MRR mensuel à la prochaine date de renouvellement.
- Une subscription ``past_due`` est exclue de la prédiction (cf. dunning
  qui gère le recouvrement).
- Argos est facturé en EUR uniquement (cf. ``stripe_client.py`` warning).

Forecast = somme des MRR attendus dans chaque fenêtre [today, today+30j],
[today+30j, today+60j], [today+60j, today+90j] basé sur
``current_period_end``.

C'est volontairement simple — pas de modèle ML, pas de churn rate
projeté. Le founder veut juste une jauge "combien je rentre si tout
reste stable", pour comparer avec son burn rate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from argos_ops.integrations.stripe_client import StripeSubscription


@dataclass(frozen=True)
class CashFlowForecast:
    """Forecast cash flow par fenêtre temporelle (jours)."""

    as_of: datetime
    expected_30d_eur: Decimal
    expected_60d_eur: Decimal
    expected_90d_eur: Decimal
    n_subs_considered: int
    n_subs_excluded: int  # past_due / canceled / unpaid

    def summary(self) -> str:
        return (
            f"30d={self.expected_30d_eur} "
            f"60d={self.expected_60d_eur} "
            f"90d={self.expected_90d_eur} "
            f"subs={self.n_subs_considered} excluded={self.n_subs_excluded}"
        )


HEALTHY_STATUSES: frozenset[str] = frozenset({"active", "trialing"})


def forecast_cash_flow(
    subs: Sequence[StripeSubscription], *, as_of: datetime | None = None
) -> CashFlowForecast:
    """Calcule les rentrées prévisionnelles 30 / 60 / 90 jours.

    Une subscription contribue à la fenêtre où tombe sa
    ``current_period_end``. Si ``current_period_end`` est None ou déjà
    passé, on suppose un renouvellement immédiat (donc 30 j).
    """
    as_of = as_of or datetime.now(UTC)
    cut_30 = as_of + timedelta(days=30)
    cut_60 = as_of + timedelta(days=60)
    cut_90 = as_of + timedelta(days=90)

    bucket_30 = Decimal("0.00")
    bucket_60 = Decimal("0.00")
    bucket_90 = Decimal("0.00")
    considered = 0
    excluded = 0

    for sub in subs:
        if sub.status not in HEALTHY_STATUSES:
            excluded += 1
            continue
        considered += 1

        renewal = sub.current_period_end or as_of
        if renewal.tzinfo is None:
            renewal = renewal.replace(tzinfo=UTC)

        if renewal <= cut_30:
            bucket_30 += sub.mrr_eur
        elif renewal <= cut_60:
            bucket_60 += sub.mrr_eur
        elif renewal <= cut_90:
            bucket_90 += sub.mrr_eur
        # > 90j : hors fenêtre — non comptabilisé

    return CashFlowForecast(
        as_of=as_of,
        expected_30d_eur=bucket_30,
        expected_60d_eur=bucket_60,
        expected_90d_eur=bucket_90,
        n_subs_considered=considered,
        n_subs_excluded=excluded,
    )


__all__ = [
    "HEALTHY_STATUSES",
    "CashFlowForecast",
    "forecast_cash_flow",
]
