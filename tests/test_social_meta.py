"""Tests unitaires de :mod:`argos_ops.social.meta` (Sprint contenu).

On mocke ``httpx.AsyncClient`` avec un faux client qui enregistre la
requête (URL + form data) pour asserter que le connecteur appelle le bon
endpoint Graph API et envoie le token dans le corps (pas dans l'URL).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.social import meta
from argos_ops.social.meta import MetaClient


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._json


def _fake_client_factory(
    response: _FakeResponse | Exception,
    recorder: list[dict[str, Any]],
) -> type:
    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            data: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None,
        ) -> _FakeResponse:
            recorder.append({"url": url, "data": data, "json": json})
            if isinstance(response, Exception):
                raise response
            return response

    return _FakeAsyncClient


def _patch(
    monkeypatch: pytest.MonkeyPatch, response: _FakeResponse | Exception
) -> list[dict[str, Any]]:
    recorder: list[dict[str, Any]] = []
    monkeypatch.setattr(meta.httpx, "AsyncClient", _fake_client_factory(response, recorder))
    return recorder


def _live_client() -> MetaClient:
    return MetaClient(
        page_id="123456789",
        page_access_token=SecretStr("EAA-token-xyz"),
        api_version="v21.0",
    )


def test_is_live_requires_page_id_and_token() -> None:
    assert MetaClient(page_id=None, page_access_token=SecretStr("x")).is_live is False
    assert MetaClient(page_id="1", page_access_token=None).is_live is False
    assert MetaClient(page_id="1", page_access_token=SecretStr("x")).is_live is True


async def test_post_shadow_without_credentials() -> None:
    result = await MetaClient(page_id=None, page_access_token=None).post("coucou")
    assert result["status"] == "shadow"
    assert result["platform"] == "meta"
    assert result["url"] is None


async def test_post_dry_run_is_shadow_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(200, {"id": "1_2"}))
    result = await _live_client().post("texte", dry_run=True)
    assert result["status"] == "shadow"
    assert recorder == []


async def test_post_published_uses_feed_endpoint_and_body_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(200, {"id": "123456789_987654321"}))
    result = await _live_client().post("Votre site est-il bien protégé ?")

    assert result["status"] == "published"
    assert result["url"] == "https://www.facebook.com/123456789_987654321"
    assert result["error"] is None

    call = recorder[0]
    assert call["url"] == "https://graph.facebook.com/v21.0/123456789/feed"
    # token dans le BODY (form), jamais dans l'URL.
    assert "EAA-token-xyz" not in call["url"]
    assert call["data"]["access_token"] == "EAA-token-xyz"
    assert call["data"]["message"] == "Votre site est-il bien protégé ?"


async def test_post_published_without_id_yields_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(200, {}))
    result = await _live_client().post("hello")
    assert result["status"] == "published"
    assert result["url"] is None


async def test_post_http_error_without_error_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(400, {}, text="bad request"))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 400"


async def test_post_http_error_surfaces_graph_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        _FakeResponse(400, {"error": {"message": "Invalid OAuth access token", "code": 190}}),
    )
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 400: Invalid OAuth access token (code 190)"


async def test_post_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, httpx.ConnectError("boom"))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "boom"


async def test_post_respects_custom_api_version(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(200, {"id": "1_2"}))
    client = MetaClient(page_id="42", page_access_token=SecretStr("EAAx"), api_version="v23.0")
    await client.post("hi")
    assert recorder[0]["url"] == "https://graph.facebook.com/v23.0/42/feed"
