"""Tests Stripe webhook endpoint — signature verify + idempotency + dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from argos_ops.ops_dashboard.api import stripe_webhook as webhook_mod
from argos_ops.ops_dashboard.app import app

WEBHOOK_SECRET = "whsec_test_dummy_for_unit_tests_only"


def _stripe_signature_header(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Recompose un header stripe-signature valide (cf. Stripe doc Webhook signing)."""
    ts = timestamp or int(time.time())
    signed_payload = f"{ts}.{payload.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


@pytest.fixture(autouse=True)
def _reset_dedup_cache() -> None:
    webhook_mod.reset_dedup_cache_for_tests()


@pytest.fixture
def client_with_secret() -> TestClient:
    """TestClient avec STRIPE_WEBHOOK_SECRET injecté dans settings."""
    from argos_ops.config import get_settings

    settings = get_settings()
    original = settings.stripe_webhook_secret
    settings.stripe_webhook_secret = SecretStr(WEBHOOK_SECRET)
    try:
        yield TestClient(app)
    finally:
        settings.stripe_webhook_secret = original


def _build_event(event_id: str = "evt_test_001", event_type: str = "ping") -> dict[str, Any]:
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "livemode": False,
        "api_version": "2024-04-10",
        "created": 1700000000,
        "data": {"object": {}},
        "pending_webhooks": 1,
        "request": {"id": None, "idempotency_key": None},
    }


def test_webhook_503_when_secret_missing() -> None:
    """Sans STRIPE_WEBHOOK_SECRET, le endpoint doit refuser (503)."""
    from argos_ops.config import get_settings

    settings = get_settings()
    original = settings.stripe_webhook_secret
    settings.stripe_webhook_secret = None
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            assert response.status_code == 503
            assert "STRIPE_WEBHOOK_SECRET" in response.json()["detail"]
    finally:
        settings.stripe_webhook_secret = original


def test_webhook_400_when_signature_missing(client_with_secret: TestClient) -> None:
    response = client_with_secret.post("/api/stripe/webhook", content=b"{}")
    assert response.status_code == 400
    assert "stripe-signature" in response.json()["detail"]


def test_webhook_400_when_signature_invalid(client_with_secret: TestClient) -> None:
    payload = json.dumps(_build_event()).encode()
    response = client_with_secret.post(
        "/api/stripe/webhook",
        content=payload,
        headers={"stripe-signature": "t=1,v1=bogus_signature"},
    )
    assert response.status_code == 400


def test_webhook_200_on_valid_signature(client_with_secret: TestClient) -> None:
    """Signature valide → 200 + payload dispatché."""
    event = _build_event(event_id="evt_test_valid_001")
    payload = json.dumps(event).encode()
    sig = _stripe_signature_header(payload, WEBHOOK_SECRET)

    with patch.object(webhook_mod, "_dispatch") as mock_dispatch:
        response = client_with_secret.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sig},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["received"] is True
    assert body["duplicate"] is False
    assert body["event_id"] == "evt_test_valid_001"
    assert mock_dispatch.await_count == 1


def test_webhook_idempotency_dedupes_replays(client_with_secret: TestClient) -> None:
    """Même event_id rejoué → duplicate=True, dispatch n'est PAS rappelé."""
    event = _build_event(event_id="evt_test_dup_001")
    payload = json.dumps(event).encode()
    sig = _stripe_signature_header(payload, WEBHOOK_SECRET)

    with patch.object(webhook_mod, "_dispatch") as mock_dispatch:
        first = client_with_secret.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sig},
        )
        second = client_with_secret.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sig},
        )

    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert mock_dispatch.await_count == 1


def test_dedup_cache_evicts_oldest() -> None:
    """Le cache LRU doit éjecter l'event le plus ancien au-delà de _DEDUP_MAX."""
    webhook_mod._DEDUP_MAX = 3  # type: ignore[attr-defined]
    webhook_mod.reset_dedup_cache_for_tests()
    try:
        # Remplir au-delà de la cap.
        assert webhook_mod._mark_seen("a") is True
        assert webhook_mod._mark_seen("b") is True
        assert webhook_mod._mark_seen("c") is True
        assert webhook_mod._mark_seen("d") is True
        # Inspection directe : cache contient les 3 derniers (b,c,d), "a" éjecté.
        cache_keys = list(webhook_mod._RECENT_EVENT_IDS.keys())
        assert cache_keys == ["b", "c", "d"]
        assert "a" not in webhook_mod._RECENT_EVENT_IDS
    finally:
        webhook_mod._DEDUP_MAX = 1024  # type: ignore[attr-defined]
        webhook_mod.reset_dedup_cache_for_tests()
