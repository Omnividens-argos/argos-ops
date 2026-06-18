"""``UptimeMonitorScript`` — disponibilité des endpoints publics (archi v2, S8).

Lit ``data/poles/sre/uptime/endpoints.yaml`` (sous ``poles_root``) et ping chaque
endpoint : vert si 2xx/3xx, jaune si 4xx (degraded), rouge si 5xx / timeout /
erreur réseau (down). Le *probe* HTTP est injectable (tests hermétiques, aucun
réseau). Aucun endpoint configuré ⇒ vert.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst

ENDPOINTS_FILE = ("uptime", "endpoints.yaml")
DEFAULT_TIMEOUT_SECONDS = 10.0


def endpoints_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / ENDPOINTS_FILE[0] / ENDPOINTS_FILE[1]


@dataclass(frozen=True)
class EndpointConfig:
    """Un endpoint à surveiller."""

    name: str
    url: str
    method: str = "GET"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class UptimeCheckResult:
    """Résultat du ping d'un endpoint."""

    name: str
    url: str
    status: str  # up | degraded | down
    http_status: int | None
    latency_ms: float | None
    error: str | None


# Un *probe* prend une config endpoint et renvoie un résultat (jamais d'exception).
Probe = Callable[[EndpointConfig], Awaitable[UptimeCheckResult]]


def load_endpoints(*, poles_root: Path = POLES_DIR) -> list[EndpointConfig]:
    """Charge les endpoints (``[]`` si fichier absent / malformé)."""
    path = endpoints_path(poles_root=poles_root)
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"uptime_monitor — endpoints.yaml invalide : {exc}")
        return []
    items = raw.get("endpoints") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    out: list[EndpointConfig] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        out.append(
            EndpointConfig(
                name=str(item.get("name") or item["url"]),
                url=str(item["url"]),
                method=str(item.get("method") or "GET").upper(),
                timeout_seconds=float(item.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
            )
        )
    return out


def classify_http(status_code: int) -> str:
    if status_code >= 500:
        return "down"
    if status_code >= 400:
        return "degraded"
    return "up"


async def http_probe(endpoint: EndpointConfig) -> UptimeCheckResult:
    """Probe réel via httpx. Toute erreur réseau ⇒ ``down`` (jamais d'exception)."""
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.request(
                endpoint.method, endpoint.url, timeout=endpoint.timeout_seconds
            )
        latency = (time.monotonic() - started) * 1000.0
        return UptimeCheckResult(
            name=endpoint.name,
            url=endpoint.url,
            status=classify_http(resp.status_code),
            http_status=resp.status_code,
            latency_ms=latency,
            error=None,
        )
    except (httpx.HTTPError, OSError) as exc:
        latency = (time.monotonic() - started) * 1000.0
        return UptimeCheckResult(
            name=endpoint.name,
            url=endpoint.url,
            status="down",
            http_status=None,
            latency_ms=latency,
            error=f"{type(exc).__name__}: {exc}",
        )


def build_report(results: list[UptimeCheckResult]) -> SreReport:
    if not results:
        return SreReport("green", "Aucun endpoint configuré.")
    up = sum(1 for r in results if r.status == "up")
    degraded = sum(1 for r in results if r.status == "degraded")
    down = sum(1 for r in results if r.status == "down")
    severity: Severity = worst("red" if down else "green", "yellow" if degraded else "green")
    summary = f"{up} up · {degraded} degraded · {down} down (sur {len(results)})"
    detail = "\n".join(
        f"- {r.name} : {r.status}"
        + (f" (HTTP {r.http_status})" if r.http_status else "")
        + (f" — {r.error}" if r.error else "")
        for r in results
        if r.status != "up"
    )
    return SreReport(severity, summary, detail)


class UptimeMonitorScript(BaseSreScript):
    """Ping les endpoints publics et alerte sur down/degraded."""

    name = "uptime_monitor"

    def __init__(self, *, poles_root: Path = POLES_DIR, probe: Probe | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._probe = probe or http_probe

    async def check(self) -> SreReport:
        endpoints = load_endpoints(poles_root=self.poles_root)
        results = [await self._probe(ep) for ep in endpoints]
        return build_report(results)


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "EndpointConfig",
    "Probe",
    "UptimeCheckResult",
    "UptimeMonitorScript",
    "build_report",
    "classify_http",
    "endpoints_path",
    "http_probe",
    "load_endpoints",
]
