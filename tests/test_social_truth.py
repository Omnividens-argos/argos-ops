"""Tests unitaires de :mod:`argos_ops.social.truth_social` (Sprint contenu).

Truth Social = fork Mastodon (``POST /api/v1/statuses`` + Bearer). On mocke
``httpx.AsyncClient`` pour asserter l'endpoint, le payload et le header.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.social import truth_social
from argos_ops.social.truth_social import MAX_CHARS, TruthSocialClient


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
    monkeypatch.setattr(truth_social.httpx, "AsyncClient", _fake_client_factory(response, recorder))
    return recorder


def _live_client() -> TruthSocialClient:
    return TruthSocialClient(
        instance_url="https://truthsocial.com", access_token=SecretStr("ts-token")
    )


def test_is_live_requires_token() -> None:
    assert (
        TruthSocialClient(instance_url="https://truthsocial.com", access_token=None).is_live
        is False
    )
    assert (
        TruthSocialClient(
            instance_url="https://truthsocial.com", access_token=SecretStr("t")
        ).is_live
        is True
    )


def test_max_chars_is_500() -> None:
    assert MAX_CHARS == 500


async def test_post_shadow_without_token() -> None:
    result = await TruthSocialClient(
        instance_url="https://truthsocial.com", access_token=None
    ).post("coucou")
    assert result["status"] == "shadow"
    assert result["platform"] == "truth"
    assert result["url"] is None


async def test_post_dry_run_is_shadow_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(200, {"url": "x"}))
    result = await _live_client().post("texte", dry_run=True)
    assert result["status"] == "shadow"
    assert recorder == []


async def test_post_published_uses_statuses_endpoint_and_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _patch(
        monkeypatch, _FakeResponse(200, {"url": "https://truthsocial.com/@argos/1789"})
    )
    result = await _live_client().post("Security awareness, neutral.")

    assert result["status"] == "published"
    assert result["url"] == "https://truthsocial.com/@argos/1789"
    assert result["error"] is None

    call = recorder[0]
    assert call["url"] == "https://truthsocial.com/api/v1/statuses"
    assert call["json"] == {"status": "Security awareness, neutral.", "visibility": "public"}
    assert call["headers"]["Authorization"] == "Bearer ts-token"


async def test_post_published_without_url_yields_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(200, {}))
    result = await _live_client().post("hello")
    assert result["status"] == "published"
    assert result["url"] is None


async def test_post_http_error_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(500, {}))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 500"


async def test_post_http_error_surfaces_mastodon_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeResponse(401, {"error": "The access token is invalid"}))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 401: The access token is invalid"


async def test_post_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, httpx.ConnectError("boom"))
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "boom"


async def test_post_respects_custom_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _FakeResponse(200, {"url": "u"}))
    client = TruthSocialClient(instance_url="https://ts.test/", access_token=SecretStr("t"))
    await client.post("hi")
    # le trailing slash de l'instance ne doit pas doubler le séparateur.
    assert recorder[0]["url"] == "https://ts.test/api/v1/statuses"
