"""Endpoint webhook Stripe — signature verify + dispatch idempotent (P7).

Stripe envoie un POST sur ``/api/stripe/webhook`` à chaque événement
(``invoice.payment_failed``, ``customer.subscription.created``, etc.).
On vérifie la signature HMAC via ``stripe.Webhook.construct_event()``
puis on délègue au handler de FinanceBot.

Sécurité :
    - ``STRIPE_WEBHOOK_SECRET`` (whsec_…) configuré dans ``.env``. Sans lui
      le endpoint répond 503 (Service Unavailable) — refuse de traiter
      des événements non vérifiables plutôt que de les laisser passer.
    - Idempotency : Stripe peut retrier le même event jusqu'à 3 jours.
      On déduplique via un cache mémoire (LRU 1024 dernières event IDs).
      Acceptable car FinanceBot pollera Stripe via API en complément.

Pas de DB write dans ce handler : on logue l'événement et retourne 200.
Le FinanceBot quotidien (P7) fait la source-of-truth via l'API Stripe.
Le webhook sert juste à déclencher des actions temps-réel ponctuelles
(ex: notifier Discord sur ``invoice.payment_failed``).
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import stripe
from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from argos_ops.config import get_settings

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# Cache LRU (event_id) -> True, 1024 derniers. Stripe ne retry pas au-delà
# de 3 jours, donc 1024 events couvre largement un trafic normal.
_RECENT_EVENT_IDS: OrderedDict[str, bool] = OrderedDict()
_DEDUP_MAX = 1024


def _mark_seen(event_id: str) -> bool:
    """Renvoie True si l'event est nouveau, False si déjà traité (idempotency)."""
    if event_id in _RECENT_EVENT_IDS:
        _RECENT_EVENT_IDS.move_to_end(event_id)
        return False
    _RECENT_EVENT_IDS[event_id] = True
    if len(_RECENT_EVENT_IDS) > _DEDUP_MAX:
        _RECENT_EVENT_IDS.popitem(last=False)
    return True


def reset_dedup_cache_for_tests() -> None:
    """Reset le cache LRU. Réservé aux tests."""
    _RECENT_EVENT_IDS.clear()


def _construct_event(payload: bytes, signature: str, secret: str) -> Any:
    """Vérifie la signature HMAC Stripe et retourne le StripeObject Event."""
    return stripe.Webhook.construct_event(  # type: ignore[no-untyped-call]
        payload=payload, sig_header=signature, secret=secret
    )


async def _dispatch(event: Any) -> None:
    """Logue l'événement. Futurs hooks FinanceBot temps-réel s'insèrent ici."""
    event_type = getattr(event, "type", "unknown")
    event_id = getattr(event, "id", "?")
    livemode = getattr(event, "livemode", False)
    logger.info(
        f"Stripe webhook reçu : type={event_type} id={event_id} live={livemode}"
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.stripe_webhook_secret
    if secret is None:
        # Refuse plutôt que de laisser passer des events non vérifiés.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_WEBHOOK_SECRET non configuré",
        )

    signature = request.headers.get("stripe-signature", "")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header stripe-signature manquant",
        )

    payload = await request.body()
    try:
        event = _construct_event(payload, signature, secret.get_secret_value())
    except stripe.SignatureVerificationError as exc:
        logger.warning(f"Stripe webhook signature invalide : {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature Stripe invalide",
        ) from exc
    except ValueError as exc:
        logger.warning(f"Stripe webhook payload invalide : {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload JSON invalide",
        ) from exc

    event_id = getattr(event, "id", "") or ""
    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event sans id",
        )

    is_new = _mark_seen(event_id)
    if not is_new:
        logger.debug(f"Stripe webhook dédupliqué : {event_id}")
        return {"received": True, "duplicate": True, "event_id": event_id}

    await _dispatch(event)
    return {"received": True, "duplicate": False, "event_id": event_id}


__all__ = ["reset_dedup_cache_for_tests", "router"]
