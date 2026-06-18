"""Facturation du pôle Finance (archi v2, S5) — MRR, dunning, forecast.

Réutilise les briques pures existantes (pas de re-port) :

- :class:`argos_ops.integrations.stripe_client.StripeSubscription` /
  :class:`StripeInvoice` (DTOs) + :func:`compute_mrr_eur` / :func:`compute_arr_eur`
  / :func:`classify_dunning_level` ;
- :data:`argos_ops.agents.finance_bot.DUNNING_TEMPLATES` +
  :func:`render_dunning_email` (templates de relance dégradés, ton pré-écrit) ;
- :func:`argos_ops.finance.cash_flow.forecast_cash_flow`.

**Local-first (D-017)** : aucune lecture Stripe live ici. Les subs/factures sont
lues depuis un **snapshot** ``data/poles/finance/billing/{subscriptions,invoices}.yaml``
(le ``finance_bot`` rafraîchit ce snapshot depuis Stripe quand une clé API est
présente ; sinon le fondateur l'exporte à la main). Le drafting de relance est en
**mode shadow** : on écrit un brouillon, on n'envoie rien (humain-in-the-loop).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from loguru import logger

from argos_ops.agents.finance_bot import render_dunning_email
from argos_ops.finance.cash_flow import CashFlowForecast, forecast_cash_flow
from argos_ops.integrations.stripe_client import (
    DunningLevel,
    StripeInvoice,
    StripeSubscription,
    classify_dunning_level,
    compute_arr_eur,
    compute_mrr_eur,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.store import load_yaml_mapping, write_markdown

FINANCE_POLE = "finance"

# Statuts de sub considérés « sains » (contribuent au MRR canonique).
HEALTHY_SUB_STATUSES: frozenset[str] = frozenset({"active", "trialing"})


# =============================================================================
# Chemins
# =============================================================================
def billing_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "billing"


def subscriptions_path(*, poles_root: Path = POLES_DIR) -> Path:
    return billing_dir(poles_root=poles_root) / "subscriptions.yaml"


def invoices_path(*, poles_root: Path = POLES_DIR) -> Path:
    return billing_dir(poles_root=poles_root) / "invoices.yaml"


def dunning_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return billing_dir(poles_root=poles_root) / "dunning"


# =============================================================================
# Parsing snapshot → DTOs Stripe
# =============================================================================
def _to_decimal(value: object, default: Decimal = Decimal("0.00")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _to_dt(value: object) -> datetime | None:
    """Normalise une valeur YAML (date/datetime/str ISO) en ``datetime`` UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def load_subscriptions(*, poles_root: Path = POLES_DIR) -> list[StripeSubscription]:
    """Lit le snapshot des subscriptions. Absent ⇒ ``[]`` (best-effort cockpit)."""
    raw = load_yaml_mapping(subscriptions_path(poles_root=poles_root))
    rows = raw.get("subscriptions") or []
    if not isinstance(rows, list):
        return []
    out: list[StripeSubscription] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            StripeSubscription(
                id=str(row["id"]),
                customer_id=str(row.get("customer_id", "")),
                customer_email=(str(row["customer_email"]) if row.get("customer_email") else None),
                customer_name=(str(row["customer_name"]) if row.get("customer_name") else None),
                status=str(row.get("status", "active")),
                mrr_eur=_to_decimal(row.get("mrr_eur")),
                currency=str(row.get("currency", "eur")),
                interval=str(row.get("interval", "month")),
                created_at=_to_dt(row.get("created_at")) or datetime.now(UTC),
                current_period_end=_to_dt(row.get("current_period_end")),
            )
        )
    return out


def load_invoices(*, poles_root: Path = POLES_DIR) -> list[StripeInvoice]:
    """Lit le snapshot des factures (impayées ou non). Absent ⇒ ``[]``."""
    raw = load_yaml_mapping(invoices_path(poles_root=poles_root))
    rows = raw.get("invoices") or []
    if not isinstance(rows, list):
        return []
    out: list[StripeInvoice] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            StripeInvoice(
                id=str(row["id"]),
                customer_id=str(row.get("customer_id", "")),
                customer_email=(str(row["customer_email"]) if row.get("customer_email") else None),
                customer_name=(str(row["customer_name"]) if row.get("customer_name") else None),
                status=str(row.get("status", "open")),
                amount_due_eur=_to_decimal(row.get("amount_due_eur")),
                due_date=_to_dt(row.get("due_date")),
                created_at=_to_dt(row.get("created_at")) or datetime.now(UTC),
                attempt_count=int(row.get("attempt_count", 0) or 0),
                hosted_invoice_url=(
                    str(row["hosted_invoice_url"]) if row.get("hosted_invoice_url") else None
                ),
            )
        )
    return out


