"""Export comptable du pôle Finance (archi v2, S5).

Produit un CSV comptable (journal de trésorerie) depuis le tableur des flux
(:mod:`argos_ops.poles.finance.ledger`) : une ligne par mouvement, colonnes
``date / libellé / catégorie / débit / crédit / solde`` (solde cumulé). Écrit
dans ``data/poles/finance/docs/exports/`` et renvoie aussi le texte CSV (pour le
téléchargement direct depuis le cockpit). Format FR-friendly, encodage UTF-8.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.docs import docs_dir
from argos_ops.poles.finance.ledger import load_flows

FINANCE_POLE = "finance"

_HEADER = ("date", "libelle", "categorie", "debit_eur", "credit_eur", "solde_eur")


def exports_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return docs_dir(poles_root=poles_root) / "exports"


def build_accounting_csv(*, poles_root: Path = POLES_DIR) -> str:
    """Construit le CSV comptable (solde cumulé) depuis le tableur des flux."""
    flows = load_flows(poles_root=poles_root)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADER)
    balance = Decimal("0.00")
    for f in flows:
        balance += f.signed_eur
        debit = f.amount_eur if f.direction == "out" else Decimal("0.00")
        credit = f.amount_eur if f.direction == "in" else Decimal("0.00")
        writer.writerow(
            [
                f.flow_date.isoformat(),
                f.label,
                f.category,
                f"{debit:.2f}",
                f"{credit:.2f}",
                f"{balance:.2f}",
            ]
        )
    return buf.getvalue()


def export_accounting(*, poles_root: Path = POLES_DIR, today: date | None = None) -> Path:
    """Écrit le CSV comptable daté et renvoie son chemin."""
    today = today or date.today()
    content = build_accounting_csv(poles_root=poles_root)
    d = exports_dir(poles_root=poles_root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"export_comptable_{today.isoformat()}.csv"
    path.write_text(content, encoding="utf-8")
    return path


__all__ = [
    "build_accounting_csv",
    "export_accounting",
    "exports_dir",
]
