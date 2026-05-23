"""SSLExpirer — IT Security de la flotte (P22.C Tech/SRE Sprint 4).

Vérifie la date d'expiration des certificats SSL des endpoints HTTPS
déclarés dans ``data/uptime/endpoints.yaml`` (même fichier que
UptimeMonitor, on évite la duplication de catalogue). Alerte Discord
si un certificat expire dans moins de :data:`WARN_DAYS` (30 j par défaut).

Sans dépendance externe : on utilise ``ssl`` + ``socket`` de la stdlib
pour établir une connexion TLS et lire ``getpeercert()``.

Politique anti-spam :
- **Silence** Discord si tous les certs sont valides > 30 j
- **Embed jaune** si ≥1 cert expire dans 7-30 j
- **Embed rouge** si ≥1 cert expire dans < 7 j ou est déjà expiré

Cet agent n'a pas de slash command — il tourne via Task Scheduler
mensuel (``argos-ops-ssl-expirer``).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.agents.uptime_monitor import DEFAULT_ENDPOINTS_PATH, load_endpoints
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

SslStatus = Literal["ok", "expiring_soon", "critical", "error"]

WARN_DAYS = 30
CRITICAL_DAYS = 7
SSL_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SslCheckResult:
    """Résultat du check SSL d'un endpoint."""

    name: str
    host: str
    port: int
    expires_at: datetime | None
    days_remaining: float | None
    status: SslStatus
    error: str | None


@dataclass(frozen=True)
class SslReport:
    """Résultat agrégé du run SSLExpirer."""

    results: list[SslCheckResult]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Check TLS
# =============================================================================
def _extract_host_port(url: str) -> tuple[str, int] | None:
    """``"https://omnividens.fr/"`` → ``("omnividens.fr", 443)``.

    Renvoie ``None`` si l'URL n'est pas HTTPS (HTTP pur n'a pas de cert
    à vérifier, on skip silencieusement).
    """
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return parsed.hostname, parsed.port or 443


def _parse_cert_expiry(cert: Mapping[str, object]) -> datetime | None:
    """Parse ``cert["notAfter"]`` au format ``"%b %d %H:%M:%S %Y %Z"``."""
    not_after = cert.get("notAfter")
    if not isinstance(not_after, str) or not not_after:
        return None
    expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
    return expires.replace(tzinfo=UTC)


def _check_one(
    name: str, host: str, port: int, *, now: datetime, timeout: float = SSL_TIMEOUT_SECONDS
) -> SslCheckResult:
    """Établit une connexion TLS et lit le cert. Sync (stdlib ssl)."""
    context = ssl.create_default_context()
    try:
        with (
            socket.create_connection((host, port), timeout=timeout) as sock,
            context.wrap_socket(sock, server_hostname=host) as ssock,
        ):
            cert = ssock.getpeercert()
    except Exception as exc:
        return SslCheckResult(
            name=name,
            host=host,
            port=port,
            expires_at=None,
            days_remaining=None,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )

    expires_at = _parse_cert_expiry(cert or {})
    if expires_at is None:
        return SslCheckResult(
            name=name,
            host=host,
            port=port,
            expires_at=None,
            days_remaining=None,
            status="error",
            error="notAfter introuvable dans le cert",
        )

    days_remaining = (expires_at - now).total_seconds() / 86400.0
    status: SslStatus
    if days_remaining < CRITICAL_DAYS:
        status = "critical"
    elif days_remaining < WARN_DAYS:
        status = "expiring_soon"
    else:
        status = "ok"
    return SslCheckResult(
        name=name,
        host=host,
        port=port,
        expires_at=expires_at,
        days_remaining=round(days_remaining, 1),
        status=status,
        error=None,
    )


def check_all(
    endpoints_path: Path = DEFAULT_ENDPOINTS_PATH, *, now: datetime | None = None
) -> list[SslCheckResult]:
    """Itère les endpoints HTTPS et vérifie chaque cert.

    Séquentiel — on monitor 2-10 endpoints, le coût total reste < 5 s.
    Endpoints non-HTTPS sont skipped silencieusement.
    """
    now = now or datetime.now(UTC)
    endpoints = load_endpoints(endpoints_path)
    results: list[SslCheckResult] = []
    for endpoint in endpoints:
        hp = _extract_host_port(endpoint.url)
        if hp is None:
            continue
        host, port = hp
        results.append(_check_one(endpoint.name, host, port, now=now))
    return results


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(results: list[SslCheckResult]) -> SslReport:
    """``critical``/``error`` → rouge ; ``expiring_soon`` → jaune ; sinon silence."""
    has_critical = any(r.status in ("critical", "error") for r in results)
    has_warn = any(r.status == "expiring_soon" for r in results)
    should_alert = has_critical or has_warn

    if has_critical:
        alert_color = RED
    elif has_warn:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    ok_count = sum(1 for r in results if r.status == "ok")
    warn_count = sum(1 for r in results if r.status == "expiring_soon")
    crit_count = sum(1 for r in results if r.status == "critical")
    err_count = sum(1 for r in results if r.status == "error")
    summary = (
        f"{ok_count} ok · {warn_count} soon · {crit_count} critical · {err_count} error"
    )

    return SslReport(
        results=results,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[SslStatus, str] = {
    "ok": "[OK]",
    "expiring_soon": "[SOON]",
    "critical": "[CRIT]",
    "error": "[ERR]",
}


def _format_check_value(result: SslCheckResult) -> str:
    if result.error:
        return f"{result.host}:{result.port} · {result.error[:200]}"
    expires_str = result.expires_at.date().isoformat() if result.expires_at else "n/a"
    return (
        f"{result.host}:{result.port}"
        f" · expires {expires_str}"
        f" · {result.days_remaining}j restants"
    )


def build_ssl_embed(report: SslReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un field par endpoint."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[r.status]} {r.name}",
            value=_format_check_value(r),
            inline=False,
        )
        for r in report.results
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"SSLExpirer — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • SSLExpirer",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class SSLExpirer(BaseAgent):
    """IT Security — vérifie l'expiration des certs SSL."""

    name = "SSLExpirer"
    command = None  # pas de slash command (cron mensuel)
    breaker_name = None

    def __init__(self, *, endpoints_path: Path = DEFAULT_ENDPOINTS_PATH) -> None:
        self._endpoints_path = endpoints_path

    async def run(self) -> RunResult:
        results = check_all(self._endpoints_path)
        report = build_report(results)
        return await emit_alert_or_silence(
            report, embed_builder=build_ssl_embed, agent_name=self.name
        )


__all__ = [
    "CRITICAL_DAYS",
    "SSL_TIMEOUT_SECONDS",
    "WARN_DAYS",
    "SSLExpirer",
    "SslCheckResult",
    "SslReport",
    "SslStatus",
    "build_report",
    "build_ssl_embed",
    "check_all",
]
