"""Lecture et scoring des tendances cyber pour TrendSpotter.

Source canonique : ``data/trends/sources.yaml``. Le fichier liste des
items au format ::

    items:
      - title: "Faille critique CVE-2026-12345 sur Ivanti"
        url: "https://cert.fr/..."
        published_at: "2026-05-22"
        keywords: [ivanti, cve, supply-chain]
        weight: 1.0

Tant qu'un scraper n'est pas branché (sprint ultérieur), le fichier est
maintenu à la main via veille founder + agrégation depuis CERT-FR,
Bleeping, ANSSI. Le scoring trie par récence x poids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT

DEFAULT_SOURCES = REPO_ROOT / "data" / "trends" / "sources.yaml"


@dataclass
class TrendItem:
    title: str
    url: str
    published_at: date
    keywords: list[str] = field(default_factory=list)
    weight: float = 1.0

    @property
    def age_days(self) -> int:
        return (datetime.now(UTC).date() - self.published_at).days

    @property
    def score(self) -> float:
        decay = max(0.0, 1.0 - (self.age_days / 14.0))
        return decay * self.weight


def load_trend_sources(path: Path | None = None) -> list[TrendItem]:
    """Charge la liste de tendances depuis le YAML canonique."""
    path = path or DEFAULT_SOURCES
    if not path.exists():
        logger.info(f"TrendSpotter — fichier {path} absent, retour liste vide")
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items: list[TrendItem] = []
    for entry in raw.get("items", []):
        if not isinstance(entry, dict):
            continue
        pub = entry.get("published_at")
        if isinstance(pub, str):
            try:
                pub_date = date.fromisoformat(pub)
            except ValueError:
                continue
        elif isinstance(pub, date):
            pub_date = pub
        else:
            continue
        items.append(
            TrendItem(
                title=str(entry.get("title", "")).strip(),
                url=str(entry.get("url", "")).strip(),
                published_at=pub_date,
                keywords=[str(k) for k in entry.get("keywords", []) if k],
                weight=float(entry.get("weight", 1.0)),
            )
        )
    return items


def score_trends(items: list[TrendItem], *, lookback_days: int = 14) -> list[TrendItem]:
    """Retourne les items dans la fenêtre, triés par score décroissant."""
    cutoff = datetime.now(UTC).date() - timedelta(days=lookback_days)
    fresh = [i for i in items if i.published_at >= cutoff]
    return sorted(fresh, key=lambda i: i.score, reverse=True)


__all__ = ["DEFAULT_SOURCES", "TrendItem", "load_trend_sources", "score_trends"]
