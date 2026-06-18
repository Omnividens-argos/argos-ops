"""Rapprochement bancaire du pôle Finance (archi v2, S5).

Réutilise telle quelle :func:`argos_ops.finance.reconcile.reconcile` +
:func:`parse_payouts_yaml_entries` (pas de re-port). Croise les payouts Stripe
déclarés (``data/poles/finance/reconcile/payouts.yaml``) avec les crédits du
dernier export Qonto (``data/poles/finance/expenses/<YYYY-MM>.csv``, partagé avec
:mod:`argos_ops.poles.finance.expenses`).

Output : matchés / payouts orphelins / crédits orphelins. Le fondateur regarde
les orphelins en priorité (bug d'export ou fraude).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.finance.expense_csv import parse_qonto_csv
from argos_ops.finance.reconcile import (
    ReconcileReport,
    StripePayout,
    parse_payouts_yaml_entries,
    reconcile,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.expenses import latest_csv
from argos_ops.poles.finance.store import load_yaml_mapping

FINANCE_POLE = "finance"


def payouts_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "reconcile" / "payouts.yaml"


def load_payouts(*, poles_root: Path = POLES_DIR) -> list[StripePayout]:
    """Lit les payouts Stripe déclarés. Absent ⇒ ``[]``."""
    raw = load_yaml_mapping(payouts_path(poles_root=poles_root))
    rows = raw.get("payouts") or []
    if not isinstance(rows, list):
        return []
    return parse_payouts_yaml_entries([r for r in rows if isinstance(r, dict)])


def reconcile_report(*, poles_root: Path = POLES_DIR) -> ReconcileReport:
    """Rapproche payouts Stripe ↔ crédits Qonto (best-effort si CSV absent)."""
    payouts = load_payouts(poles_root=poles_root)
    csv_path = latest_csv(poles_root=poles_root)
    expenses = parse_qonto_csv(csv_path) if csv_path is not None else []
    return reconcile(payouts, expenses)


__all__ = [
    "ReconcileReport",
    "StripePayout",
    "load_payouts",
    "payouts_path",
    "reconcile_report",
]
