"""IntentSignalsBot — Lead Gen Lead (P22.H Sales Sprint 3).

Capte des **signaux d'achat** sur le web public :

- ``breach`` — flux RSS de breaches publics (HIBP RSS si dispo,
  CERT-FR RSS bulletins, listes publiques type ``haveibeenpwned.com``).
- ``ciso_hire`` — flux RSS LinkedIn Jobs filtrés sur CISO / RSSI
  France (recherche sauvegardée exportée RSS).
- ``fundraise`` — flux ``news.crunchbase.com/feed/`` ou
  ``maddyness.com/feed/`` (levées FR).
- ``cve_critical`` — flux NVD / OSV pour les stack-tags déclarés par
  les clients (optionnel, vide en Sprint 3).

Toutes les sources sont **publiques et auth-free** — D-016 / D-017
strict. Output dans ``data/sales/signals/<YYYY-MM-DD>.yaml`` avec
``relevance_score`` calculé par mots-clés ICP. Notification Discord
ops_logs avec top-5 signaux.

Pas de scoring LLM (D-017). La pertinence est purement
mot-clé-driven — calibrée sur ``data/knowledge_base/ICP.md`` (PME tech
FR 20-250 employés).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx
import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_SOURCES_PATH: Path = REPO_ROOT / "data" / "sales" / "signals" / "sources.yaml"
DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "data" / "sales" / "signals"

# Mots-clés ICP — pèsent le relevance_score.
_ICP_KEYWORDS: tuple[str, ...] = (
    "saas",
    "scale-up",
    "scaleup",
    "pme",
    "tpe",
    "fintech",
    "healthtech",
    "edtech",
    "proptech",
    "logistique",
    "rgpd",
    "nis2",
    "iso 27001",
    "anssi",
)


@dataclass(frozen=True)
class ParsedSignal:
    """Signal parsé depuis un flux RSS."""

    kind: str
    title: str
    summary: str
    published_at: date
    source_url: str


@dataclass
class SignalStats:
    captured: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    top_relevance: int = 0
    sources_unreachable: int = 0

    def summary(self) -> str:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(self.by_kind.items()))
        return (
            f"captured={self.captured} top_relevance={self.top_relevance} "
            f"unreachable={self.sources_unreachable} ({breakdown})"
        )


def _score_relevance(title: str, summary: str) -> int:
    """Calcule le ``relevance_score`` 0-100 d'un signal."""
    text = (title + " " + summary).lower()
    matches = sum(1 for kw in _ICP_KEYWORDS if kw in text)
    base = 30  # tout signal capté vaut un minimum d'attention
    bonus = min(60, 10 * matches)
    if any(kw in text for kw in ("ransomware", "breach", "fuite", "leak")):
        bonus += 10
    return min(100, base + bonus)


def _parse_rss(xml_bytes: bytes, *, kind: str, max_items: int = 20) -> list[ParsedSignal]:
    """Extrait jusqu'à ``max_items`` signaux d'un flux RSS / Atom."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    today = datetime.now(UTC).date()
    out: list[ParsedSignal] = []
    for entry in root.iter():
        tag = entry.tag.lower().rsplit("}", 1)[-1]
        if tag not in {"item", "entry"}:
            continue
        title = ""
        summary = ""
        link = ""
        pub_date = today
        for child in entry:
            ctag = child.tag.lower().rsplit("}", 1)[-1]
            if ctag == "title" and child.text:
                title = child.text.strip()
            elif ctag in {"description", "summary"} and child.text:
                summary = re.sub(r"<[^>]+>", "", child.text).strip()
            elif ctag == "link":
                link = (child.get("href") or child.text or "").strip()
            elif ctag in {"pubdate", "published", "updated"} and child.text:
                pub_date = _parse_date(child.text.strip()) or pub_date
        if not title:
            continue
        out.append(
            ParsedSignal(
                kind=kind,
                title=title,
                summary=summary[:240],
                published_at=pub_date,
                source_url=link,
            )
        )
        if len(out) >= max_items:
            break
    return out


def _parse_date(value: str) -> date | None:
    """Parse les formats de date RSS courants — best-effort."""
    formats = (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


async def _fetch(url: str, timeout: float = 8.0) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ArgosOps/IntentSignalsBot"})
            if resp.status_code >= 300:
                return None
            return resp.content
    except (httpx.HTTPError, httpx.TimeoutException):
        return None


async def collect_signals(sources: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch + parse + score tous les flux déclarés. Retourne des dicts serializables."""
    out: list[dict[str, Any]] = []
    kind_keys = ("breach", "ciso_hire", "fundraise", "cve_critical")
    for kind in kind_keys:
        for feed_url in sources.get(kind, []) or []:
            xml = await _fetch(feed_url)
            if xml is None:
                logger.warning(f"IntentSignalsBot — {feed_url} unreachable")
                continue
            for signal in _parse_rss(xml, kind=kind):
                relevance = _score_relevance(signal.title, signal.summary)
                out.append(
                    {
                        "kind": signal.kind,
                        "title": signal.title,
                        "summary": signal.summary,
                        "published_at": signal.published_at.isoformat(),
                        "source_url": signal.source_url,
                        "relevance_score": relevance,
                    }
                )
    out.sort(key=lambda s: s["relevance_score"], reverse=True)
    return out


