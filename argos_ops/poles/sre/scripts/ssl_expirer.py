"""``SslExpirerScript`` — expiration des certificats TLS (archi v2, S8).

Réutilise ``data/poles/sre/uptime/endpoints.yaml`` : pour chaque endpoint HTTPS,
fait un handshake TLS et lit l'expiration du certificat. Vert > 30 j, jaune
< 30 j (à renouveler), rouge < 7 j ou erreur de handshake. Le fetcher de cert est
injectable (tests hermétiques). Aucun endpoint HTTPS ⇒ vert.
"""

from __future__ import annotations

import asyncio
import socket
import ssl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst
from argos_ops.poles.sre.scripts.uptime_monitor import EndpointConfig, load_endpoints

WARN_DAYS = 30
CRITICAL_DAYS = 7
SSL_TIMEOUT_SECONDS = 5.0
_CERT_DATE_FMT = "%b %d %H:%M:%S %Y %Z"

_STATUS_SEVERITY: dict[str, Severity] = {
    "ok": "green",
    "expiring_soon": "yellow",
    "critical": "red",
    "error": "red",
}


@dataclass(frozen=True)
class SslCheckResult:
    """Résultat de la vérification d'un certificat."""

    name: str
    host: str
    port: int
    expires_at: datetime | None
    days_remaining: float | None
    status: str  # ok | expiring_soon | critical | error
    error: str | None


# Fetcher : (host, port) → expiration du cert (ou None si introuvable).
CertFetcher = Callable[[str, int], Awaitable[datetime | None]]


def _host_port(url: str) -> tuple[str, int] | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return parsed.hostname, parsed.port or 443


async def real_cert_fetcher(host: str, port: int) -> datetime | None:
    """Handshake TLS bloquant déporté dans un thread (cf. asyncio.to_thread)."""

    def _fetch() -> datetime | None:
        ctx = ssl.create_default_context()
        with (
            socket.create_connection((host, port), timeout=SSL_TIMEOUT_SECONDS) as sock,
            ctx.wrap_socket(sock, server_hostname=host) as ssock,
        ):
            cert = ssock.getpeercert()
        not_after = cert.get("notAfter") if cert else None
        if not not_after:
            return None
        return datetime.strptime(str(not_after), _CERT_DATE_FMT).replace(tzinfo=UTC)

    return await asyncio.to_thread(_fetch)


def classify_days(days: float) -> str:
    if days < CRITICAL_DAYS:
        return "critical"
    if days < WARN_DAYS:
        return "expiring_soon"
    return "ok"


async def check_endpoint(
    endpoint: EndpointConfig, fetcher: CertFetcher, *, now: datetime | None = None
) -> SslCheckResult | None:
    """Vérifie un endpoint HTTPS. ``None`` si l'endpoint n'est pas HTTPS."""
    hp = _host_port(endpoint.url)
    if hp is None:
        return None
    host, port = hp
    moment = now or datetime.now(UTC)
    try:
        expires_at = await fetcher(host, port)
    except (OSError, ssl.SSLError, ValueError) as exc:
        return SslCheckResult(endpoint.name, host, port, None, None, "error", str(exc))
    if expires_at is None:
        return SslCheckResult(endpoint.name, host, port, None, None, "error", "cert illisible")
    days = (expires_at - moment).total_seconds() / 86400.0
    return SslCheckResult(endpoint.name, host, port, expires_at, days, classify_days(days), None)


def build_report(results: list[SslCheckResult]) -> SreReport:
    if not results:
        return SreReport("green", "Aucun endpoint HTTPS à vérifier.")
    counts = {k: sum(1 for r in results if r.status == k) for k in _STATUS_SEVERITY}
    severity = worst(*(_STATUS_SEVERITY[r.status] for r in results))
    summary = (
        f"{counts['ok']} ok · {counts['expiring_soon']} bientôt · "
        f"{counts['critical']} critique(s) · {counts['error']} erreur(s)"
    )
    detail = "\n".join(
        f"- {r.name} ({r.host}) : {r.status}"
        + (f" — {r.days_remaining:.1f} j" if r.days_remaining is not None else "")
        + (f" — {r.error}" if r.error else "")
        for r in results
        if r.status != "ok"
    )
    return SreReport(severity, summary, detail)


class SslExpirerScript(BaseSreScript):
    """Vérifie l'expiration des certificats TLS des endpoints HTTPS."""

    name = "ssl_expirer"

    def __init__(self, *, poles_root: Path = POLES_DIR, fetcher: CertFetcher | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._fetcher = fetcher or real_cert_fetcher

    async def check(self) -> SreReport:
        results: list[SslCheckResult] = []
        for ep in load_endpoints(poles_root=self.poles_root):
            res = await check_endpoint(ep, self._fetcher)
            if res is not None:
                results.append(res)
        if not results:
            logger.debug("ssl_expirer — aucun endpoint HTTPS")
        return build_report(results)


__all__ = [
    "CRITICAL_DAYS",
    "WARN_DAYS",
    "CertFetcher",
    "SslCheckResult",
    "SslExpirerScript",
    "build_report",
    "check_endpoint",
    "classify_days",
    "real_cert_fetcher",
]
