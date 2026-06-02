"""Tests unitaires de :mod:`argos_ops.social.twitter` (Sprint contenu).

On mocke ``httpx.AsyncClient`` avec un faux client qui enregistre la requête
(URL + JSON body + headers) pour asserter que le connecteur appelle bien
``POST /2/tweets`` avec le token en Bearer et le texte en JSON.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.social import twitter
from argos_ops.social.twitter import MAX_CHARS, TwitterClient


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
            json: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
        ) -> _FakeResponse:
            recorder.append({"url": url, "json": json, "headers": headers})
            if isinstance(response, Exception):
                raise response
            return response

    return _FakeAsyncClient


def _patch(
    monkeypatch: pytest.MonkeyPatch, response: _FakeResponse | Exception
) -> list[dict[str, Any]]:
    recorder: list[dict[str, Any]] = []
    monkeypatch.setattr(twitter.httpx, "AsyncClient", _fake_client_factory(response, recorder))
    return recorder


def _live_client() -> TwitterClient:
    return TwitterClient(access_token=SecretStr("x-user-token"))


def test_is_live_requires_token() -> None:
    assert TwitterClient(access_token=None).is_live is False
    assert TwitterClient(access_token=SecretStr("t")).is_live is True


def test_max_chars_is_280() -> None:
    assert MAX_CHARS == 280


async def test_post_shadow_without_token() -> None:
    result = await TwitterClient(access_token=None).post("coucou")
    assert result["status"] == "shadow"
    assert result["platform"] == "x"
    assert result["url"] is None


async def test_post_dry_run_is_shadow_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(201, {"data": {"id": "1"}}))
    result = await _live_client().post("texte", dry_run=True)
    assert result["status"] == "shadow"
    assert recorder == []


async def test_post_published_201_uses_tweets_endpoint_and_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # X v2 renvoie 201 Created en succès.
    recorder = _patch(monkeypatch, _FakeResponse(201, {"data": {"id": "1789012345", "text": "ok"}}))
    result = await _live_client().post("On scanne, vous corrigez.")

    assert result["status"] == "published"
    assert result["url"] == "https://x.com/i/web/status/1789012345"
    assert result["error"] is None

    call = recorder[0]
    assert call["url"] == "https://api.twitter.com/2/tweets"
    assert call["json"] == {"text": "On scanne, vous corrigez."}
    assert call["headers"]["Authorization"] == "Bearer x-user-token"


async def test_post_published_without_id_yields_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(201, {"data": {}}))
    result = await _live_client().post("hello")
    assert result["status"] == "published"
    assert result["url"] is None


async def test_post_http_error_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(403, {}))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 403"


async def test_post_http_error_surfaces_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        _FakeResponse(401, {"title": "Unauthorized", "detail": "Unauthenticated", "status": 401}),
    )
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 401: Unauthenticated"


async def test_post_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, httpx.ConnectError("boom"))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "boom"


async def test_post_respects_custom_api_base(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(201, {"data": {"id": "1"}}))
    client = TwitterClient(access_token=SecretStr("t"), api_base="https://api.x.test")
    await client.post("hi")
    assert recorder[0]["url"] == "https://api.x.test/2/tweets"
