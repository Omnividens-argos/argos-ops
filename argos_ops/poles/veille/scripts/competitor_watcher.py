"""``CompetitorWatcherScript`` — veille concurrentielle (Veille, archi v2).

Porté depuis ``argos_ops.agents.competitor_watcher`` (legacy). Bras déterministe :

1. lit ``data/competitors/targets.yaml`` (founder-maintained) les pages
   ``/pricing`` et ``/features`` de quelques concurrents ;
2. fetch (cache 24h via :mod:`argos_ops.agents._fetcher_base`), normalise le
   HTML en texte hashable, compare au snapshot précédent (sha256) ;
3. persiste le snapshot (baseline au premier passage, nouveau hash sur diff) et
   écrit un fait dans **sa propre mémoire de pôle** (``kind="competitor"``) pour
   chaque page qui a bougé.

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit cette
mémoire et agit. Idempotent : une page re-détectée comme changée a le même corps
de fait (URL + section) ⇒ même fait (le socle
:func:`argos_ops.poles.memory.write_memory` déduplique par hash).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

DEFAULT_TARGETS_PATH: Path = REPO_ROOT / "data" / "competitors" / "targets.yaml"
DEFAULT_SNAPSHOT_DIR: Path = REPO_ROOT / "data" / "competitors" / "snapshots"
SERVICE_NAME = "competitor-watcher"

_MAX_FACTS_PER_RUN = 5  # cap les faits écrits par run (anti-flood mémoire)


@dataclass(frozen=True)
class CompetitorTarget:
    """Une page concurrent à scraper — déclarée dans le YAML."""

    name: str
    section: str  # "pricing" | "features" | autre
    url: str


@dataclass(frozen=True)
class CompetitorChange:
    """Résultat de la comparaison sur une page."""

    target: CompetitorTarget
    previous_hash: str | None
    current_hash: str
    changed: bool


# =============================================================================
# Config — YAML
# =============================================================================
def load_targets(path: Path = DEFAULT_TARGETS_PATH) -> list[CompetitorTarget]:
    """Lit le YAML ``targets.yaml``. Fichier absent -> liste vide."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("targets", [])
    out: list[CompetitorTarget] = []
    for entry in entries:
        name = entry.get("name")
        url = entry.get("url")
        section = entry.get("section", "page")
        if not name or not url:
            raise ValueError(f"Target mal forme (manque name ou url): {entry!r}")
        out.append(CompetitorTarget(name=name, section=section, url=url))
    return out


# =============================================================================
# Normalisation HTML -> texte hashable
# =============================================================================
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def normalize_html(html: str) -> str:
    """Extrait le texte visible et écrase le whitespace.

    Suffit pour détecter qu'un prix a bougé ou qu'une feature a été
    ajoutée. Pas de parsing structuré (lxml/bs4) — sur 5-10 pages, le
    coût d'un parser DOM ne se justifie pas et augmente la surface de
    bugs (CDATA, encodings exotiques, ...).
    """
    stripped_scripts = _SCRIPT_STYLE_RE.sub(" ", html)
    no_tags = _TAG_RE.sub(" ", stripped_scripts)
    return _WS_RE.sub(" ", no_tags).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =============================================================================
# Snapshot I/O
# =============================================================================
def _snapshot_path(target: CompetitorTarget, base_dir: Path) -> Path:
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{target.name}_{target.section}")
    return base_dir / f"{safe_name}.json"


def load_previous_hash(target: CompetitorTarget, base_dir: Path) -> str | None:
    path = _snapshot_path(target, base_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"CompetitorWatcher snapshot corrompu ({path.name}): {exc}")
        return None
    value = payload.get("hash") if isinstance(payload, dict) else None
    return str(value) if isinstance(value, str) else None


def save_snapshot_hash(target: CompetitorTarget, *, hash_: str, base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(target, base_dir)
    path.write_text(
        json.dumps(
            {
                "name": target.name,
                "section": target.section,
                "url": target.url,
                "hash": hash_,
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# =============================================================================
# Scrape + diff
# =============================================================================
async def compare_target(target: CompetitorTarget, *, snapshot_dir: Path) -> CompetitorChange:
    """Fetch (avec cache 24h) + hash + diff."""
    response = await fetch(target.url, service=SERVICE_NAME)
    current = content_hash(normalize_html(response.body))
    previous = load_previous_hash(target, snapshot_dir)
    changed = previous is not None and previous != current
    return CompetitorChange(
        target=target,
        previous_hash=previous,
        current_hash=current,
        changed=changed,
    )


class CompetitorWatcherScript(BaseScript):
    """Surveille les pages concurrents et mémorise les diffs (``kind="competitor"``)."""

    pole = "veille"
    name = "competitor_watcher"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        targets_path: Path = DEFAULT_TARGETS_PATH,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._targets_path = targets_path
        self._snapshot_dir = snapshot_dir

    async def run(self) -> ScriptResult:
        targets = load_targets(self._targets_path)
        if not targets:
            return ScriptResult(
                status="success",
                summary="0/0 page(s) concurrent ont bouge (aucune cible)",
                written=[],
            )

        changes: list[CompetitorChange] = []
        for target in targets:
            try:
                change = await compare_target(target, snapshot_dir=self._snapshot_dir)
            except Exception as exc:
                logger.warning(
                    f"CompetitorWatcher — fetch {target.name} echoue: {type(exc).__name__}: {exc}"
                )
                continue
            changes.append(change)
            if change.changed or change.previous_hash is None:
                # On persiste à chaque fetch réussi : premier run = baseline,
                # diff = on bascule sur le nouveau hash sans re-détecter le même
                # changement au prochain tour (politique « changement vu »).
                save_snapshot_hash(target, hash_=change.current_hash, base_dir=self._snapshot_dir)

        changed = [c for c in changes if c.changed]
        written = []
        for change in changed[:_MAX_FACTS_PER_RUN]:
            t = change.target
            record = await self.write_memory(
                f"Concurrent {t.name} a modifie sa page {t.section} - {t.url}",
                kind="competitor",
                tags=("competitor", t.section),
                important=False,
                source=t.url,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(changed)}/{len(targets)} page(s) concurrent ont bouge",
            written=written,
        )


__all__ = [
    "DEFAULT_SNAPSHOT_DIR",
    "DEFAULT_TARGETS_PATH",
    "SERVICE_NAME",
    "CompetitorChange",
    "CompetitorTarget",
    "CompetitorWatcherScript",
    "compare_target",
    "content_hash",
    "load_previous_hash",
    "load_targets",
    "normalize_html",
    "save_snapshot_hash",
]
