"""WebinarPromoter — drafte les assets de promotion d'un webinar Argos.

Lit ``data/webinars/upcoming.yaml``, pour chaque webinar dont la date
est dans les 14 jours et qui n'a pas encore d'assets, drafte :

- 3 posts sociaux échelonnés (J-14, J-7, J-1) dans ``data/content/drafts/``
- 1 email teaser dans ``data/webinars/<slug>/email_teaser.md``
- 1 fiche replay vide dans ``data/webinars/<slug>/replay_edit.md`` à remplir
  après le live

Pas d'envoi automatique : tout passe par /publish-content et /draft-newsletter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

WEBINARS_PATH = REPO_ROOT / "data" / "webinars" / "upcoming.yaml"
WEBINARS_DIR = REPO_ROOT / "data" / "webinars"
DRAFTS_DIR = REPO_ROOT / "data" / "content" / "drafts"


@dataclass
class Webinar:
    slug: str
    title: str
    date: date
    register_url: str
    speaker: str = "Founder Argos"
    description: str = ""


@dataclass
class PromotionStats:
    upcoming: int = 0
    drafted: int = 0
    skipped_existing: int = 0
    new_assets: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"upcoming={self.upcoming} drafted={self.drafted} skipped={self.skipped_existing}"


def load_upcoming(path: Path | None = None) -> list[Webinar]:
    path = path or WEBINARS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[Webinar] = []
    for entry in raw.get("webinars", []):
        if not isinstance(entry, dict):
            continue
        d = entry.get("date")
        if isinstance(d, str):
            try:
                d_date = date.fromisoformat(d)
            except ValueError:
                continue
        elif isinstance(d, date):
            d_date = d
        else:
            continue
        try:
            out.append(
                Webinar(
                    slug=str(entry["slug"]),
                    title=str(entry["title"]),
                    date=d_date,
                    register_url=str(entry.get("register_url", "")),
                    speaker=str(entry.get("speaker", "Founder Argos")),
                    description=str(entry.get("description", "")),
                )
            )
        except KeyError:
            continue
    return out


def _post_body(webinar: Webinar, when_label: str) -> str:
    return (
        f"---\nstatus: ready_to_validate\nchannel: linkedin\n"
        f"scheduled_for: \nwebinar_slug: {webinar.slug}\n---\n\n"
        f"{when_label} — webinar **{webinar.title}** par {webinar.speaker} "
        f"({webinar.date.isoformat()}).\n\n"
        f"{webinar.description}\n\n"
        f"Inscription : {webinar.register_url}\n"
    )


def draft_assets(webinar: Webinar, *, today: date | None = None) -> list[Path]:
    today = today or datetime.now(UTC).date()
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    base = WEBINARS_DIR / webinar.slug
    base.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    schedule = [
        (today - timedelta(days=0), "J-14", f"webinar-{webinar.slug}-j14.md"),
        (today - timedelta(days=0), "J-7", f"webinar-{webinar.slug}-j7.md"),
        (today - timedelta(days=0), "J-1", f"webinar-{webinar.slug}-j1.md"),
    ]
    for _, label, fname in schedule:
        path = DRAFTS_DIR / fname
        if path.exists():
            continue
        path.write_text(_post_body(webinar, label), encoding="utf-8")
        created.append(path)

    teaser = base / "email_teaser.md"
    if not teaser.exists():
        teaser.write_text(
            f"# Email teaser — {webinar.title}\n\n"
            f"Date : {webinar.date.isoformat()}\n"
            f"Inscription : {webinar.register_url}\n\n"
            f"Bonjour,\n\nÀ remplir.\n",
            encoding="utf-8",
        )
        created.append(teaser)

    replay = base / "replay_edit.md"
    if not replay.exists():
        replay.write_text(
            f"# Replay edit — {webinar.title}\n\n"
            f"À compléter après le live :\n"
            f"- Lien vidéo brute\n- Timestamps des temps forts\n"
            f"- 1 quote à reposter sur LinkedIn\n",
            encoding="utf-8",
        )
        created.append(replay)
    return created


def build_promoter_embed(stats: PromotionStats) -> Embed:
    color = GREEN if stats.drafted > 0 or stats.upcoming == 0 else YELLOW
    return Embed(
        title="Argos — WebinarPromoter",
        color=color,
        fields=[
            EmbedField(name="À venir", value=str(stats.upcoming), inline=True),
            EmbedField(name="Assets draftés", value=str(stats.drafted), inline=True),
            EmbedField(name="Déjà draftés", value=str(stats.skipped_existing), inline=True),
        ],
        footer="Argos Ops • WebinarPromoter",
    )


class WebinarPromoter(BaseAgent):
    """Drafte les assets promo d'un webinar (3 posts + email + fiche replay)."""

    name = "WebinarPromoter"
    command = "/promote-webinar"
    breaker_name = "WebinarPromoter"

    async def run(self) -> RunResult:
        today = datetime.now(UTC).date()
        webinars = load_upcoming()
        upcoming = [w for w in webinars if today <= w.date <= today + timedelta(days=14)]
        stats = PromotionStats(upcoming=len(upcoming))

        for w in upcoming:
            created = draft_assets(w, today=today)
            if created:
                stats.drafted += len(created)
                stats.new_assets.extend(p.name for p in created)
            else:
                stats.skipped_existing += 1

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and stats.upcoming > 0:
            try:
                await send_embed(webhook, build_promoter_embed(stats))
            except Exception as exc:
                logger.warning(f"WebinarPromoter — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DRAFTS_DIR",
    "WEBINARS_DIR",
    "WEBINARS_PATH",
    "PromotionStats",
    "Webinar",
    "WebinarPromoter",
    "build_promoter_embed",
    "draft_assets",
    "load_upcoming",
]
