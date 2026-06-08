"""PressReleaseDrafter — drafte un communiqué de presse standard.

Lit ``data/comm/press_releases/queue.yaml`` qui liste les annonces à
traiter (statuts: ``queued``). Pour chaque annonce, drafte un communiqué
structuré dans ``data/comm/press_releases/<slug>.md`` selon le canevas :

- Titre (≤ 60 chars)
- Sous-titre (résumé en 1 phrase)
- Dazibao 5W (qui / quoi / où / quand / pourquoi)
- Contexte
- Citation founder (placeholder à remplir si vide)
- Boilerplate Omnividens
- Contacts presse
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.comm.brand import BRAND_TAGLINE, CANONICAL_DOMAIN
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

QUEUE_PATH = REPO_ROOT / "data" / "comm" / "press_releases" / "queue.yaml"
RELEASES_DIR = REPO_ROOT / "data" / "comm" / "press_releases"


@dataclass
class ReleaseRequest:
    slug: str
    title: str
    angle: str  # 'product' | 'finance' | 'milestone' | 'crisis_response'
    summary: str
    body: str  # corpus en clair, le founder remplit
    founder_quote: str = ""
    status: str = "queued"


@dataclass
class DraftStats:
    queued: int = 0
    drafted: int = 0
    skipped_existing: int = 0

    def summary(self) -> str:
        return f"queued={self.queued} drafted={self.drafted} existing={self.skipped_existing}"


def load_queue(path: Path | None = None) -> list[ReleaseRequest]:
    path = path or QUEUE_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[ReleaseRequest] = []
    for entry in raw.get("releases", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                ReleaseRequest(
                    slug=str(entry["slug"]),
                    title=str(entry["title"]),
                    angle=str(entry.get("angle", "product")),
                    summary=str(entry.get("summary", "")),
                    body=str(entry.get("body", "")),
                    founder_quote=str(entry.get("founder_quote", "")),
                    status=str(entry.get("status", "queued")),
                )
            )
        except KeyError:
            continue
    return out


def draft_release(req: ReleaseRequest, *, now: datetime | None = None) -> str:
    """Drafte un communiqué Markdown structuré."""
    now = now or datetime.now(UTC)
    quote = req.founder_quote or "_(citation founder à compléter)_"
    return (
        f"---\nstatus: drafted\nslug: {req.slug}\nangle: {req.angle}\n"
        f"date: {now.date().isoformat()}\n---\n\n"
        f"# {req.title}\n\n"
        f"_Communiqué de presse Omnividens — {now.date().isoformat()}, Paris._\n\n"
        f"**{req.summary}**\n\n"
        f"## Contexte\n\n{req.body or '_à compléter_'}\n\n"
        f"## Citation\n\n> {quote}\n\n— Founder, Omnividens\n\n"
        f"## À propos d'Omnividens\n\n"
        f"Omnividens développe Argos, plateforme de pentest BtoB pour PME tech "
        f"françaises. {BRAND_TAGLINE} En ligne sur https://{CANONICAL_DOMAIN}.\n\n"
        f"## Contacts presse\n\n"
        f"- Founder Omnividens — contact@{CANONICAL_DOMAIN}\n"
        f"- Site : https://{CANONICAL_DOMAIN}/presse\n"
    )


def build_release_embed(stats: DraftStats) -> Embed:
    color = GREEN if stats.drafted > 0 or stats.queued == 0 else YELLOW
    return Embed(
        title=f"Argos — PressReleaseDrafter ({stats.drafted} draftés)",
        color=color,
        fields=[
            EmbedField(name="En queue", value=str(stats.queued), inline=True),
            EmbedField(name="Draftés", value=str(stats.drafted), inline=True),
            EmbedField(name="Déjà draftés", value=str(stats.skipped_existing), inline=True),
        ],
        footer="Argos Ops • PressReleaseDrafter",
    )


class PressReleaseDrafter(BaseAgent):
    """Drafte un communiqué de presse structuré — validation founder requise."""

    name = "PressReleaseDrafter"
    command = "/draft-press-release"
    breaker_name = "PressReleaseDrafter"
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        queue = load_queue()
        queued = [r for r in queue if r.status == "queued"]
        stats = DraftStats(queued=len(queued))

        RELEASES_DIR.mkdir(parents=True, exist_ok=True)
        for req in queued:
            path = RELEASES_DIR / f"{req.slug}.md"
            if path.exists():
                stats.skipped_existing += 1
                continue
            try:
                path.write_text(draft_release(req), encoding="utf-8")
                stats.drafted += 1
            except OSError as exc:
                logger.warning(f"PressReleaseDrafter — écriture {req.slug} : {exc}")

        settings = get_settings()
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None and stats.drafted > 0:
            try:
                await send_embed(webhook, build_release_embed(stats))
            except Exception as exc:
                logger.warning(f"PressReleaseDrafter — notif Discord : {exc}")

        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=[
                IOItem(
                    label="Queue communiqués",
                    kind="file",
                    detail=f"{stats.queued} en statut queued",
                    ref="data/comm/press_releases/queue.yaml",
                    count=len(queue),
                )
            ],
            outputs=[
                IOItem(
                    label="Communiqués draftés",
                    kind="draft",
                    detail=f"{stats.skipped_existing} déjà draftés (skip)",
                    ref="data/comm/press_releases/",
                    count=stats.drafted,
                )
            ],
        )


__all__ = [
    "QUEUE_PATH",
    "RELEASES_DIR",
    "DraftStats",
    "PressReleaseDrafter",
    "ReleaseRequest",
    "build_release_embed",
    "draft_release",
    "load_queue",
]
