"""Tests unitaires de :mod:`argos_ops.integrations.umami` (INFRA-02).

On mocke ``httpx.AsyncClient`` avec un faux client routant chaque requête
(``post`` login + ``get`` stats/metrics) via un *handler* contrôlé par le
test, et un *recorder* pour asserter URLs / params / header Authorization.
Aucun appel réseau réel. Le flux nominal couvre : login → liste d'URLs →
stats par URL (+ conversions optionnelles), et les calculs dérivés
(bounce_rate, avg_time_seconds).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.integrations import umami
from argos_ops.integrations.umami import UmamiClient, UmamiPageMetric, _stat_value

# --------------------------------------------------------------------------
# Faux httpx.AsyncClient (post + get)
# --------------------------------------------------------------------------

Handler = Callable[[str, str, "dict[str, Any] | None", "dict[str, Any] | None"], "_FakeResponse"]


class _FakeResponse:
    def __init__(
        self, status_code: int, json_data: Any = None, text: str = "", raise_json: bool = False
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self._raise_json = raise_json

    def json(self) -> Any:
        if self._raise_json:
            # Simule un corps 200 non-JSON (httpx lève json.JSONDecodeError,
            # sous-classe de ValueError).
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._json


def _make_client(handler: Handler, recorder: list[dict[str, Any]]) -> type:
    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

        async def post(
            self, url: str, *, json: dict[str, Any] | None = None, headers: Any = None
        ) -> _FakeResponse:
            recorder.append({"method": "POST", "url": url, "json": json, "headers": headers})
            return handler("POST", url, None, json)

        async def get(
            self, url: str, *, params: dict[str, Any] | None = None, headers: Any = None
        ) -> _FakeResponse:
            recorder.append({"method": "GET", "url": url, "params": params, "headers": headers})
            return handler("GET", url, params, None)

    return _FakeAsyncClient


def _patch(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> list[dict[str, Any]]:
    recorder: list[dict[str, Any]] = []
    monkeypatch.setattr(umami.httpx, "AsyncClient", _make_client(handler, recorder))
    return recorder


def _live_client(conversion_event: str | None = None) -> UmamiClient:
    return UmamiClient(
        base_url="https://analytics.omnividens.fr",
        username="admin",
        password=SecretStr("s3cret"),
        website_id="web-123",
        conversion_event=conversion_event,
    )


# Stats canoniques par page (format Umami v3 : valeurs à plat).
_STATS = {
    "/": {"pageviews": 500, "visits": 400, "bounces": 120, "totaltime": 8000},
    "/pricing": {"pageviews": 200, "visits": 150, "bounces": 130, "totaltime": 1500},
}


def _nominal_handler(
    method: str, url: str, params: dict[str, Any] | None, json: dict[str, Any] | None
) -> _FakeResponse:
    if url.endswith("/api/auth/login"):
        return _FakeResponse(200, {"token": "JWT-XYZ"})
    p = params or {}
    if url.endswith("/metrics") and p.get("type") == "path":
        return _FakeResponse(200, [{"x": "/", "y": 500}, {"x": "/pricing", "y": 200}])
    if url.endswith("/metrics") and p.get("type") == "event":
        page = p.get("path")
        events = {"/": [{"x": "demande-demo", "y": 8}], "/pricing": [{"x": "demande-demo", "y": 3}]}
        return _FakeResponse(200, events.get(page, []))
    if url.endswith("/stats"):
        return _FakeResponse(200, _STATS[str(p.get("path"))])
    raise AssertionError(f"requête inattendue {method} {url} params={params}")


# --------------------------------------------------------------------------
# is_configured / _stat_value
# --------------------------------------------------------------------------


def test_is_configured_requires_all_four() -> None:
    assert _live_client().is_configured is True
    assert UmamiClient(None, "u", SecretStr("p"), "w").is_configured is False
    assert UmamiClient("b", None, SecretStr("p"), "w").is_configured is False
    assert UmamiClient("b", "u", None, "w").is_configured is False
    assert UmamiClient("b", "u", SecretStr("p"), None).is_configured is False


def test_stat_value_tolerates_both_formats() -> None:
    assert _stat_value({"pageviews": {"value": 42}}, "pageviews") == 42.0
    assert _stat_value({"pageviews": 42}, "pageviews") == 42.0  # format plat
    assert _stat_value({}, "pageviews") == 0.0  # clé absente
    assert _stat_value({"pageviews": {"value": None}}, "pageviews") == 0.0
    assert _stat_value({"pageviews": {"value": "nan"}}, "pageviews") == 0.0


# --------------------------------------------------------------------------
# Shadow
# --------------------------------------------------------------------------


async def test_fetch_shadow_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _nominal_handler)
    client = UmamiClient(base_url=None, username=None, password=None, website_id=None)
    metrics = await client.fetch_landing_metrics()
    assert metrics == []
    assert recorder == []  # aucun appel réseau en shadow


# --------------------------------------------------------------------------
# Flux nominal
# --------------------------------------------------------------------------


async def test_fetch_nominal_builds_metrics_with_derived_math(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, _nominal_handler)
    metrics = await _live_client().fetch_landing_metrics()
    assert [m.page for m in metrics] == ["/", "/pricing"]

    home = metrics[0]
    assert home.visits == 400
    assert home.bounce_rate == 0.30  # 120/400
    assert home.avg_time_seconds == 20.0  # 8000/400
    assert home.conversions == 0  # pas de conversion_event configuré

    pricing = metrics[1]
    assert pricing.visits == 150
    assert pricing.bounce_rate == 0.8667  # 130/150 arrondi 4
    assert pricing.avg_time_seconds == 10.0  # 1500/150


async def test_fetch_counts_conversions_from_event(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _nominal_handler)
    metrics = await _live_client(conversion_event="demande-demo").fetch_landing_metrics()
    assert metrics[0].conversions == 8  # "/"
    assert metrics[1].conversions == 3  # "/pricing"


async def test_fetch_sends_bearer_token_and_ms_window(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch(monkeypatch, _nominal_handler)
    await _live_client().fetch_landing_metrics(days=30)
    # Login posté avec les identifiants
    login = next(c for c in recorder if c["url"].endswith("/api/auth/login"))
    assert login["json"] == {"username": "admin", "password": "s3cret"}
    # Tous les GET portent le Bearer issu du login
    gets = [c for c in recorder if c["method"] == "GET"]
    assert gets and all(c["headers"]["Authorization"] == "Bearer JWT-XYZ" for c in gets)
    # Fenêtre en millisecondes (epoch ms ~ 1e12), end > start
    stats_call = next(c for c in gets if c["url"].endswith("/stats"))
    start, end = stats_call["params"]["startAt"], stats_call["params"]["endAt"]
    assert isinstance(start, int) and isinstance(end, int)
    assert end > start
    assert start > 1_000_000_000_000  # bien des millisecondes, pas des secondes


# --------------------------------------------------------------------------
# Échecs → [] (résilience, le bot gère le fallback)
# --------------------------------------------------------------------------


async def test_fetch_login_http_error_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        if url.endswith("/api/auth/login"):
            return _FakeResponse(401, {}, text="bad credentials")
        raise AssertionError("ne doit pas aller plus loin que le login")

    recorder = _patch(monkeypatch, handler)
    metrics = await _live_client().fetch_landing_metrics()
    assert metrics == []
    assert all("/metrics" not in c["url"] for c in recorder)  # court-circuit


async def test_fetch_login_network_error_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        raise httpx.ConnectError("boom")

    _patch(monkeypatch, handler)
    assert await _live_client().fetch_landing_metrics() == []


async def test_fetch_login_missing_token_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        return _FakeResponse(200, {"user": {"id": 1}})  # pas de "token"

    _patch(monkeypatch, handler)
    assert await _live_client().fetch_landing_metrics() == []


async def test_fetch_skips_page_when_stats_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        p = params or {}
        if url.endswith("/api/auth/login"):
            return _FakeResponse(200, {"token": "T"})
        if url.endswith("/metrics") and p.get("type") == "path":
            return _FakeResponse(200, [{"x": "/", "y": 10}, {"x": "/down", "y": 5}])
        if url.endswith("/stats") and p.get("path") == "/down":
            return _FakeResponse(500, {}, text="boom")  # cette page échoue
        if url.endswith("/stats"):
            return _FakeResponse(200, _STATS["/"])
        raise AssertionError(f"inattendu {url}")

    _patch(monkeypatch, handler)
    metrics = await _live_client().fetch_landing_metrics()
    assert [m.page for m in metrics] == ["/"]  # "/down" sauté, pas de crash


async def test_fetch_url_metrics_non_list_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        if url.endswith("/api/auth/login"):
            return _FakeResponse(200, {"token": "T"})
        if url.endswith("/metrics"):
            return _FakeResponse(500, {}, text="boom")  # liste d'URLs indispo
        raise AssertionError(f"inattendu {url}")

    _patch(monkeypatch, handler)
    assert await _live_client().fetch_landing_metrics() == []


async def test_fetch_login_non_json_body_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Login HTTP 200 mais corps non-JSON (proxy renvoie du HTML) : le contrat
    # « aucune exception ne remonte » doit tenir → [].
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        if url.endswith("/api/auth/login"):
            return _FakeResponse(200, raise_json=True, text="<html>502</html>")
        raise AssertionError("ne doit pas dépasser le login")

    _patch(monkeypatch, handler)
    assert await _live_client().fetch_landing_metrics() == []


async def test_fetch_skips_page_when_stats_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, params: Any, json: Any) -> _FakeResponse:
        p = params or {}
        if url.endswith("/api/auth/login"):
            return _FakeResponse(200, {"token": "T"})
        if url.endswith("/metrics") and p.get("type") == "path":
            return _FakeResponse(200, [{"x": "/", "y": 10}, {"x": "/bad", "y": 5}])
        if url.endswith("/stats") and p.get("path") == "/bad":
            return _FakeResponse(200, raise_json=True, text="<html>oops</html>")
        if url.endswith("/stats"):
            return _FakeResponse(200, _STATS["/"])
        raise AssertionError(f"inattendu {url}")

    _patch(monkeypatch, handler)
    metrics = await _live_client().fetch_landing_metrics()
    assert [m.page for m in metrics] == ["/"]  # "/bad" sauté sans crash


def test_dto_fields() -> None:
    m = UmamiPageMetric(page="/", visits=10, conversions=1, bounce_rate=0.5, avg_time_seconds=30.0)
    assert (m.page, m.visits, m.conversions, m.bounce_rate, m.avg_time_seconds) == (
        "/",
        10,
        1,
        0.5,
        30.0,
    )
