"""Rapprochement Stripe payouts ↔ relevés bancaires Qonto (ReconcileBot — Sprint 10).

Stripe verse les fonds sur Qonto par payouts (1-2x par semaine selon
le plan). Chaque payout Stripe doit retomber comme un crédit Qonto
identifié par son libellé (« STRIPE »).

Match heuristique :
1. Cherche dans le CSV Qonto les crédits dont le label contient
   "STRIPE" (insensible casse).
2. Pour chaque payout Stripe, trouve un match Qonto avec :
   - amount identique (à 1 centime près, arrondi compta)
   - date Qonto entre J et J+5 (le virement met 1-3 jours ouvrés)

Output : 3 listes — matchés, payouts Stripe orphelins, crédits
Qonto Stripe orphelins. Le founder regarde les listes orphelines
en priorité (potentiel fraude ou bug d'export).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from argos_ops.finance.expense_csv import Expense


@dataclass(frozen=True)
class StripePayout:
    """Payout Stripe — virement en attente ou réalisé."""

    id: str
    arrival_date: date
    amount_eur: Decimal  # toujours positif (sortie côté Stripe = entrée côté Qonto)


@dataclass(frozen=True)
class ReconcileMatch:
    """Un match retenu entre un payout Stripe et un crédit Qonto."""

    payout: StripePayout
    qonto_credit: Expense
    delta_days: int  # nombre de jours entre arrival_date et settled_on


@dataclass(frozen=True)
class ReconcileReport:
    """Bilan global d'un run ReconcileBot."""

    matches: list[ReconcileMatch]
    orphan_payouts: list[StripePayout]  # côté Stripe : pas trouvé en Qonto
    orphan_credits: list[Expense]  # côté Qonto : crédit Stripe non matché

    def summary(self) -> str:
        return (
            f"matched={len(self.matches)} "
            f"orphan_payouts={len(self.orphan_payouts)} "
            f"orphan_credits={len(self.orphan_credits)}"
        )


def _is_stripe_credit(expense: Expense) -> bool:
    """True si la ligne Qonto ressemble à un crédit Stripe."""
    if expense.amount_eur <= 0:
        return False
    haystack = " ".join(filter(None, (expense.vendor, expense.label))).lower()
    return "stripe" in haystack


def reconcile(
    payouts: list[StripePayout],
    qonto_expenses: list[Expense],
    *,
    max_delay_days: int = 5,
    amount_tolerance_eur: Decimal = Decimal("0.01"),
) -> ReconcileReport:
    """Match les payouts Stripe contre les crédits Qonto.

    Algo glouton — chaque crédit Qonto est consommé au plus une fois.
    On itère sur les payouts triés par date (ancien d'abord) pour
    privilégier les matchs proches.
    """
    qonto_credits = [e for e in qonto_expenses if _is_stripe_credit(e)]
    matches: list[ReconcileMatch] = []
    consumed_credit_ids: set[int] = set()

    sorted_payouts = sorted(payouts, key=lambda p: p.arrival_date)

    for payout in sorted_payouts:
        match_credit: Expense | None = None
        for idx, credit in enumerate(qonto_credits):
            if idx in consumed_credit_ids:
                continue
            delta = (credit.settled_on - payout.arrival_date).days
            if delta < 0 or delta > max_delay_days:
                continue
            if abs(credit.amount_eur - payout.amount_eur) > amount_tolerance_eur:
                continue
            match_credit = credit
            consumed_credit_ids.add(idx)
            break

        if match_credit is not None:
            matches.append(
                ReconcileMatch(
                    payout=payout,
                    qonto_credit=match_credit,
                    delta_days=(match_credit.settled_on - payout.arrival_date).days,
                )
            )

    matched_payout_ids = {m.payout.id for m in matches}
    orphan_payouts = [p for p in payouts if p.id not in matched_payout_ids]
    orphan_credits = [
        credit
        for idx, credit in enumerate(qonto_credits)
        if idx not in consumed_credit_ids
    ]

    return ReconcileReport(
        matches=matches,
        orphan_payouts=orphan_payouts,
        orphan_credits=orphan_credits,
    )


def parse_payouts_yaml_entries(rows: list[dict[str, object]]) -> list[StripePayout]:
    """Construit des :class:`StripePayout` depuis des dicts YAML/JSON.

    Permet de scénariser un test ou de feeder le bot avec un export
    Stripe Dashboard manuel sans toucher à l'API.
    """
    out: list[StripePayout] = []
    for row in rows:
        payout_id = row.get("id")
        arrival = row.get("arrival_date")
        amount = row.get("amount_eur")
        if not isinstance(payout_id, str) or arrival is None or amount is None:
            continue
        if isinstance(arrival, datetime):
            arrival_date = arrival.date()
        elif isinstance(arrival, date):
            arrival_date = arrival
        elif isinstance(arrival, str):
            try:
                arrival_date = date.fromisoformat(arrival)
            except ValueError:
                continue
        else:
            continue
        try:
            amount_dec = Decimal(str(amount))
        except Exception:
            continue
        out.append(
            StripePayout(id=payout_id, arrival_date=arrival_date, amount_eur=amount_dec)
        )
    return out


__all__ = [
    "ReconcileMatch",
    "ReconcileReport",
    "StripePayout",
    "parse_payouts_yaml_entries",
    "reconcile",
]
