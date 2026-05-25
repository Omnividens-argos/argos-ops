"""SocialAnalytics — reporting hebdo engagement par canal.

Lit ``data/social/engagement.yaml`` (alimenté manuellement ou via APIs
analytics quand tokens disponibles), agrège sur 7 jours par canal et
push un récap Discord. Alerte (jaune) si CTR < 1% ou ER < 2% en moyenne.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import get_settings
from argos_ops.marketing.analytics import EngagementMetrics, load_engagement_window
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed


@dataclass
class ChannelReport:
    channel: str
    posts: int = 0
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


@dataclass
class AnalyticsRun:
    window_days: int
    by_channel: dict[str, ChannelReport] = field(default_factory=dict)

    @property
    def has_weak_signal(self) -> bool:
        for r in self.by_channel.values():
            if r.posts == 0:
                continue
            if r.ctr < 0.01 or r.engagement_rate < 0.02:
                return True
        return False

    def summary(self) -> str:
        parts = []
        for ch, r in sorted(self.by_channel.items()):
            parts.append(f"{ch}: {r.posts}posts ctr={r.ctr * 100:.1f}%")
        return " | ".join(parts) if parts else "no data"


def aggregate(metrics: list[EngagementMetrics], *, window_days: int = 7) -> AnalyticsRun:
    run = AnalyticsRun(window_days=window_days)
    buckets: dict[str, ChannelReport] = defaultdict(lambda: ChannelReport(channel=""))
    for m in metrics:
        bucket = buckets[m.platform]
        bucket.channel = m.platform
        bucket.posts += 1
        bucket.impressions += m.impressions
        bucket.engagements += m.engagements
        bucket.clicks += m.clicks
    run.by_channel = dict(buckets)
    return run


def build_analytics_embed(run: AnalyticsRun) -> Embed:
    color = YELLOW if run.has_weak_signal else GREEN
    fields: list[EmbedField] = []
    for ch, r in sorted(run.by_channel.items()):
        fields.append(
            EmbedField(
                name=ch,
                value=(
                    f"{r.posts} posts · {r.impressions} imp · "
                    f"CTR {r.ctr * 100:.1f}% · ER {r.engagement_rate * 100:.1f}%"
                ),
                inline=False,
            )
        )
    if not fields:
        fields.append(EmbedField(name="Données", value="aucune mesure dans la fenêtre", inline=False))
    return Embed(
        title=f"Argos — SocialAnalytics ({run.window_days}j)",
        color=color,
        fields=fields,
        footer="Argos Ops • SocialAnalytics",
    )


class SocialAnalytics(BaseAgent):
    """Reporting hebdo engagement par canal social."""

    name = "SocialAnalytics"
    command = "/run-social-analytics"
    breaker_name = "SocialAnalytics"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        metrics = load_engagement_window(days=7)
        run = aggregate(metrics, window_days=7)

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and run.by_channel:
            try:
                await send_embed(webhook, build_analytics_embed(run))
            except Exception as exc:
                logger.warning(f"SocialAnalytics — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=run.summary())


__all__ = ["AnalyticsRun", "ChannelReport", "SocialAnalytics", "aggregate", "build_analytics_embed"]
