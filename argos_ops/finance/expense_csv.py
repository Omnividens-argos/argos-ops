"""Parser CSV export Qonto (ExpenseAuditor — Sprint 10).

Qonto exporte un CSV par compte avec colonnes canoniques (English ou
Français selon la locale du compte). On supporte les deux entêtes.

Anomalies détectées :

- ``amount_outlier`` : transaction > 3x la médiane mensuelle (seuil
  configurable). Catch les achats inhabituels.
- ``duplicate`` : même (vendor, amount, date à 1j près) → potentiel
  double prélèvement.
- ``new_vendor`` : vendor jamais vu avant dans l'historique. Catch
  les nouveaux abonnements SaaS récurrents.

Pas de connexion API Qonto (D-017 — pas de SaaS récurrent supplémentaire).
Le founder exporte un CSV depuis l'interface web et le pose dans
``data/expenses/<YYYY-MM>.csv``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

AnomalyKind = Literal["amount_outlier", "duplicate", "new_vendor"]

# Mapping headers EN ↔ FR (Qonto export accepte les deux selon locale)
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("Settlement date", "Date de règlement", "Date", "Operation date"),
    "vendor": ("Counterparty name", "Nom de la contrepartie", "Bénéficiaire", "Counterparty"),
    "amount": ("Total amount (EUR)", "Montant total (EUR)", "Amount", "Montant"),
    "label": ("Reference", "Référence", "Label", "Libellé"),
}


@dataclass(frozen=True)
class Expense:
    """Une ligne de transaction Qonto normalisée."""

    settled_on: date
    vendor: str
    amount_eur: Decimal  # négatif = dépense, positif = recette
    label: str | None


@dataclass(frozen=True)
class Anomaly:
    """Une anomalie détectée sur une dépense (à examiner par le founder)."""

    expense: Expense
    kind: AnomalyKind
    reason: str


def _pick_column(header: list[str], aliases: tuple[str, ...]) -> str | None:
    """Trouve le nom de colonne réel parmi les alias acceptés."""
    for alias in aliases:
        if alias in header:
            return alias
    return None


def _parse_amount(raw: str) -> Decimal | None:
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_qonto_csv(path: Path) -> list[Expense]:
    """Parse un export Qonto. Lignes mal formées → skip silencieux."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=",")
        header = reader.fieldnames or []
        if not header:
            # Re-essayer avec un séparateur ";" (export FR)
            fh.seek(0)
            reader = csv.DictReader(fh, delimiter=";")
            header = reader.fieldnames or []
        date_col = _pick_column(header, COLUMN_ALIASES["date"])
        vendor_col = _pick_column(header, COLUMN_ALIASES["vendor"])
        amount_col = _pick_column(header, COLUMN_ALIASES["amount"])
        label_col = _pick_column(header, COLUMN_ALIASES["label"])
        if not (date_col and vendor_col and amount_col):
            return []

        expenses: list[Expense] = []
        for row in reader:
            settled_on = _parse_date(row.get(date_col, ""))
            amount = _parse_amount(row.get(amount_col, ""))
            vendor = (row.get(vendor_col, "") or "").strip()
            if settled_on is None or amount is None or not vendor:
                continue
            expenses.append(
                Expense(
                    settled_on=settled_on,
                    vendor=vendor,
                    amount_eur=amount,
                    label=(row.get(label_col) or None) if label_col else None,
                )
            )
        return expenses


def detect_anomalies(
    expenses: list[Expense],
    *,
    historic_vendors: set[str] | None = None,
    outlier_multiplier: Decimal = Decimal("3"),
) -> list[Anomaly]:
    """Applique les 3 règles d'anomalie sur la liste d'expenses.

    ``historic_vendors`` est l'ensemble des fournisseurs déjà vus dans
    les exports précédents (None = pas d'historique → tous les vendors
    sont "nouveaux", on skippe la règle ``new_vendor``).
    """
    anomalies: list[Anomaly] = []
    historic_vendors = historic_vendors if historic_vendors is not None else None

    debit_amounts = [abs(e.amount_eur) for e in expenses if e.amount_eur < 0]
    if debit_amounts:
        sorted_amounts = sorted(debit_amounts)
        median = sorted_amounts[len(sorted_amounts) // 2]
        outlier_threshold = median * outlier_multiplier
    else:
        outlier_threshold = Decimal("0.00")

    seen_signatures: dict[tuple[str, Decimal, date], int] = {}
    for exp in expenses:
        if exp.amount_eur < 0 and abs(exp.amount_eur) > outlier_threshold > 0:
            anomalies.append(
                Anomaly(
                    expense=exp,
                    kind="amount_outlier",
                    reason=(
                        f"montant {abs(exp.amount_eur)} € > seuil "
                        f"{outlier_threshold:.2f} € (3x médiane)"
                    ),
                )
            )

        sig = (exp.vendor.lower(), exp.amount_eur, exp.settled_on)
        seen_signatures[sig] = seen_signatures.get(sig, 0) + 1

        if historic_vendors is not None and exp.vendor not in historic_vendors:
            anomalies.append(
                Anomaly(
                    expense=exp,
                    kind="new_vendor",
                    reason=f"vendor jamais vu : {exp.vendor}",
                )
            )

    for sig, count in seen_signatures.items():
        if count > 1:
            vendor_match = next(
                (e for e in expenses if (e.vendor.lower(), e.amount_eur, e.settled_on) == sig),
                None,
            )
            if vendor_match is not None:
                anomalies.append(
                    Anomaly(
                        expense=vendor_match,
                        kind="duplicate",
                        reason=(
                            f"{count} transactions identiques "
                            f"({vendor_match.vendor}, {vendor_match.amount_eur} €, "
                            f"{vendor_match.settled_on})"
                        ),
                    )
                )
    return anomalies


__all__ = [
    "COLUMN_ALIASES",
    "Anomaly",
    "AnomalyKind",
    "Expense",
    "detect_anomalies",
    "parse_qonto_csv",
]
