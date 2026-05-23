"""UptimeMonitor — SRE de l'infrastructure publique (P22.C Tech/SRE Sprint 4).

Ping HTTP les endpoints publics déclarés dans
``data/uptime/endpoints.yaml`` et alerte Discord si l'un d'eux est down
plus de :data:`DOWN_THRESHOLD_SECONDS` (60 s par défaut).

Politique anti-spam :
- **Silence** Discord si tous les endpoints répondent en 2xx/3xx
- **Embed rouge** si ≥1 endpoint timeout, 5xx, ou refuse la connexion
- **Embed jaune** si ≥1 endpoint répond en 4xx (potentiellement un
  changement de comportement applicatif, à vérifier mais pas critique)

Le check est volontairement **read-only** : on fait des ``GET`` simples
(pas de HEAD car certains serveurs les rejettent), 10 s de timeout
agressif côté client + ``DOWN_THRESHOLD_SECONDS`` comme cutoff pour
l'alerte « down ».

Format ``data/uptime/endpoints.yaml`` ::

    endpoints:
      - name: "Site public"
        url: "https://omnividens.fr/"
      - name: "Admin Panel"
        url: "https://ops.omnividens.fr/"
        # method (default: GET), timeout_seconds (default: 10)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import yaml
from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
)

UptimeStatus = Literal["up", "degraded", "down"]

DEFAULT_ENDPOINTS_PATH: Path = REPO_ROOT / "data" / "uptime" / "endpoints.yaml"
DEFAULT_TIMEOUT_SECONDS = 10.0
DOWN_THRESHOLD_SECONDS = 60.0


@dataclass(frozen=True)
class EndpointConfig:
    """Endpoint déclaré dans le YAML — `name`, `url` + overrides optionnels."""

    name: str
    url: str
    method: str = "GET"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class UptimeCheckResult:
    """Résultat d'un check HTTP sur un endpoint."""

    endpoint: EndpointConfig
    status: UptimeStatus
    http_status: int | None
    latency_ms: float | None
    error: str | None  # exception class + message si crash


@dataclass(frozen=True)
class UptimeReport:
    """Résultat agrégé du run UptimeMonitor."""

    results: list[UptimeCheckResult]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Configuration
