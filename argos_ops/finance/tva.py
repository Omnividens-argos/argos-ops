"""Helpers TVA française pour TaxBot (Sprint 10).

Argos est facturé en EUR uniquement, taux TVA normal **20 %** sur les
prestations de services SaaS BtoB en France métropolitaine. Pour les
clients UE BtoB hors France, autoliquidation (mention obligatoire,
TVA à 0). Hors-UE : exonération.

CA3 mensuelle = formulaire de déclaration TVA, déposée sur impots.gouv.fr
le 19 du mois M+1 pour le mois M. Champs principaux :

- CA HT (base imposable)
- TVA collectée
- TVA déductible (sur achats)
- TVA nette à payer

Helpers minimaux ici — l'objectif est juste de pré-remplir un draft
exploitable par le founder. Pas de connexion DGFiP directe (hors scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

VAT_RATE_NORMAL = Decimal("0.20")
"""Taux normal TVA France (20 %)."""

IS_RATE_REDUCED = Decimal("0.15")
"""Taux IS réduit (15 %) sur les premiers 42 500 € de bénéfices."""

IS_RATE_NORMAL = Decimal("0.25")
"""Taux IS normal (25 %) au-delà du seuil PME."""

IS_REDUCED_THRESHOLD = Decimal("42500.00")
"""Seuil du taux IS réduit pour les PME (2024)."""


def _round_eur(value: Decimal) -> Decimal:
    """Arrondi monétaire à 2 décimales — `ROUND_HALF_UP` (norme compta FR)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CA3Report:
    """Brouillon de déclaration TVA CA3 mensuelle."""

    period_month: str  # "2026-05"
    ca_ht_eur: Decimal
    tva_collected_eur: Decimal
    tva_deductible_eur: Decimal
    tva_net_due_eur: Decimal

    def summary(self) -> str:
        return (
            f"ca_ht={self.ca_ht_eur} "
            f"tva_collected={self.tva_collected_eur} "
            f"tva_deductible={self.tva_deductible_eur} "
            f"tva_net={self.tva_net_due_eur}"
        )


def compute_ca3(
    *,
    period_month: str,
    ca_ht_eur: Decimal,
    tva_deductible_eur: Decimal = Decimal("0.00"),
    rate: Decimal = VAT_RATE_NORMAL,
) -> CA3Report:
    """Calcule la TVA collectée et nette due pour un CA HT donné.

    ``ca_ht_eur`` doit être en EUR Hors Taxes (le montant des factures
    Stripe émises en HT sur la période). Si ``tva_deductible_eur`` n'est
    pas fourni, le draft estimera juste la TVA collectée à payer (le
    founder ajustera avec ses propres achats).
    """
    tva_collected = _round_eur(ca_ht_eur * rate)
    tva_net = _round_eur(tva_collected - tva_deductible_eur)
    return CA3Report(
        period_month=period_month,
        ca_ht_eur=_round_eur(ca_ht_eur),
        tva_collected_eur=tva_collected,
        tva_deductible_eur=_round_eur(tva_deductible_eur),
        tva_net_due_eur=tva_net,
    )


@dataclass(frozen=True)
class ISForecast:
    """Estimation IS prévisionnel sur le résultat avant impôt fourni."""

    profit_before_tax_eur: Decimal
    is_reduced_part_eur: Decimal  # IS dû à 15 % (jusqu'au seuil PME)
    is_normal_part_eur: Decimal  # IS dû à 25 % (au-delà du seuil)
    is_total_eur: Decimal


def estimate_is(profit_before_tax_eur: Decimal) -> ISForecast:
    """Calcule l'IS dû selon le barème PME 2024 (15 % puis 25 %).

    Le seuil PME (42 500 €) s'applique aux sociétés avec CA < 10 M€ et
    capital détenu à ≥ 75 % par des personnes physiques. Argos est dans
    cette catégorie au moment où Sprint 10 est livré.
    """
    if profit_before_tax_eur <= 0:
        zero = Decimal("0.00")
        return ISForecast(
            profit_before_tax_eur=_round_eur(profit_before_tax_eur),
            is_reduced_part_eur=zero,
            is_normal_part_eur=zero,
            is_total_eur=zero,
        )

    reduced_base = min(profit_before_tax_eur, IS_REDUCED_THRESHOLD)
    normal_base = max(Decimal("0.00"), profit_before_tax_eur - IS_REDUCED_THRESHOLD)
    reduced_part = _round_eur(reduced_base * IS_RATE_REDUCED)
    normal_part = _round_eur(normal_base * IS_RATE_NORMAL)

    return ISForecast(
        profit_before_tax_eur=_round_eur(profit_before_tax_eur),
        is_reduced_part_eur=reduced_part,
        is_normal_part_eur=normal_part,
        is_total_eur=_round_eur(reduced_part + normal_part),
    )


__all__ = [
    "IS_RATE_NORMAL",
    "IS_RATE_REDUCED",
    "IS_REDUCED_THRESHOLD",
    "VAT_RATE_NORMAL",
    "CA3Report",
    "ISForecast",
    "compute_ca3",
    "estimate_is",
]
