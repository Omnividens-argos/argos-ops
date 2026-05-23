"""Helper partagé des fetcher bots Argos Ops (P22.D Tech finition + Veille).

Tous les watchers qui appellent une **source externe** (HTTP, DNS, RSS,
scraping HTML public) passent par ce module pour :

1. Réutiliser un cache disque 24 h (anti-hammering — D-017 local-first
   impose qu'on n'agresse jamais un site tiers, même API publique)
2. Gérer le retry exponentiel sur les erreurs réseau transitoires
3. Marquer un User-Agent explicite ``Argos-Ops/<service>`` pour que
   les sites scrapés sachent qui les visite et puissent nous contacter
4. Respecter un rate-limit minimal entre 2 calls sur le même host

Le cache vit dans ``data/_fetcher_cache/`` (gitignored sauf
``.gitkeep``). Une entrée = ``sha256(method|url|body)`` → fichier
``.json`` avec ``fetched_at`` + ``status_code`` + ``body`` (text) +
``headers`` minimaux. La TTL par défaut est 24 h.

Ce module ne supporte **que** des GET et POST sur des sources publiques.
Toute auth / cookie sensible doit rester dans son agent (ex :
``DependencyAuditor`` qui POST sur OSV.dev sans cache car les CVE
peuvent évoluer dans la journée — il ne consomme donc pas ce helper).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE Sprint 4 +
§ 8 Veille Sprint 6.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
from loguru import logger

from argos_ops.config import REPO_ROOT

DEFAULT_CACHE_DIR: Final[Path] = REPO_ROOT / "data" / "_fetcher_cache"
DEFAULT_TTL_SECONDS: Final[float] = 24 * 3600
DEFAULT_TIMEOUT_SECONDS: Final[float] = 15.0
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RATE_LIMIT_SECONDS: Final[float] = 1.0  # entre 2 calls sur le même host

USER_AGENT_TEMPLATE: Final[str] = (
    "Argos-Ops/{service} (+https://omnividens.fr/contact)"
)


@dataclass(frozen=True)
class FetchResponse:
    """Réponse d'un fetch — minimaliste, pickle-friendly via JSON."""

    url: str
    status_code: int
    body: str
    fetched_at: datetime
    from_cache: bool


def _cache_key(method: str, url: str, body: bytes | None) -> str:
    """``sha256(method|url|body)`` → nom de fichier cache."""
    digest = hashlib.sha256()
    digest.update(method.upper().encode("utf-8"))
    digest.update(b"\x00")
    digest.update(url.encode("utf-8"))
    digest.update(b"\x00")
    if body:
        digest.update(body)
    return digest.hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def _load_cached(
    path: Path, *, ttl_seconds: float, now: datetime
) -> FetchResponse | None:
    """Retourne la réponse cachée si elle est plus récente que la TTL."""
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(raw["fetched_at"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning(f"fetcher-cache corrompu ({path.name}): {exc}")
        return None
    if (now - fetched_at) > timedelta(seconds=ttl_seconds):
        return None
    return FetchResponse(
        url=raw["url"],
        status_code=raw["status_code"],
        body=raw["body"],
        fetched_at=fetched_at,
        from_cache=True,
    )


def _store_cache(path: Path, response: FetchResponse) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "url": response.url,
        "status_code": response.status_code,
        "body": response.body,
        "fetched_at": response.fetched_at.isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# Rate limit par host — un dict en module (process-local) suffit
# =============================================================================
_LAST_CALL_PER_HOST: dict[str, float] = {}


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower()


async def _respect_rate_limit(host: str, *, min_interval: float) -> None:
    """Sleep si on a frappé ce host récemment (instance process-local)."""
    if min_interval <= 0:
        return
    last = _LAST_CALL_PER_HOST.get(host)
    if last is None:
        _LAST_CALL_PER_HOST[host] = time.monotonic()
        return
    elapsed = time.monotonic() - last
    if elapsed < min_interval:
        await asyncio.sleep(min_interval - elapsed)
    _LAST_CALL_PER_HOST[host] = time.monotonic()


# =============================================================================
# Public API
# =============================================================================
async def fetch(
    url: str,
    *,
    service: str,
    method: str = "GET",
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
    bypass_cache: bool = False,
    now: datetime | None = None,
) -> FetchResponse:
    """Fetch une URL publique avec cache disque + retry + rate limit.

    Args:
        url: URL absolue (http/https).
        service: nom court de l'agent appelant, injecté dans le
            User-Agent (ex : ``"competitor-watcher"``).
        method: ``GET`` ou ``POST``.
        body: corps brut pour POST (sera hashé dans la clé cache).
        headers: headers additionnels (le User-Agent est forcé).
        ttl_seconds: durée de validité du cache (24 h par défaut).
        bypass_cache: ignore le cache existant (mais y écrit la fresh).

    Returns:
        Un :class:`FetchResponse`. ``from_cache=True`` si la valeur vient
        du disque.

    Raises:
        httpx.HTTPError: si les ``max_retries`` échouent tous.
        httpx.HTTPStatusError: sur 4xx/5xx après retry (5xx retryable).
    """
    now = now or datetime.now(UTC)
    key = _cache_key(method, url, body)
    path = _cache_path(cache_dir, key)

    if not bypass_cache:
        cached = _load_cached(path, ttl_seconds=ttl_seconds, now=now)
        if cached is not None:
            logger.debug(f"fetcher-cache HIT {service} {url}")
            return cached

    await _respect_rate_limit(_host_of(url), min_interval=rate_limit_seconds)

    final_headers = {"User-Agent": USER_AGENT_TEMPLATE.format(service=service)}
    if headers:
        final_headers.update(headers)

    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.request(
                    method, url, content=body, headers=final_headers
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning(
                    f"fetcher {service} {method} {url} attempt {attempt}/"
                    f"{max_retries} failed: {type(exc).__name__}: {exc}"
                )
                if attempt == max_retries:
                    raise
                await asyncio.sleep(_backoff(attempt))
                continue

            if response.status_code >= 500 and attempt < max_retries:
                logger.warning(
                    f"fetcher {service} {url} got {response.status_code}, "
                    f"retry {attempt}/{max_retries}"
                )
                await asyncio.sleep(_backoff(attempt))
                continue

            response.raise_for_status()
            fresh = FetchResponse(
                url=url,
                status_code=response.status_code,
                body=response.text,
                fetched_at=now,
                from_cache=False,
            )
            _store_cache(path, fresh)
            return fresh

    # Sécurité — devrait être inatteignable car on raise dans la boucle
    raise last_exc or RuntimeError(f"fetcher: aucune réponse pour {url}")


def _backoff(attempt: int) -> float:
    """Exponentiel + jitter : ``2^attempt * (0.5..1.0)`` plafonné à 30 s."""
    base = min(2.0**attempt, 30.0)
    return base * (0.5 + random.random() * 0.5)


def clear_cache(cache_dir: Path = DEFAULT_CACHE_DIR) -> int:
    """Supprime toutes les entrées cachées. Retourne le nombre supprimé."""
    if not cache_dir.exists():
        return 0
    count = 0
    for entry in cache_dir.glob("*.json"):
        entry.unlink()
        count += 1
    return count


__all__ = [
    "DEFAULT_CACHE_DIR",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RATE_LIMIT_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_TTL_SECONDS",
    "USER_AGENT_TEMPLATE",
    "FetchResponse",
    "clear_cache",
    "fetch",
]
