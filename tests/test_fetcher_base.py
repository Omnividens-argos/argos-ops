"""Tests unitaires de :mod:`argos_ops.agents._fetcher_base` (P22.D).

Couvre la logique pure et l'I/O cache disque. Pas d'appel HTTP réel —
``fetch()`` est exercé via le cache (on pré-écrit un fichier cache puis
on vérifie le HIT).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from argos_ops.agents._fetcher_base import (
    DEFAULT_TTL_SECONDS,
    FetchResponse,
    _backoff,
    _cache_key,
    _host_of,
    _load_cached,
    _store_cache,
    clear_cache,
    fetch,
)


def test_cache_key_is_deterministic() -> None:
    a = _cache_key("GET", "https://acme.test/x", None)
    b = _cache_key("GET", "https://acme.test/x", None)
    c = _cache_key("GET", "https://acme.test/y", None)
    assert a == b
    assert a != c


def test_cache_key_includes_body() -> None:
    a = _cache_key("POST", "https://api.test/q", b'{"a":1}')
    b = _cache_key("POST", "https://api.test/q", b'{"a":2}')
    assert a != b


def test_cache_key_normalizes_method_case() -> None:
    assert _cache_key("get", "https://x.test/", None) == _cache_key(
        "GET", "https://x.test/", None
    )


def test_host_of_lowercases() -> None:
    assert _host_of("https://EXAMPLE.com/x") == "example.com"


def test_load_cached_returns_none_when_missing(tmp_path: Path) -> None:
    assert (
        _load_cached(
            tmp_path / "nope.json", ttl_seconds=3600, now=datetime.now(UTC)
        )
        is None
    )


def test_load_cached_returns_response_when_fresh(tmp_path: Path) -> None:
    now = datetime(2026, 5, 23, 12, tzinfo=UTC)
    payload = {
        "url": "https://x.test/",
        "status_code": 200,
        "body": "hello",
        "fetched_at": (now - timedelta(minutes=5)).isoformat(),
    }
    path = tmp_path / "x.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cached = _load_cached(path, ttl_seconds=3600, now=now)
    assert cached is not None
    assert cached.from_cache is True
    assert cached.body == "hello"


def test_load_cached_returns_none_when_stale(tmp_path: Path) -> None:
    now = datetime(2026, 5, 23, 12, tzinfo=UTC)
    payload = {
        "url": "https://x.test/",
        "status_code": 200,
        "body": "hello",
        "fetched_at": (now - timedelta(hours=48)).isoformat(),
    }
    path = tmp_path / "x.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _load_cached(path, ttl_seconds=DEFAULT_TTL_SECONDS, now=now) is None


def test_store_cache_creates_parent_and_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "deep" / "cache.json"
    response = FetchResponse(
        url="https://x.test/",
        status_code=200,
        body="payload",
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        from_cache=False,
    )
    _store_cache(target, response)
    assert target.exists()
    reloaded = _load_cached(target, ttl_seconds=3600, now=datetime(2026, 5, 23, tzinfo=UTC))
    assert reloaded is not None
    assert reloaded.body == "payload"


def test_backoff_is_bounded() -> None:
    # 30s plafond après amplification, plage [15..30] sur attempts élevés
    assert 0 < _backoff(1) <= 4
    assert _backoff(10) <= 30


def test_clear_cache_counts_and_removes(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "not_cache.txt").write_text("ignore", encoding="utf-8")
    assert clear_cache(tmp_path) == 2
    assert not (tmp_path / "a.json").exists()
    assert (tmp_path / "not_cache.txt").exists()


@pytest.mark.asyncio
async def test_fetch_returns_cache_hit_without_network(tmp_path: Path) -> None:
    """Si la valeur est cachée, ``fetch()`` ne touche pas le réseau."""
    url = "https://no-network.test/path"
    now = datetime(2026, 5, 23, 12, tzinfo=UTC)
    # Pré-remplit le cache à la main avec la même clé que celle calculée
    # par ``fetch``.
    from argos_ops.agents._fetcher_base import _cache_key, _cache_path

    key = _cache_key("GET", url, None)
    path = _cache_path(tmp_path, key)
    payload = {
        "url": url,
        "status_code": 200,
        "body": "cached body",
        "fetched_at": (now - timedelta(minutes=1)).isoformat(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    response = await fetch(
        url, service="test", cache_dir=tmp_path, now=now, rate_limit_seconds=0.0
    )
    assert response.from_cache is True
    assert response.body == "cached body"
