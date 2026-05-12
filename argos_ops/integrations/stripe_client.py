"""Wrapper async sur le SDK Stripe (sync) pour FinanceBot (P7).

Le SDK Stripe officiel ``stripe>=9.5`` est synchrone (httplib sous le capot).
On enrobe les appels dans :func:`asyncio.to_thread` pour ne pas bloquer la
boucle async — pattern identique à :mod:`argos_ops.integrations.zimbra`.

API publique :

- :class:`StripeSubscription` / :class:`StripeInvoice` — DTOs normalisés
- :func:`fetch_active_subscriptions` — liste des subs en cours
- :func:`fetch_open_invoices` — factures impayées (status=open ou past_due)
- :func:`compute_mrr_eur` — calcul MRR canonique (annuel→mensuel équivalent)
- :func:`classify_dunning_level` — classification J+3 / J+7 / J+15

Compte Stripe partagé avec SecHunter (cf. P0 décision). La clé est dans
``STRIPE_SECRET_KEY`` (``.env.local``). Utiliser un compte test avant prod.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import stripe
from loguru import logger
from pydantic import SecretStr


# =============================================================================
# DTOs
# =============================================================================
@dataclass(frozen=True)
class StripeSubscription:
    """Subscription Stripe normalisée pour Argos Ops."""

    id: str
    customer_id: str
    customer_email: str | None
    customer_name: str | None
    status: str  # 'active' | 'trialing' | 'past_due' | 'canceled' | 'unpaid' | 'incomplete'
    mrr_eur: Decimal  # MRR équivalent mensuel (annuel divisé par 12)
    currency: str
    interval: str  # 'month' | 'year'
    created_at: datetime
    current_period_end: datetime | None


@dataclass(frozen=True)
class StripeInvoice:
    """Invoice Stripe normalisée — usage principal : dunning impayés."""

    id: str
    customer_id: str
    customer_email: str | None
    customer_name: str | None
    status: str  # 'draft' | 'open' | 'paid' | 'uncollectible' | 'void'
    amount_due_eur: Decimal  # 0 si payée
    due_date: datetime | None  # None pour les factures sans date d'échéance
    created_at: datetime
    attempt_count: int  # nombre de tentatives Stripe Smart Retries
    hosted_invoice_url: str | None  # lien public à inclure dans l'email de relance


# =============================================================================
# Init
# =============================================================================
def _configure(api_key: SecretStr) -> None:
    """Configure la clé API Stripe — appelé en début de chaque appel."""
    stripe.api_key = api_key.get_secret_value()


# =============================================================================
# Conversion DTOs
# =============================================================================
def _eur_from_cents(cents: int | None, currency: str) -> Decimal:
    """Convertit un montant Stripe (cents int, eur attendu) en Decimal eur."""
    if cents is None:
        return Decimal("0.00")
    if currency.lower() != "eur":
        # Hors-scope P7 — Argos est facturé en EUR uniquement (pricing.md).
        # Si une sub multi-devise apparaît, on log mais on retourne 0 pour
        # éviter une mauvaise agrégation MRR.
        logger.warning(f"Currency '{currency}' non gérée — montant ignoré")
        return Decimal("0.00")
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def _mrr_from_subscription(sub_obj: Any) -> Decimal:
    """Calcule le MRR équivalent mensuel d'une subscription Stripe.

    Mensuel : unit_amount * quantity / 100
    Annuel : (unit_amount * quantity / 100) / 12
    """
    items = (sub_obj.get("items") or {}).get("data") or []
    if not items:
        return Decimal("0.00")
    total = Decimal("0.00")
    for item in items:
        price = item.get("price") or {}
        recurring = price.get("recurring") or {}
        unit_amount = price.get("unit_amount") or 0
        quantity = item.get("quantity") or 1
        currency = price.get("currency") or "eur"
        amount_eur = _eur_from_cents(unit_amount * quantity, currency)
        interval = recurring.get("interval") or "month"
        if interval == "year":
            amount_eur = (amount_eur / Decimal(12)).quantize(Decimal("0.01"))
        elif interval not in ("month",):
            # 'week' / 'day' : hors scope, on ignore
            logger.warning(f"Interval '{interval}' non géré — sub ignorée")
            return Decimal("0.00")
        total += amount_eur
    return total


def _to_subscription_dto(sub_obj: Any) -> StripeSubscription:
    customer = sub_obj.get("customer") or {}
    if isinstance(customer, str):
        customer = {"id": customer}
    return StripeSubscription(
        id=sub_obj["id"],
        customer_id=customer.get("id", ""),
        customer_email=customer.get("email"),
        customer_name=customer.get("name"),
        status=sub_obj.get("status", "unknown"),
        mrr_eur=_mrr_from_subscription(sub_obj),
        currency=(((sub_obj.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get(
            "currency", "eur"
        ),
        interval=(
            (((sub_obj.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get(
                "recurring"
            )
            or {}
        ).get("interval", "month"),
        created_at=datetime.fromtimestamp(sub_obj["created"], tz=UTC),
        current_period_end=(
            datetime.fromtimestamp(sub_obj["current_period_end"], tz=UTC)
            if sub_obj.get("current_period_end")
            else None
        ),
    )


def _to_invoice_dto(inv_obj: Any) -> StripeInvoice:
    customer = inv_obj.get("customer") or {}
    if isinstance(customer, str):
        customer = {"id": customer}
    return StripeInvoice(
        id=inv_obj["id"],
        customer_id=customer.get("id", ""),
        customer_email=customer.get("email") or inv_obj.get("customer_email"),
        customer_name=customer.get("name") or inv_obj.get("customer_name"),
        status=inv_obj.get("status", "unknown"),
        amount_due_eur=_eur_from_cents(inv_obj.get("amount_due"), inv_obj.get("currency") or "eur"),
        due_date=(
            datetime.fromtimestamp(inv_obj["due_date"], tz=UTC) if inv_obj.get("due_date") else None
        ),
        created_at=datetime.fromtimestamp(inv_obj["created"], tz=UTC),
        attempt_count=inv_obj.get("attempt_count", 0),
        hosted_invoice_url=inv_obj.get("hosted_invoice_url"),
    )


# =============================================================================
# Fetchers (sync wrappers)
# =============================================================================
def _list_subscriptions_sync(api_key: SecretStr, limit: int) -> list[StripeSubscription]:
    _configure(api_key)
    out: list[StripeSubscription] = []
    # status='all' inclut les sub annulées — utile pour calculer les churns.
    for sub_obj in stripe.Subscription.list(
        status="all",
        limit=limit,
        expand=["data.customer"],
    ).auto_paging_iter():
        out.append(_to_subscription_dto(sub_obj))
    return out


def _list_open_invoices_sync(api_key: SecretStr, limit: int) -> list[StripeInvoice]:
    _configure(api_key)
    out: list[StripeInvoice] = []
    for inv_obj in stripe.Invoice.list(
        status="open",
        limit=limit,
        expand=["data.customer"],
    ).auto_paging_iter():
        out.append(_to_invoice_dto(inv_obj))
    return out


# =============================================================================
# API async
# =============================================================================
async def fetch_active_subscriptions(
    api_key: SecretStr, *, limit: int = 100
) -> list[StripeSubscription]:
    """Pull async toutes les subs (toutes statuts confondus pour MRR + churn)."""
    return await asyncio.to_thread(_list_subscriptions_sync, api_key, limit)


async def fetch_open_invoices(api_key: SecretStr, *, limit: int = 100) -> list[StripeInvoice]:
    """Pull async toutes les factures ``status='open'`` (impayées)."""
    return await asyncio.to_thread(_list_open_invoices_sync, api_key, limit)


# =============================================================================
# Calculs MRR + dunning
# =============================================================================
def compute_mrr_eur(subs: list[StripeSubscription]) -> Decimal:
    """MRR canonique : somme des subs ``status in ('active', 'trialing')``."""
    total = Decimal("0.00")
    for sub in subs:
        if sub.status in ("active", "trialing"):
            total += sub.mrr_eur
    return total.quantize(Decimal("0.01"))


def compute_arr_eur(mrr_eur: Decimal) -> Decimal:
    """ARR = MRR * 12, formule canonique."""
    return (mrr_eur * Decimal(12)).quantize(Decimal("0.01"))


DunningLevel = Literal["J+3", "J+7", "J+15", "none"]


def classify_dunning_level(invoice: StripeInvoice, *, now: datetime | None = None) -> DunningLevel:
    """Classe une facture impayée selon le délai depuis la due_date.

    - J+3 : 3-6 jours de retard (relance amicale)
    - J+7 : 7-14 jours (relance ferme)
    - J+15 : 15+ jours (escalade)
    - 'none' : pas due_date OR retard < 3 jours OR facture pas en 'open'
    """
    if invoice.status != "open" or invoice.due_date is None:
        return "none"
    now = now or datetime.now(UTC)
    days_late = (now - invoice.due_date).days
    if days_late < 3:
        return "none"
    if days_late < 7:
        return "J+3"
    if days_late < 15:
        return "J+7"
    return "J+15"


__all__ = [
    "DunningLevel",
    "StripeInvoice",
    "StripeSubscription",
    "classify_dunning_level",
    "compute_arr_eur",
    "compute_mrr_eur",
    "fetch_active_subscriptions",
    "fetch_open_invoices",
]
