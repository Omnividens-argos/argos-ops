"""Trésorerie du pôle Finance (archi v2, S5) — burn & runway.

Réutilise telle quelle la logique pure de
:mod:`argos_ops.agents.burn_rate_monitor` (:func:`load_treasury` +
:func:`build_report`) — pas de re-port — en la pointant sur le snapshot local
``data/poles/finance/treasury/state.yaml`` (mêmes champs que le YAML legacy :
``cash_balance_eur`` / ``monthly_burn_eur`` / ``monthly_revenue_eur`` /
``snapshot_date`` / ``burn_cap_eur``).

Local-first (D-017) : aucune valeur secrète, lecture best-effort.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.burn_rate_monitor import (
    RUNWAY_ALERT_MONTHS,
    RUNWAY_WARN_MONTHS,
    BurnReport,
    TreasurySnapshot,
    build_report,
    load_treasury,
)
from argos_ops.poles.config import POLES_DIR

FINANCE_POLE = "finance"


def treasury_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "treasury" / "state.yaml"


def load_snapshot(*, poles_root: Path = POLES_DIR) -> TreasurySnapshot | None:
    """Lit l'état trésorerie déclaré (``None`` si pas encore renseigné)."""
    return load_treasury(treasury_path(poles_root=poles_root))


def burn_report(*, poles_root: Path = POLES_DIR) -> BurnReport:
    """Calcule net burn + runway + sévérité depuis le snapshot."""
    return build_report(load_snapshot(poles_root=poles_root))


__all__ = [
    "RUNWAY_ALERT_MONTHS",
    "RUNWAY_WARN_MONTHS",
    "BurnReport",
    "TreasurySnapshot",
    "burn_report",
    "load_snapshot",
    "treasury_path",
]
