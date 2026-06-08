"""RegulatoryWatcher — Compliance Watch (P22.D Veille Sprint 6).

Suit les évolutions réglementaires impactant Argos / SecHunter (RGPD,
AI Act, NIS2, DORA) via les flux RSS officiels (Commission UE, CNIL,
ANSSI). Filtre les entrées sur une liste de mots-clés stricte pour
éviter le bruit politique.

Politique anti-spam :
- **Silence** Discord si aucune entrée nouvelle ne matche les keywords
- **Embed jaune** si ≥1 entrée nouvelle correspond

L'état "déjà vu" est tracé via un fichier de hash des derniers GUIDs
RSS connus (``data/regulatory/seen_guids.json``) — on n'alerte qu'une
fois par publication.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 8 Veille, Sprint 6.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField

SERVICE_NAME = "regulatory-watcher"
DEFAULT_SOURCES_PATH: Path = REPO_ROOT / "data" / "regulatory" / "sources.yaml"
DEFAULT_SEEN_PATH: Path = REPO_ROOT / "data" / "regulatory" / "seen_guids.json"
DEFAULT_MAX_SEEN_KEPT = 500  # rolling window pour empêcher le fichier de croître sans fin

# Mots-clés pertinents pour Argos (cyber + IA + protection donnée)
DEFAULT_KEYWORDS: Final[tuple[str, ...]] = (
    "rgpd",
    "gdpr",
    "ai act",
    "ia act",
    "nis2",
    "nis 2",
    "dora",
    "cyber resilience",
    "directive nis",
    "transposition",
    "pentest",
    "cnil",
    "anssi",
)


@dataclass(frozen=True)
class RegulatorySource:
    name: str  # ex: "Commission UE Justice"
    rss_url: str


@dataclass(frozen=True)
class RegulatoryItem:
    """Une entrée RSS pertinente."""

    source: str
    guid: str
    title: str
    link: str
    published_at: datetime | None
    matched_keywords: list[str]


@dataclass(frozen=True)
class RegulatoryReport:
    new_items: list[RegulatoryItem]
    total_scanned: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Config
# =============================================================================
def load_sources(
    path: Path = DEFAULT_SOURCES_PATH,
) -> tuple[list[RegulatorySource], tuple[str, ...]]:
    """Lit ``sources.yaml``. Renvoie (sources, keywords)."""
    if not path.exists():
        return [], DEFAULT_KEYWORDS
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources_raw = raw.get("sources", [])
    sources: list[RegulatorySource] = []
    for entry in sources_raw:
        name = entry.get("name")
        rss_url = entry.get("rss_url")
        if not name or not rss_url:
            continue
        sources.append(RegulatorySource(name=str(name), rss_url=str(rss_url)))
    keywords = tuple(
        kw.lower() for kw in raw.get("keywords", DEFAULT_KEYWORDS) if isinstance(kw, str)
    )
    return sources, keywords or DEFAULT_KEYWORDS


# =============================================================================
# Seen GUIDs
# =============================================================================
def load_seen_guids(path: Path = DEFAULT_SEEN_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"RegulatoryWatcher seen_guids corrompu: {exc}")
        return set()
    return set(payload.get("seen", []))


def save_seen_guids(
    seen: set[str], *, path: Path = DEFAULT_SEEN_PATH, max_kept: int = DEFAULT_MAX_SEEN_KEPT
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = list(seen)[-max_kept:]
    path.write_text(
        json.dumps({"seen": trimmed, "saved_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


# =============================================================================
# Parsing
# =============================================================================
def match_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    """Retourne la liste des keywords présents dans ``text`` (lowercased)."""
    lowered = text.lower()
    return [kw for kw in keywords if kw in lowered]


async def fetch_source(
    source: RegulatorySource, keywords: tuple[str, ...]
) -> list[RegulatoryItem]:
    """Parse le flux RSS et filtre les entrées qui matchent les keywords."""
    try:
        import feedparser  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("RegulatoryWatcher — feedparser absent, skip source")
        return []
    response = await fetch(source.rss_url, service=SERVICE_NAME)
    parsed = feedparser.parse(response.body)
    items: list[RegulatoryItem] = []
    for entry in parsed.entries:
        title = str(entry.get("title", ""))
        summary = str(entry.get("summary", ""))
        matches = match_keywords(f"{title} {summary}", keywords)
        if not matches:
            continue
        guid = str(entry.get("id") or entry.get("link") or title)
        published_at: datetime | None = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime

            published_at = datetime.fromtimestamp(mktime(entry.published_parsed), UTC)
        items.append(
            RegulatoryItem(
                source=source.name,
                guid=guid,
                title=title,
                link=str(entry.get("link") or ""),
                published_at=published_at,
                matched_keywords=matches,
            )
        )
    return items


# =============================================================================
# Report
# =============================================================================
def select_new_items(
    items: list[RegulatoryItem], seen: set[str]
) -> list[RegulatoryItem]:
    return [item for item in items if item.guid not in seen]


def build_report(new_items: list[RegulatoryItem], total_scanned: int) -> RegulatoryReport:
    if not new_items:
        return RegulatoryReport(
            new_items=[],
            total_scanned=total_scanned,
            should_alert=False,
            alert_color=GREEN,
            summary=f"aucune nouvelle entrée ({total_scanned} scannées)",
        )
    return RegulatoryReport(
        new_items=new_items,
        total_scanned=total_scanned,
        should_alert=True,
        alert_color=YELLOW,
        summary=f"{len(new_items)} nouvelle(s) entrée(s) réglementaire(s) pertinente(s)",
    )


_LINK_TRUNCATE_RE = re.compile(r"^(https?://[^/]+)(/[^/]*)?")


def _short_link(link: str) -> str:
    """Affiche un short link cliquable : ``https://eur-lex.europa.eu/...``."""
    if not link:
        return ""
    match = _LINK_TRUNCATE_RE.match(link)
    if not match:
        return link[:80]
    return f"{match.group(1)}{match.group(2) or '/'}…"


