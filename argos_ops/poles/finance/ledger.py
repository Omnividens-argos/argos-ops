"""Tableur des flux du pôle Finance (archi v2, S5) — éditable.

Le « tableur des flux » du cockpit : un journal de mouvements de trésorerie
(entrées / sorties) **éditable** par le fondateur, stocké en
``data/poles/finance/ledger/flows.yaml``. Chaque ligne porte un ``id`` stable
dérivé de son contenu (ajout idempotent — deux fois la même ligne ⇒ une seule).

Pur, sans LLM : agrégats déterministes (total in/out, net, net par mois, net par
catégorie). Aucune valeur secrète (D-017).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.store import dump_yaml_mapping, load_yaml_mapping, parse_date

FINANCE_POLE = "finance"
FlowDirection = Literal["in", "out"]
_ID_LEN = 10


def ledger_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "ledger" / "flows.yaml"


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


@dataclass(frozen=True)
class Flow:
    """Un mouvement de trésorerie du tableur."""

    id: str
    flow_date: date
    label: str
    category: str
    direction: FlowDirection
    amount_eur: Decimal  # toujours positif ; le signe vient de ``direction``

    @property
    def signed_eur(self) -> Decimal:
        return self.amount_eur if self.direction == "in" else -self.amount_eur


@dataclass(frozen=True)
class LedgerSummary:
    """Agrégats du tableur."""

    total_in_eur: Decimal
    total_out_eur: Decimal
    net_eur: Decimal
    count: int
    by_month: list[tuple[str, Decimal]]  # (YYYY-MM, net) trié
    by_category: list[tuple[str, Decimal]]  # (catégorie, net signé) trié desc


def compute_flow_id(flow_date: date, label: str, direction: str, amount: Decimal) -> str:
    """Identifiant stable d'une ligne (hash de son contenu normalisé)."""
    payload = f"{flow_date.isoformat()}|{label.strip().lower()}|{direction}|{amount}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:_ID_LEN]


def _normalize_direction(value: object) -> FlowDirection:
    return "out" if str(value).strip().lower() == "out" else "in"


def load_flows(*, poles_root: Path = POLES_DIR) -> list[Flow]:
    """Lit le tableur (trié par date croissante puis label). Absent ⇒ ``[]``."""
    raw = load_yaml_mapping(ledger_path(poles_root=poles_root))
    rows = raw.get("flows") or []
    if not isinstance(rows, list):
        return []
    out: list[Flow] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        try:
            flow_date = parse_date(row["date"])
        except (ValueError, TypeError):
            continue
        amount = _to_decimal(row.get("amount_eur"))
        direction = _normalize_direction(row.get("direction"))
        label = str(row.get("label") or "")
        fid = str(row.get("id") or compute_flow_id(flow_date, label, direction, amount))
        out.append(
            Flow(
                id=fid,
                flow_date=flow_date,
                label=label,
                category=str(row.get("category") or "autre"),
                direction=direction,
                amount_eur=amount,
            )
        )
    out.sort(key=lambda f: (f.flow_date, f.label))
    return out


def _persist(flows: list[Flow], *, poles_root: Path) -> None:
    data = {
        "flows": [
            {
                "id": f.id,
                "date": f.flow_date.isoformat(),
                "label": f.label,
                "category": f.category,
                "direction": f.direction,
                "amount_eur": str(f.amount_eur),
            }
            for f in flows
        ]
    }
    dump_yaml_mapping(ledger_path(poles_root=poles_root), data)


def add_flow(
    *,
    flow_date: date,
    label: str,
    category: str,
    direction: FlowDirection,
    amount_eur: Decimal,
    poles_root: Path = POLES_DIR,
) -> Flow:
    """Ajoute une ligne au tableur (idempotent par contenu). Renvoie la ligne."""
    amount = amount_eur.quantize(Decimal("0.01"))
    fid = compute_flow_id(flow_date, label, direction, amount)
    flow = Flow(
        id=fid,
        flow_date=flow_date,
        label=label,
        category=category or "autre",
        direction=direction,
        amount_eur=amount,
    )
    flows = [f for f in load_flows(poles_root=poles_root) if f.id != fid]
    flows.append(flow)
    flows.sort(key=lambda f: (f.flow_date, f.label))
    _persist(flows, poles_root=poles_root)
    return flow


def update_flow(
    flow_id: str,
    *,
    flow_date: date,
    label: str,
    category: str,
    direction: FlowDirection,
    amount_eur: Decimal,
    poles_root: Path = POLES_DIR,
) -> Flow | None:
    """Édite une ligne existante en place. ``None`` si ``flow_id`` inconnu.

    Le tableur est réécrit ; l'``id`` de la ligne reste **stable** (on ne le
    recalcule pas depuis le nouveau contenu) pour que la ligne éditée garde son
    identité côté cockpit. Si la nouvelle valeur entre en collision avec une
    autre ligne, l'autre n'est pas touchée (l'unicité par contenu n'est garantie
    qu'à l'ajout). Renvoie la ligne mise à jour, ré-triée à sa place.
    """
    flows = load_flows(poles_root=poles_root)
    if not any(f.id == flow_id for f in flows):
        return None
    amount = amount_eur.quantize(Decimal("0.01"))
    updated = Flow(
        id=flow_id,
        flow_date=flow_date,
        label=label,
        category=category or "autre",
        direction=direction,
        amount_eur=amount,
    )
    flows = [updated if f.id == flow_id else f for f in flows]
    flows.sort(key=lambda f: (f.flow_date, f.label))
    _persist(flows, poles_root=poles_root)
    return updated


def delete_flow(flow_id: str, *, poles_root: Path = POLES_DIR) -> bool:
    """Supprime une ligne. ``True`` si elle existait."""
    flows = load_flows(poles_root=poles_root)
    kept = [f for f in flows if f.id != flow_id]
    if len(kept) == len(flows):
        return False
    _persist(kept, poles_root=poles_root)
    return True


def summarize(flows: list[Flow]) -> LedgerSummary:
    """Agrège le tableur (total in/out, net, net par mois, net par catégorie)."""
    total_in = sum((f.amount_eur for f in flows if f.direction == "in"), Decimal("0.00"))
    total_out = sum((f.amount_eur for f in flows if f.direction == "out"), Decimal("0.00"))
    by_month: dict[str, Decimal] = {}
    by_cat: dict[str, Decimal] = {}
    for f in flows:
        month = f.flow_date.strftime("%Y-%m")
        by_month[month] = by_month.get(month, Decimal("0.00")) + f.signed_eur
        by_cat[f.category] = by_cat.get(f.category, Decimal("0.00")) + f.signed_eur
    return LedgerSummary(
        total_in_eur=total_in.quantize(Decimal("0.01")),
        total_out_eur=total_out.quantize(Decimal("0.01")),
        net_eur=(total_in - total_out).quantize(Decimal("0.01")),
        count=len(flows),
        by_month=sorted(by_month.items()),
        by_category=sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True),
    )


__all__ = [
    "Flow",
    "FlowDirection",
    "LedgerSummary",
    "add_flow",
    "compute_flow_id",
    "delete_flow",
    "ledger_path",
    "load_flows",
    "summarize",
    "update_flow",
]
