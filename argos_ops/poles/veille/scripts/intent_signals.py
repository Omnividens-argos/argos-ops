"""``IntentSignalsScript`` — signaux d'achat publics (Veille, archi v2).

Porté depuis ``argos_ops.agents.intent_signals`` (legacy). Bras déterministe :

1. lit ``data/sales/signals/sources.yaml`` (founder-maintained, auth-free) ;
2. fetch + parse + score chaque flux RSS par mots-clés ICP (PME tech FR) ;
3. écrit les top signaux dans **sa propre mémoire de pôle**
   (``kind="intent_signal"``).

Quatre familles de signaux : ``breach`` (fuites publiques), ``ciso_hire``
(embauches RSSI), ``fundraise`` (levées FR), ``cve_critical`` (CVE sur stacks
clients). Toutes les sources sont publiques et auth-free (D-016 / D-017).

Pas de Discord, pas de DB, pas de YAML quotidien, pas de LLM (D-017) : la
mémoire est l'unique sortie et le :class:`VeilleAgent` lit cette mémoire et
agit. La pertinence est purement mot-clé-driven, calibrée sur l'ICP (PME tech
FR 20-250 employés). Idempotent : un signal re-capté a le même corps -> même
fait (le socle :func:`argos_ops.poles.memory.write_memory` déduplique par hash).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

DEFAULT_SOURCES_PATH: Path = REPO_ROOT / "data" / "sales" / "signals" / "sources.yaml"

_TOP_N = 10
_IMPORTANT_THRESHOLD = 70  # un signal score >= 70 est marqué important

# Familles de signaux d'achat captées (clés du sources.yaml).
_KIND_KEYS: tuple[str, ...] = ("breach", "ciso_hire", "fundraise", "cve_critical")

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


def _score_relevance(title: str, summary: str) -> int:
    """Calcule le ``relevance_score`` 0-100 d'un signal."""
    text = (title + " " + summary).lower()
    matches = sum(1 for kw in _ICP_KEYWORDS if kw in text)
    base = 30  # tout signal capté vaut un minimum d'attention
    bonus = min(60, 10 * matches)
    if any(kw in text for kw in ("ransomware", "breach", "fuite", "leak")):
        bonus += 10
    return min(100, base + bonus)


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


async def _fetch(url: str, timeout: float = 8.0) -> bytes | None:
    """GET auth-free d'un flux RSS — renvoie ``None`` si injoignable."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ArgosOps/IntentSignals"})
            if resp.status_code >= 300:
                return None
            return resp.content
    except (httpx.HTTPError, httpx.TimeoutException):
        return None


async def collect_signals(sources: dict[str, object]) -> list[dict[str, str | int]]:
    """Fetch + parse + score tous les flux déclarés, triés par relevance desc."""
    out: list[dict[str, str | int]] = []
    for kind in _KIND_KEYS:
        feeds = sources.get(kind) or []
        if not isinstance(feeds, list):
            continue
        for feed_url in feeds:
            xml = await _fetch(str(feed_url))
            if xml is None:
                logger.warning(f"IntentSignals — {feed_url} injoignable")
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
    out.sort(key=lambda s: int(s["relevance_score"]), reverse=True)
    return out


def _load_sources(path: Path) -> dict[str, object]:
    """Charge le ``sources.yaml`` (vide si absent, lève si malformé)."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AgentDataSourceError(f"signals/sources.yaml malformé : {path}")
    return raw


class IntentSignalsScript(BaseScript):
    """Capte les signaux d'achat publics et les mémorise (``kind="intent_signal"``)."""

    pole = "veille"
    name = "intent_signals"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        sources_path: Path = DEFAULT_SOURCES_PATH,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._sources_path = sources_path

    async def run(self) -> ScriptResult:
        sources = _load_sources(self._sources_path)
        if not sources:
            logger.info(f"IntentSignals — pas de sources ({self._sources_path}), skip")
            return ScriptResult(
                status="success",
                summary="0 signal capté (aucune source)",
                written=[],
            )

        signals = await collect_signals(sources)
        top = signals[:_TOP_N]

        written = []
        for signal in top:
            kind = str(signal["kind"])
            relevance = int(signal["relevance_score"])
            title = str(signal["title"])
            source_url = str(signal["source_url"])
            record = await self.write_memory(
                f"Signal {kind} (score {relevance}/100) : {title}",
                kind="intent_signal",
                tags=("intent", kind),
                important=relevance >= _IMPORTANT_THRESHOLD,
                source=source_url or self.name,
            )
            written.append(record)

        top_relevance = int(top[0]["relevance_score"]) if top else 0
        return ScriptResult(
            status="success",
            summary=(
                f"{len(top)} signal(aux) mémorisé(s) sur {len(signals)} capté(s) "
                f"(top relevance {top_relevance}/100)"
            ),
            written=written,
        )


__all__ = [
    "DEFAULT_SOURCES_PATH",
    "IntentSignalsScript",
    "ParsedSignal",
    "collect_signals",
]
