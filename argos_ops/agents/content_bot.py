"""ContentBot full (P9) — publie les drafts validés sur LinkedIn / Mastodon.

Pipeline cron (toutes les 2 h en journée) :

1. Scan ``data/content/drafts/`` pour les fichiers ``status: validated``
   dont ``scheduled_for`` <= now
2. Cap journalier ``content_daily_max_per_channel`` par canal
3. Dispatch via :func:`argos_ops.social.publisher.publish_draft`
4. Déplace le draft vers ``data/content/published/`` (live ou shadow)
5. Notif Discord récap

Live mode = posting réel sur les APIs. Shadow mode = simulation
(credentials API absents OU ``CONTENT_LIVE_MODE`` non activé). Le passage
en live est gouverné par D-024 (LinkedIn API token) et D-025 (Mastodon
access token).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.social.publisher import PublishResult, find_ready_drafts, publish_draft


@dataclass
class ContentRunStats:
    """Récap d'un run ContentBot."""

    ready: int = 0
    published_live: int = 0
    published_shadow: int = 0
    skipped_daily_cap: int = 0
    failures: int = 0
    by_channel: Counter[str] = field(default_factory=Counter)

    def summary(self) -> str:
        return (
            f"ready={self.ready} live={self.published_live} shadow={self.published_shadow} "
            f"skipped={self.skipped_daily_cap} failures={self.failures}"
        )


def build_content_embed(stats: ContentRunStats, live_mode: bool) -> Embed:
    """Embed Discord récap ContentBot."""
    color = YELLOW if stats.failures > 0 else GREEN
    mode = "live" if live_mode else "shadow"
    fields = [
        EmbedField(name="Drafts prêts", value=str(stats.ready), inline=True),
        EmbedField(name="Publiés live", value=str(stats.published_live), inline=True),
        EmbedField(name="Publiés shadow", value=str(stats.published_shadow), inline=True),
        EmbedField(name="Skippés (cap)", value=str(stats.skipped_daily_cap), inline=True),
        EmbedField(name="Échecs", value=str(stats.failures), inline=True),
        EmbedField(name="Mode", value=mode, inline=True),
    ]
    if stats.by_channel:
        breakdown = ", ".join(f"{ch}={n}" for ch, n in stats.by_channel.most_common())
        fields.append(EmbedField(name="Par canal", value=breakdown, inline=False))

    return Embed(
        title=f"Argos — ContentBot ({stats.published_live + stats.published_shadow} posts)",
        color=color,
        fields=fields,
        footer="Argos Ops • ContentBot",
    )


class ContentBot(BaseAgent):
    """Publie les drafts sociaux validés sur LinkedIn / Mastodon."""

    name = "ContentBot"
    command = "/publish-content"
    breaker_name = "ContentBot"
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        settings = get_settings()
        ready = find_ready_drafts()
        stats = ContentRunStats(ready=len(ready))

        if not ready:
            logger.info("ContentBot — aucun draft prêt à publier")
            return RunResult(status="success", output_summary=stats.summary())

        published_today = Counter[str]()
        for draft in ready:
            try:
                pub: PublishResult = await publish_draft(draft)
            except Exception as exc:
                logger.exception(f"ContentBot — échec publication {draft.name} : {exc}")
                stats.failures += 1
                continue

            channel = pub.platform
            if published_today[channel] >= settings.content_daily_max_per_channel:
                stats.skipped_daily_cap += 1
                continue

            if pub.status == "published":
                stats.published_live += 1
                published_today[channel] += 1
                stats.by_channel[channel] += 1
            elif pub.status == "shadow":
                stats.published_shadow += 1
                published_today[channel] += 1
                stats.by_channel[channel] += 1
            else:
                stats.failures += 1
                logger.warning(f"ContentBot — {draft.name} status={pub.status} err={pub.error}")

        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None:
            live_mode = settings.linkedin_api_token is not None or (
                settings.mastodon_access_token is not None
            )
            try:
                await send_embed(webhook, build_content_embed(stats, live_mode))
            except Exception as exc:
                logger.warning(f"ContentBot — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = ["ContentBot", "ContentRunStats", "build_content_embed"]
