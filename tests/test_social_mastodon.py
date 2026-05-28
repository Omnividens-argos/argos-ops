"""Tests MastodonClient — shadow vs live, gestion erreurs."""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.social.mastodon import MastodonClient


@pytest.mark.asyncio
async def test_mastodon_shadow_without_token() -> None:
    """Sans access_token, le client doit retomber en shadow (aucun appel HTTP)."""
    client = MastodonClient(
        instance_url="https://infosec.exchange", access_token=None
    )
    assert client.is_live is False

    result = await client.post("hello world")
    assert result["status"] == "shadow"
    assert result["platform"] == "mastodon"
    assert result["url"] is None
    assert result["error"] is None


@pytest.mark.asyncio
async def test_mastodon_dry_run_forces_shadow() -> None:
    """dry_run=True doit forcer shadow même si un token est présent."""
    client = MastodonClient(
        instance_url="https://infosec.exchange",
        access_token=SecretStr("fake-token-do-not-use"),
    )
    assert client.is_live is True

    result = await client.post("hello", dry_run=True)
    assert result["status"] == "shadow"


@pytest.mark.asyncio
async def test_mastodon_published_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Réponse 200 → status=published + URL extraite du JSON."""
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json() -> dict[str, str]:
            return {"url": "https://infosec.exchange/@argos/12345"}

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, object], headers: dict[str, str]) -> _FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    client = MastodonClient(
        instance_url="https://infosec.exchange",
        access_token=SecretStr("real-looking-token"),
    )
    result = await client.post("toot test")

    assert result["status"] == "published"
    assert result["url"] == "https://infosec.exchange/@argos/12345"
    assert captured["url"] == "https://infosec.exchange/api/v1/statuses"
    assert captured["json"] == {"status": "toot test", "visibility": "public"}
    assert "Bearer real-looking-token" in captured["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_mastodon_failed_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Réponse 4xx → status=failed + error contient le code HTTP."""

    class _FakeResponse:
        status_code = 401
        text = "Unauthorized"

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    client = MastodonClient(
        instance_url="https://infosec.exchange",
        access_token=SecretStr("expired-token"),
    )
    result = await client.post("toot test")
    assert result["status"] == "failed"
    assert "HTTP 401" in str(result["error"])


@pytest.mark.asyncio
async def test_mastodon_failed_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Erreur réseau (DNS, timeout) → status=failed + error contient l'exception."""

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("DNS resolution failed")

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    client = MastodonClient(
        instance_url="https://infosec.exchange",
        access_token=SecretStr("tok"),
    )
    result = await client.post("hi")
    assert result["status"] == "failed"
    assert "DNS resolution failed" in str(result["error"])
