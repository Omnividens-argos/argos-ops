"""Tests LinkedInClient — perso vs page, target=auto, shadow, erreurs."""

from __future__ import annotations

from typing import ClassVar

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.social.linkedin import LinkedInClient


def _make_client(
    *,
    personal: bool = False,
    page: bool = False,
) -> LinkedInClient:
    return LinkedInClient(
        personal_token=SecretStr("tok-perso") if personal else None,
        personal_urn="urn:li:person:abc" if personal else None,
        page_token=SecretStr("tok-page") if page else None,
        page_urn="urn:li:organization:42" if page else None,
    )


def test_is_live_flags() -> None:
    empty = _make_client()
    assert empty.is_live is False
    assert empty.personal_is_live is False
    assert empty.page_is_live is False

    perso_only = _make_client(personal=True)
    assert perso_only.is_live is True
    assert perso_only.personal_is_live is True
    assert perso_only.page_is_live is False

    page_only = _make_client(page=True)
    assert page_only.is_live is True
    assert page_only.personal_is_live is False
    assert page_only.page_is_live is True


def test_resolve_target_auto_prefers_page() -> None:
    """target=auto doit préférer Page si dispo (audience brandée)."""
    both = _make_client(personal=True, page=True)
    assert both._resolve_target("auto") == "page"

    perso = _make_client(personal=True)
    assert perso._resolve_target("auto") == "personal"

    empty = _make_client()
    assert empty._resolve_target("auto") == "personal"  # fallback


@pytest.mark.asyncio
async def test_shadow_when_target_not_configured() -> None:
    """target=personal mais aucun token perso → shadow."""
    client = _make_client(page=True)  # seulement page
    result = await client.post("hello", target="personal")
    assert result["status"] == "shadow"
    assert result["target"] == "personal"


@pytest.mark.asyncio
async def test_dry_run_forces_shadow() -> None:
    client = _make_client(personal=True, page=True)
    result = await client.post("hello", dry_run=True, target="page")
    assert result["status"] == "shadow"
    assert result["target"] == "page"


@pytest.mark.asyncio
async def test_post_personal_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """En target=personal, l'author du payload doit être urn:li:person:."""
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 201
        headers: ClassVar[dict[str, str]] = {"x-restli-id": "urn:li:share:7777"}
        text = ""

        @staticmethod
        def json() -> dict[str, str]:
            return {"id": "urn:li:share:7777"}

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

    client = _make_client(personal=True, page=True)
    result = await client.post("hello perso", target="personal")

    assert result["status"] == "published"
    assert result["target"] == "personal"
    assert result["url"] == "https://www.linkedin.com/feed/update/urn:li:share:7777"
    assert captured["url"] == "https://api.linkedin.com/v2/ugcPosts"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["author"] == "urn:li:person:abc"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert "Bearer tok-perso" in headers["Authorization"]


@pytest.mark.asyncio
async def test_post_page_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """En target=page, l'author doit être urn:li:organization: et le token Page."""
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 201
        headers: ClassVar[dict[str, str]] = {"x-restli-id": "urn:li:share:9999"}
        text = ""

        @staticmethod
        def json() -> dict[str, str]:
            return {"id": "urn:li:share:9999"}

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict[str, object], headers: dict[str, str]) -> _FakeResponse:
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    client = _make_client(personal=True, page=True)
    result = await client.post("hello page", target="page")

    assert result["status"] == "published"
    assert result["target"] == "page"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["author"] == "urn:li:organization:42"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert "Bearer tok-page" in headers["Authorization"]


@pytest.mark.asyncio
async def test_failed_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResponse:
        status_code = 403
        headers: ClassVar[dict[str, str]] = {}
        text = "Forbidden"

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

    client = _make_client(personal=True)
    result = await client.post("hi", target="personal")
    assert result["status"] == "failed"
    assert "HTTP 403" in str(result["error"])
