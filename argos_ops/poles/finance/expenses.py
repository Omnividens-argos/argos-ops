"""Dépenses du pôle Finance (archi v2, S5) — audit CSV Qonto.

Réutilise telle quelle la logique pure existante (pas de re-port) :
:func:`argos_ops.finance.expense_csv.parse_qonto_csv` /
:func:`detect_anomalies` + les helpers journal vendor de
:mod:`argos_ops.agents.expense_auditor`
(:func:`find_latest_csv` / :func:`load_vendor_history` /
:func:`append_new_vendors` / :func:`build_report`).

Le fondateur dépose ses exports Qonto dans
``data/poles/finance/expenses/<YYYY-MM>.csv`` (D-017 : pas d'API Qonto). Le
journal des vendors connus est maintenu dans ``expenses/vendors.md``.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.expense_auditor import (
    ExpenseAuditReport,
    append_new_vendors,
    build_report,
    find_latest_csv,
    load_vendor_history,
)
from argos_ops.finance.expense_csv import detect_anomalies, parse_qonto_csv
from argos_ops.poles.config import POLES_DIR

FINANCE_POLE = "finance"


def expenses_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "expenses"


def latest_csv(*, poles_root: Path = POLES_DIR) -> Path | None:
    """Dernier export Qonto (par mtime) ou ``None`` si aucun."""
    return find_latest_csv(expenses_dir(poles_root=poles_root))


def audit(*, poles_root: Path = POLES_DIR, update_history: bool = False) -> ExpenseAuditReport:
    """Audite le dernier CSV Qonto (anomalies vs historique vendors).

    ``update_history=True`` (utilisé par le script) ajoute les nouveaux vendors
    au journal ; le cockpit lit en read-only (``False``) pour ne rien muter.
    """
    d = expenses_dir(poles_root=poles_root)
    source = find_latest_csv(d)
    if source is None:
        return build_report(None, [])
    expenses = parse_qonto_csv(source)
    history = load_vendor_history(d)
    anomalies = detect_anomalies(expenses, historic_vendors=history)
    if update_history:
        append_new_vendors(d, {e.vendor for e in expenses})
    return build_report(source, anomalies)


__all__ = [
    "ExpenseAuditReport",
    "audit",
    "expenses_dir",
    "latest_csv",
]