def build_regulatory_embed(
    report: RegulatoryReport, *, now: datetime | None = None
) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[{item.source}] {item.title[:200]}",
            value=(
                f"keywords : `{', '.join(item.matched_keywords)}`\n"
                f"{_short_link(item.link)}"
            ),
            inline=False,
        )
        for item in report.new_items[:10]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"RegulatoryWatcher — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • RegulatoryWatcher",
        timestamp=now.isoformat(),
    )


class RegulatoryWatcher(BaseAgent):
    """Compliance Watch — flux RSS officiels filtrés par keywords pertinents."""

    name = "RegulatoryWatcher"
    command = "/run-regulatory-watch"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        sources_path: Path = DEFAULT_SOURCES_PATH,
        seen_path: Path = DEFAULT_SEEN_PATH,
    ) -> None:
        self._sources_path = sources_path
        self._seen_path = seen_path

    async def run(self) -> RunResult:
        sources, keywords = load_sources(self._sources_path)
        if not sources:
            logger.info(
                f"RegulatoryWatcher — aucune source déclarée ({self._sources_path})"
            )
            return RunResult(
                status="success",
                output_summary="silence (aucune source)",
                extras={"alerted": False, "summary": "0 sources"},
            )
        seen = load_seen_guids(self._seen_path)
        all_items: list[RegulatoryItem] = []
        for source in sources:
            try:
                all_items.extend(await fetch_source(source, keywords))
            except Exception as exc:
                logger.warning(
                    f"RegulatoryWatcher — fetch {source.name} échoué: "
                    f"{type(exc).__name__}: {exc}"
                )
        new_items = select_new_items(all_items, seen)
        seen_before = len(seen)
        # Persiste tous les guids scannés (pas que les matched), sinon le
        # cache RSS oublie qu'on a vu un titre non pertinent qui pourrait
        # ressortir comme "nouveau" si le keyword set change.
        seen.update(item.guid for item in all_items)
        save_seen_guids(seen, path=self._seen_path)
        report = build_report(new_items, total_scanned=len(all_items))
        inputs = [
            IOItem(
                label="Sources RSS réglementaires",
                kind="file",
                detail=", ".join(s.name for s in sources),
                ref=str(self._sources_path),
                count=len(sources),
            ),
            IOItem(
                label="Entrées RSS matchant les keywords",
                kind="http",
                detail=f"keywords : {', '.join(keywords)}",
                count=len(all_items),
            ),
            IOItem(
                label="GUIDs déjà vus (cache anti-doublon)",
                kind="file",
                ref=str(self._seen_path),
                count=seen_before,
            ),
        ]
        outputs = [
            IOItem(
                label="Nouvelles entrées réglementaires",
                kind="other",
                detail=", ".join(i.title[:80] for i in new_items) or None,
                count=len(new_items),
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_regulatory_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_KEYWORDS",
    "DEFAULT_MAX_SEEN_KEPT",
    "DEFAULT_SEEN_PATH",
    "DEFAULT_SOURCES_PATH",
    "SERVICE_NAME",
    "RegulatoryItem",
    "RegulatoryReport",
    "RegulatorySource",
    "RegulatoryWatcher",
    "build_regulatory_embed",
    "build_report",
    "fetch_source",
    "load_seen_guids",
    "load_sources",
    "match_keywords",
    "save_seen_guids",
    "select_new_items",
]