# =============================================================================
# Vue MRR + dunning
# =============================================================================
@dataclass(frozen=True)
class DunningItem:
    """Une facture impayée + son niveau de relance classifié."""

    invoice_id: str
    customer_id: str
    customer_email: str | None
    customer_name: str | None
    amount_due_eur: Decimal
    due_date: date | None
    level: DunningLevel
    drafted: bool


@dataclass(frozen=True)
class BillingSnapshot:
    """Photo de facturation pour le cockpit + l'agent."""

    n_subs: int
    n_active_subs: int
    mrr_eur: Decimal
    arr_eur: Decimal
    n_open_invoices: int
    open_amount_eur: Decimal
    dunning: tuple[DunningItem, ...]

    @property
    def n_dunning_due(self) -> int:
        return sum(1 for d in self.dunning if d.level != "none")


def _dunning_drafted(invoice_id: str, *, poles_root: Path) -> bool:
    return (dunning_dir(poles_root=poles_root) / f"{invoice_id}.md").exists()


def build_billing_snapshot(
    *, poles_root: Path = POLES_DIR, now: datetime | None = None
) -> BillingSnapshot:
    """Agrège subs + factures en photo de facturation (MRR/ARR + dunning)."""
    now = now or datetime.now(UTC)
    subs = load_subscriptions(poles_root=poles_root)
    invoices = load_invoices(poles_root=poles_root)
    mrr = compute_mrr_eur(subs)

    dunning: list[DunningItem] = []
    open_amount = Decimal("0.00")
    open_invoices = [inv for inv in invoices if inv.status == "open"]
    for inv in open_invoices:
        open_amount += inv.amount_due_eur
        dunning.append(
            DunningItem(
                invoice_id=inv.id,
                customer_id=inv.customer_id,
                customer_email=inv.customer_email,
                customer_name=inv.customer_name,
                amount_due_eur=inv.amount_due_eur,
                due_date=inv.due_date.date() if inv.due_date else None,
                level=classify_dunning_level(inv, now=now),
                drafted=_dunning_drafted(inv.id, poles_root=poles_root),
            )
        )
    # Tri : relance la plus avancée d'abord (J+15 > J+7 > J+3 > none), puis montant.
    order = {"J+15": 3, "J+7": 2, "J+3": 1, "none": 0}
    dunning.sort(key=lambda d: (order.get(d.level, 0), d.amount_due_eur), reverse=True)

    return BillingSnapshot(
        n_subs=len(subs),
        n_active_subs=sum(1 for s in subs if s.status in HEALTHY_SUB_STATUSES),
        mrr_eur=mrr,
        arr_eur=compute_arr_eur(mrr),
        n_open_invoices=len(open_invoices),
        open_amount_eur=open_amount.quantize(Decimal("0.01")),
        dunning=tuple(dunning),
    )


def forecast(*, poles_root: Path = POLES_DIR, now: datetime | None = None) -> CashFlowForecast:
    """Forecast cash flow 30/60/90j depuis le snapshot des subs."""
    subs = load_subscriptions(poles_root=poles_root)
    return forecast_cash_flow(subs, as_of=now or datetime.now(UTC))


# =============================================================================
# Drafting de relance (shadow — humain-in-the-loop)
# =============================================================================
def draft_dunning(
    invoice_id: str, *, poles_root: Path = POLES_DIR, now: datetime | None = None
) -> Path | None:
    """Drafte la relance d'une facture impayée (mode shadow). ``None`` si pas due.

    Renvoie le chemin du brouillon écrit, ou ``None`` si la facture est introuvable
    / déjà payée / pas encore en retard (``level == "none"``). Idempotent au sens
    fichier (réécrit le même brouillon). « Python tranche » : aucun envoi ici.
    """
    invoices = {inv.id: inv for inv in load_invoices(poles_root=poles_root)}
    inv = invoices.get(invoice_id)
    if inv is None:
        return None
    level = classify_dunning_level(inv, now=now or datetime.now(UTC))
    rendered = render_dunning_email(level, inv)
    if rendered is None:
        return None
    subject, body = rendered
    out = dunning_dir(poles_root=poles_root) / f"{invoice_id}.md"
    write_markdown(
        out,
        {
            "invoice_id": inv.id,
            "level": level,
            "to": inv.customer_email or "(email inconnu)",
            "amount_due_eur": str(inv.amount_due_eur),
            "subject": subject,
            "mode": "shadow",
        },
        body=body,
    )
    logger.debug(f"finance/billing — relance {level} draftée (shadow) pour {invoice_id}")
    return out


__all__ = [
    "HEALTHY_SUB_STATUSES",
    "BillingSnapshot",
    "DunningItem",
    "billing_dir",
    "build_billing_snapshot",
    "draft_dunning",
    "dunning_dir",
    "forecast",
    "invoices_path",
    "load_invoices",
    "load_subscriptions",
    "subscriptions_path",
]
