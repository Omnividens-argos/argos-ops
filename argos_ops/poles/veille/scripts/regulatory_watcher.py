"""``RegulatoryWatcherScript`` — veille réglementaire (Veille, archi v2).

Porté depuis ``argos_ops.agents.regulatory_watcher`` (legacy). Bras
déterministe qui suit les évolutions réglementaires impactant Argos /
SecHunter (RGPD, AI Act, NIS2, DORA) via les flux RSS officiels (Commission
UE, CNIL, ANSSI). Il :

1. lit ``data/regulatory/sources.yaml`` (sources + keywords) ;
2. parse chaque flux RSS (``feedparser``) et filtre les entrées sur une liste
   de mots-clés stricte (anti-bruit politique) ;
3. ne retient que les GUIDs jamais vus (cache ``data/regulatory/seen_guids.json``) ;
4. écrit chaque nouvelle entrée dans **sa propre mémoire de pôle**
   (``kind="regulatory"``) puis persiste tous les GUIDs scannés.

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit
cette mémoire et agit. Idempotent : une entrée re-détectée a le même corps ⇒
même fait (le socle :func:`argos_ops.poles.memory.write_memory` déduplique par
hash), et son GUID est dans ``seen_guids.json`` dès le premier passage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

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


async def fetch_source(source: RegulatorySource, keywords: tuple[str, ...]) -> list[RegulatoryItem]:
    """Parse le flux RSS et filtre les entrées qui matchent les keywords."""
    try:
        import feedparser  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("RegulatoryWatcher - feedparser absent, skip source")
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


def select_new_items(items: list[RegulatoryItem], seen: set[str]) -> list[RegulatoryItem]:
    """Filtre les entrées dont le GUID a déjà été vu."""
    return [item for item in items if item.guid not in seen]


class RegulatoryWatcherScript(BaseScript):
    """Veille réglementaire RSS filtrée par keywords (``kind="regulatory"``)."""

    pole = "veille"
    name = "regulatory_watcher"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        sources_path: Path = DEFAULT_SOURCES_PATH,
        seen_path: Path = DEFAULT_SEEN_PATH,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._sources_path = sources_path
        self._seen_path = seen_path

    async def run(self) -> ScriptResult:
        sources, keywords = load_sources(self._sources_path)
        if not sources:
            logger.info(f"RegulatoryWatcher - aucune source déclarée ({self._sources_path})")
            return ScriptResult(
                status="success",
                summary="aucune source réglementaire déclarée",
                written=[],
            )

        seen = load_seen_guids(self._seen_path)
        all_items: list[RegulatoryItem] = []
        for source in sources:
            try:
                all_items.extend(await fetch_source(source, keywords))
            except Exception as exc:
                logger.warning(
                    f"RegulatoryWatcher - fetch {source.name} échoué: {type(exc).__name__}: {exc}"
                )

        new_items = select_new_items(all_items, seen)

        # Persiste tous les guids scannés (pas que les matched), sinon le
        # cache RSS oublie qu'on a vu un titre non pertinent qui pourrait
        # ressortir comme "nouveau" si le keyword set change.
        seen.update(item.guid for item in all_items)
        save_seen_guids(seen, path=self._seen_path)

        written = []
        for item in new_items:
            tags = ("regulatory", *item.matched_keywords[:3])
            record = await self.write_memory(
                f"[{item.source}] {item.title} (keywords: {', '.join(item.matched_keywords)})",
                kind="regulatory",
                tags=tags,
                important=False,
                source=item.link or self.name,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=(
                f"{len(new_items)} nouvelle(s) entrée(s) réglementaire(s) "
                f"sur {len(all_items)} scannée(s)"
            ),
            written=written,
        )


__all__ = [
    "DEFAULT_KEYWORDS",
    "DEFAULT_MAX_SEEN_KEPT",
    "DEFAULT_SEEN_PATH",
    "DEFAULT_SOURCES_PATH",
    "SERVICE_NAME",
    "RegulatoryItem",
    "RegulatorySource",
    "RegulatoryWatcherScript",
    "fetch_source",
    "load_seen_guids",
    "load_sources",
    "match_keywords",
    "save_seen_guids",
    "select_new_items",
]