# =============================================================================
def load_endpoints(path: Path = DEFAULT_ENDPOINTS_PATH) -> list[EndpointConfig]:
    """Lit le YAML et retourne la liste des endpoints à monitorer.

    Le fichier peut ne pas exister (rien à monitorer encore) — on
    retourne une liste vide silencieusement. Une entrée mal formée fait
    raise un :class:`ValueError` explicite plutôt que de skipper en
    silence (un endpoint manquant est un trou de surveillance).
    """
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("endpoints", [])
    out: list[EndpointConfig] = []
    for entry in entries:
        name = entry.get("name")
        url = entry.get("url")
        if not name or not url:
            raise ValueError(f"Endpoint mal formé (manque name ou url) : {entry!r}")
        out.append(
            EndpointConfig(
                name=name,
                url=url,
                method=entry.get("method", "GET"),
                timeout_seconds=float(entry.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
            )
        )
    return out


# =============================================================================
# Check HTTP
# =============================================================================
async def _check_one(
    client: httpx.AsyncClient, endpoint: EndpointConfig
) -> UptimeCheckResult:
    """Effectue un check HTTP unique. N'attrape jamais d'exception
    inattendue — chaque crash devient un :class:`UptimeCheckResult`
    ``down`` avec le message d'erreur."""
    start = time.perf_counter()
    try:
        response = await client.request(
            endpoint.method, endpoint.url, timeout=endpoint.timeout_seconds
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
    except httpx.TimeoutException as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return UptimeCheckResult(
            endpoint=endpoint,
            status="down",
            http_status=None,
            latency_ms=latency_ms,
            error=f"timeout: {exc}",
        )
    except (httpx.ConnectError, httpx.NetworkError) as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return UptimeCheckResult(
            endpoint=endpoint,
            status="down",
            http_status=None,
            latency_ms=latency_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return UptimeCheckResult(
            endpoint=endpoint,
            status="down",
            http_status=None,
            latency_ms=latency_ms,
            error=f"{type(exc).__name__}: {exc}",
        )

    status: UptimeStatus
    if response.status_code >= 500:
        status = "down"
    elif response.status_code >= 400:
        status = "degraded"
    else:
        status = "up"
    return UptimeCheckResult(
        endpoint=endpoint,
        status=status,
        http_status=response.status_code,
        latency_ms=latency_ms,
        error=None,
    )


async def check_all(endpoints: list[EndpointConfig]) -> list[UptimeCheckResult]:
    """Lance les checks séquentiellement.

    Pas de parallélisme : on monitor 2-10 endpoints, le coût total reste
    de l'ordre de la seconde, et la séquentialité simplifie le profiling
    en cas d'incident.
    """
    results: list[UptimeCheckResult] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for endpoint in endpoints:
            results.append(await _check_one(client, endpoint))
    return results


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(results: list[UptimeCheckResult]) -> UptimeReport:
    """Politique : ``down`` → rouge, ``degraded`` (4xx) → jaune, ``up`` → silence."""
    has_down = any(r.status == "down" for r in results)
    has_degraded = any(r.status == "degraded" for r in results)
    should_alert = has_down or has_degraded

    if has_down:
        alert_color = RED
    elif has_degraded:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    up_count = sum(1 for r in results if r.status == "up")
    deg_count = sum(1 for r in results if r.status == "degraded")
    down_count = sum(1 for r in results if r.status == "down")
    summary = f"{up_count} up · {deg_count} degraded · {down_count} down"

    return UptimeReport(
        results=results,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[UptimeStatus, str] = {
    "up": "[UP]",
    "degraded": "[4XX]",
    "down": "[DOWN]",
}


def _format_check_value(result: UptimeCheckResult) -> str:
    parts: list[str] = [result.endpoint.url]
    if result.http_status is not None:
        parts.append(f"HTTP {result.http_status}")
    if result.latency_ms is not None:
        parts.append(f"{int(result.latency_ms)}ms")
    if result.error:
        parts.append(result.error[:120])
    return " · ".join(parts)


def build_uptime_embed(report: UptimeReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un field par endpoint."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[r.status]} {r.endpoint.name}",
            value=_format_check_value(r),
            inline=False,
        )
        for r in report.results
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"UptimeMonitor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • UptimeMonitor",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class UptimeMonitor(BaseAgent):
    """SRE — ping les endpoints publics et alerte si down."""

    name = "UptimeMonitor"
    command = "/run-uptime"
    breaker_name = None

    def __init__(self, *, endpoints_path: Path = DEFAULT_ENDPOINTS_PATH) -> None:
        self._endpoints_path = endpoints_path

    async def run(self) -> RunResult:
        endpoints = load_endpoints(self._endpoints_path)
        if not endpoints:
            logger.info(
                f"UptimeMonitor — aucun endpoint déclaré ({self._endpoints_path}), skip"
            )
            return RunResult(
                status="success",
                output_summary="silence (aucun endpoint)",
                extras={"alerted": False, "summary": "0 endpoints"},
            )

        results = await check_all(endpoints)
        report = build_report(results)
        return await emit_alert_or_silence(
            report, embed_builder=build_uptime_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_ENDPOINTS_PATH",
    "DEFAULT_TIMEOUT_SECONDS",
    "DOWN_THRESHOLD_SECONDS",
    "EndpointConfig",
    "UptimeCheckResult",
    "UptimeMonitor",
    "UptimeReport",
    "UptimeStatus",
    "build_report",
    "build_uptime_embed",
    "check_all",
    "load_endpoints",
]
