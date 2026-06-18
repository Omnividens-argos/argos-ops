"""``SocialAnalyticsScript`` — reporting engagement social 7j (Marketing, archi v2).

Porté depuis ``argos_ops.agents.social_analytics``. Bras déterministe :

1. lit ``data/social/engagement.yaml`` (founder-maintained / export manuel) via
   le module domaine :mod:`argos_ops.marketing.analytics` ;
2. agrège l'engagement par canal sur la fenêtre (7j) ;
3. écrit un fait par canal dans **sa propre mémoire** (``kind="engagement"``),
   flaggé ``important`` si le signal est faible (CTR < 1 % ou ER < 2 %).

Pas de Discord, pas de DB (D-017) : le :class:`MarketingAgent` lit cette mémoire.
Idempotent : un canal re-agrégé sur les mêmes posts donne le même corps de fait.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from argos_ops.marketing.analytics import EngagementMetrics, load_engagement_window
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

_WINDOW_DAYS = 7
_WEAK_CTR = 0.01
_WEAK_ER = 0.02


@dataclass
class ChannelAgg:
    """Engagement agrégé d'un canal sur la fenêtre. Réutilisé par le cockpit."""

    posts: int = 0
    impressions: int = 0
    engagements: int = 0
    clicks: int = 0

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0

    @property
    def engagement_rate(self) -> float:
        return self.engagements / self.impressions if self.impressions else 0.0

    @property
    def is_weak(self) -> bool:
        return self.posts > 0 and (self.ctr < _WEAK_CTR or self.engagement_rate < _WEAK_ER)


def aggregate_engagement(metrics: list[EngagementMetrics]) -> dict[str, ChannelAgg]:
    """Agrège des métriques par canal (``platform``)."""
    buckets: dict[str, ChannelAgg] = defaultdict(ChannelAgg)
    for m in metrics:
        agg = buckets[m.platform]
        agg.posts += 1
        agg.impressions += m.impressions
        agg.engagements += m.engagements
        agg.clicks += m.clicks
    return dict(buckets)


class SocialAnalyticsScript(BaseScript):
    """Agrège l'engagement social par canal et le mémorise (``kind="engagement"``)."""

    pole = "marketing"
    name = "social_analytics"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        engagement_path: Path | None = None,
        window_days: int = _WINDOW_DAYS,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._engagement_path = engagement_path
        self._window_days = window_days

    async def run(self) -> ScriptResult:
        metrics = load_engagement_window(days=self._window_days, path=self._engagement_path)
        by_channel = aggregate_engagement(metrics)

        written = []
        for channel, agg in sorted(by_channel.items()):
            record = await self.write_memory(
                (
                    f"Engagement {channel} ({self._window_days}j) : {agg.posts} post(s), "
                    f"CTR {agg.ctr * 100:.1f}%, ER {agg.engagement_rate * 100:.1f}%"
                ),
                kind="engagement",
                tags=(channel, "weak") if agg.is_weak else (channel,),
                important=agg.is_weak,
            )
            written.append(record)

        weak = sum(1 for a in by_channel.values() if a.is_weak)
        return ScriptResult(
            status="success",
            summary=(
                f"{len(written)} canal/canaux mesuré(s) sur {len(metrics)} post(s) — "
                f"{weak} signal(aux) faible(s)"
            ),
            written=written,
        )


__all__ = ["ChannelAgg", "SocialAnalyticsScript", "aggregate_engagement"]