def build_signals_embed(stats: SignalStats, top: list[dict[str, Any]]) -> Embed:
    """Embed Discord — top-5 signaux par relevance."""
    if stats.top_relevance >= 70:
        color = ORANGE
    elif stats.captured > 0:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="Signaux capturés", value=str(stats.captured), inline=True),
        EmbedField(name="Top relevance", value=f"{stats.top_relevance}/100", inline=True),
        EmbedField(name="Sources injoignables", value=str(stats.sources_unreachable), inline=True),
    ]
    if top:
        preview_lines = []
        for s in top[:5]:
            preview_lines.append(
                f"• [{s['relevance_score']}/100] **{s['kind']}** · {s['title'][:80]}"
            )
        fields.append(EmbedField(name="Top 5", value="\n".join(preview_lines), inline=False))
    return Embed(
        title=f"IntentSignalsBot — {stats.captured} signaux",
        description=(
            "Inspecte `data/sales/signals/<date>.yaml` puis croise avec l'inbox "
            "ProspectMiner pour prioriser les leads."
            if stats.captured > 0
            else "Aucun signal capté (sources stables / week-end ?)."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • IntentSignalsBot",
    )


def _load_sources(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"signals/sources.yaml malformé : {path}")
    return raw


def _persist_signals(output_dir: Path, signals: list[dict[str, Any]]) -> Path:
    """Écrit le YAML quotidien (idempotent — réécrit le fichier du jour)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date()
    out_path = output_dir / f"{today.isoformat()}.yaml"
    payload = {
        "captured_at": datetime.now(UTC).isoformat(),
        "count": len(signals),
        "signals": signals,
    }
    out_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return out_path


class IntentSignalsBot(BaseAgent):
    """Lead Gen Lead — capte signaux d'achat publics, score ICP."""

    name = "IntentSignalsBot"
    command = "/run-intent-signals"
    breaker_name = "IntentSignalsBot"

    def __init__(
        self,
        *,
        sources_path: Path = DEFAULT_SOURCES_PATH,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self._sources_path = sources_path
        self._output_dir = output_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        sources = _load_sources(self._sources_path)
        if not sources:
            logger.info(f"IntentSignalsBot — pas de sources ({self._sources_path}), skip")
            return RunResult(status="success", output_summary="silence (no sources)")

        signals = await collect_signals(sources)
        by_kind: dict[str, int] = {}
        for s in signals:
            by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
        stats = SignalStats(
            captured=len(signals),
            by_kind=by_kind,
            top_relevance=signals[0]["relevance_score"] if signals else 0,
        )

        _persist_signals(self._output_dir, signals)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_signals_embed(stats, signals))
            except Exception as exc:
                logger.warning(f"IntentSignalsBot — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_SOURCES_PATH",
    "IntentSignalsBot",
    "ParsedSignal",
    "SignalStats",
    "build_signals_embed",
    "collect_signals",
]
