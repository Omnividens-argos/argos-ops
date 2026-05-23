"""Lecture des métriques d'engagement social pour SocialAnalytics.

Source : ``data/social/engagement.yaml`` — alimenté par export manuel
LinkedIn (CSV → YAML) ou via les APIs analytics si tokens disponibles.

Format ::

    posts:
      - posted_at: "2026-05-15T08:30:00Z"
        platform: linkedin
        url: "https://linkedin.com/..."
        impressions: 1240
        engagements: 87
        clicks: 12
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT

DEFAULT_ENGAGEMENT = REPO_ROOT / "data" / "social" / "engagement.yaml"


@dataclass
class EngagementMetrics:
    posted_at: datetime
    platform: str
    url: str
    impressions: int = 0
    engagements: int = 0
    clicks: int = 0

    @property
    def ctr(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.clicks / self.impressions

    @property
    def engagement_rate(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.engagements / self.impressions


def load_engagement_window(
    *, days: int = 7, path: Path | None = None
) -> list[EngagementMetrics]:
    """Charge les métriques publiées dans la fenêtre `days` derniers jours."""
    path = path or DEFAULT_ENGAGEMENT
    if not path.exists():
        logger.info(f"SocialAnalytics — fichier {path} absent")
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cutoff = datetime.now(UTC) - timedelta(days=days)
    out: list[EngagementMetrics] = []
    for entry in raw.get("posts", []):
        if not isinstance(entry, dict):
            continue
        ts = entry.get("posted_at")
        if isinstance(ts, str):
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
        elif isinstance(ts, datetime):
            ts_dt = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        else:
            continue
        if ts_dt < cutoff:
            continue
        out.append(
            EngagementMetrics(
                posted_at=ts_dt,
                platform=str(entry.get("platform", "unknown")),
                url=str(entry.get("url", "")),
                impressions=int(entry.get("impressions", 0)),
                engagements=int(entry.get("engagements", 0)),
                clicks=int(entry.get("clicks", 0)),
            )
        )
    return out


__all__ = ["DEFAULT_ENGAGEMENT", "EngagementMetrics", "load_engagement_window"]
