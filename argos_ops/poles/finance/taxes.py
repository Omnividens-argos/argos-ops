"""Fiscalité du pôle Finance (archi v2, S5) — TVA CA3, IS, échéancier.

Réutilise telle quelle (pas de re-port) :func:`argos_ops.finance.tva.compute_ca3`
/ :func:`estimate_is` + :func:`argos_ops.agents.tax_bot.render_tax_markdown`. Le
CA HT est approximé par le MRR Stripe courant (proxy — cf. ``tax_bot``), lu depuis
le snapshot de :mod:`argos_ops.poles.finance.billing`.

Ajoute un **échéancier fiscal** déterministe (:func:`fiscal_calendar`) : prochaines
dates limites FR (CA3 le 19 du mois M+1, acomptes IS trimestriels, CFE, liasse) —
brique du front « échéancier fiscal ». Pur, sans IO ni LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from argos_ops.agents.tax_bot import render_tax_markdown
from argos_ops.finance.tva import CA3Report, ISForecast, compute_ca3, estimate_is
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.billing import build_billing_snapshot

FiscalKind = Literal["tva_ca3", "is_acompte", "cfe", "liasse"]


def _previous_month(today: date) -> str:
    """Mois M-1 au format ``YYYY-MM`` (période déclarée le 19 de M)."""
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def current_ca3(
    *,
    poles_root: Path = POLES_DIR,
    period_month: str | None = None,
    tva_deductible_eur: Decimal = Decimal("0.00"),
    today: date | None = None,
) -> CA3Report:
    """Calcule la CA3 du mois (CA HT = MRR proxy), TVA collectée + nette due."""
    today = today or date.today()
    snapshot = build_billing_snapshot(poles_root=poles_root)
    return compute_ca3(
        period_month=period_month or _previous_month(today),
        ca_ht_eur=snapshot.mrr_eur,
        tva_deductible_eur=tva_deductible_eur,
    )


def is_forecast(profit_before_tax_eur: Decimal) -> ISForecast:
    """IS prévisionnel PME (15 % puis 25 %) sur un résultat avant impôt donné."""
    return estimate_is(profit_before_tax_eur)


# =============================================================================
# Échéancier fiscal
# =============================================================================
@dataclass(frozen=True)
class FiscalDeadline:
    """Une échéance fiscale à venir."""

    kind: FiscalKind
    label: str
    due_date: date
    days_until: int


def _ca3_due_for_month(period_month: str) -> date:
    """Date limite CA3 = le 19 du mois suivant le mois déclaré."""
    year, month = (int(x) for x in period_month.split("-"))
    due_year, due_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return date(due_year, due_month, 19)


def fiscal_calendar(*, today: date | None = None, horizon_days: int = 120) -> list[FiscalDeadline]:
    """Prochaines échéances fiscales FR dans ``horizon_days`` jours (triées).

    Déterministe et conservateur : CA3 mensuelles (19 de M+1) sur l'horizon,
    acomptes IS trimestriels (15/03·06·09·12), CFE (15/12), liasse fiscale (≈05/05).
    """
    today = today or date.today()
    horizon = date.fromordinal(today.toordinal() + horizon_days)
    out: list[FiscalDeadline] = []

    def _add(kind: FiscalKind, label: str, due: date) -> None:
        if today <= due <= horizon:
            out.append(FiscalDeadline(kind, label, due, (due - today).days))

    # CA3 mensuelles couvrant l'horizon (mois M-1 .. fin de l'horizon). Le nombre
    # de mois itérés est dérivé de horizon_days (et non figé) pour ne jamais
    # tronquer une échéance dont la date butoir tombe dans la fenêtre demandée.
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    months_ahead = horizon_days // 30 + 3
    for _ in range(months_ahead):
        period = f"{year:04d}-{month:02d}"
        _add("tva_ca3", f"TVA CA3 {period}", _ca3_due_for_month(period))
        month += 1
        if month == 13:
            year, month = year + 1, 1

    # Acomptes IS trimestriels + CFE + liasse, sur l'année courante et la suivante.
    for y in (today.year, today.year + 1):
        for m in (3, 6, 9, 12):
            _add("is_acompte", f"Acompte IS {y}-{m:02d}", date(y, m, 15))
        _add("cfe", f"CFE {y}", date(y, 12, 15))
        _add("liasse", f"Liasse fiscale {y}", date(y, 5, 5))

    out.sort(key=lambda d: d.due_date)
    return out


__all__ = [
    "CA3Report",
    "FiscalDeadline",
    "FiscalKind",
    "ISForecast",
    "current_ca3",
    "fiscal_calendar",
    "is_forecast",
    "render_tax_markdown",
]
