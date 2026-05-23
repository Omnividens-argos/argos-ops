"""TestimonialHunter — drafte les demandes de verbatim post-NPS positif.

Pipeline shadow strict (Sprint 12) :

1. Lit ``data/crm/nps_responses.yaml`` (alimenté manuellement ou par
   ReviewBot/NPSCollector futurs)
2. Filtre les réponses ``score >= 9`` ET non encore traitées
3. Pour chaque client, drafte un email de demande de verbatim court dans
   ``data/marketing/testimonial_drafts/<slug>.md``
4. Pas d'envoi — humain-in-the-loop via zimbra-ops après validation

Cap journalier : max 5 demandes / run pour ne pas saturer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

NPS_PATH = REPO_ROOT / "data" / "crm" / "nps_responses.yaml"
DRAFTS_DIR = REPO_ROOT / "data" / "marketing" / "testimonial_drafts"
DAILY_MAX = 5


@dataclass
class NpsHit:
    slug: str
    contact_name: str
    contact_email: str
    company: str
    score: int
    comment: str = ""


@dataclass
class HunterStats:
    total_hits: int = 0
    high_score_hits: int = 0
    drafted: int = 0
    skipped_existing: int = 0
    new_slugs: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"hits={self.total_hits} promoters={self.high_score_hits} "
            f"drafted={self.drafted} skipped={self.skipped_existing}"
        )


def load_nps(path: Path | None = None) -> list[NpsHit]:
    path = path or NPS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[NpsHit] = []
    for entry in raw.get("responses", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                NpsHit(
                    slug=str(entry["slug"]),
                    contact_name=str(entry.get("contact_name", "")),
                    contact_email=str(entry.get("contact_email", "")),
                    company=str(entry.get("company", "")),
                    score=int(entry["score"]),
                    comment=str(entry.get("comment", "")),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def draft_request(hit: NpsHit) -> str:
    quote_block = ""
    if hit.comment:
        quote_block = f'\n> « {hit.comment} »\n'
    return (
        f"---\nstatus: drafted\nslug: {hit.slug}\n"
        f"contact_email: {hit.contact_email}\n"
        f"contact_name: {hit.contact_name}\n"
        f"company: {hit.company}\nnps_score: {hit.score}\n---\n\n"
        f"Bonjour {hit.contact_name},\n\n"
        f"Merci pour votre score NPS de {hit.score}/10 sur Argos.{quote_block}\n"
        f"Auriez-vous 5 min pour qu'on fixe par écrit votre retour en 2-3 "
        f"phrases ? On le publierait sur omnividens.fr avec votre prénom + "
        f"votre rôle chez {hit.company} (et avec votre validation explicite "
        f"avant mise en ligne).\n\n"
        f"Si oui, répondez-moi simplement « ok » et je revous envoie 2 "
        f"questions courtes. Si non, aucun souci.\n\n"
        f"Bien cordialement,\n"
        f"L'équipe Argos\n"
        f"Argos — on scanne, vous corrigez.\n"
        f"Email rédigé par notre assistant Argos Ops.\n"
    )


def build_hunter_embed(stats: HunterStats) -> Embed:
    color = GREEN if stats.drafted > 0 else YELLOW
    return Embed(
        title=f"Argos — TestimonialHunter ({stats.drafted} demandes draftées)",
        color=color,
        fields=[
            EmbedField(name="NPS lus", value=str(stats.total_hits), inline=True),
            EmbedField(name="Promoteurs (≥9)", value=str(stats.high_score_hits), inline=True),
            EmbedField(name="Déjà draftés", value=str(stats.skipped_existing), inline=True),
        ],
        footer="Argos Ops • TestimonialHunter",
    )


class TestimonialHunter(BaseAgent):
    """Drafte les demandes de verbatim post-NPS pour les promoteurs."""

    name = "TestimonialHunter"
    command = "/draft-testimonial-request"
    breaker_name = "TestimonialHunter"

    async def run(self) -> RunResult:
        nps = load_nps()
        stats = HunterStats(total_hits=len(nps))
        promoters = [n for n in nps if n.score >= 9 and n.contact_email]
        stats.high_score_hits = len(promoters)

        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        for hit in promoters[:DAILY_MAX]:
            path = DRAFTS_DIR / f"{hit.slug}.md"
            if path.exists():
                stats.skipped_existing += 1
                continue
            try:
                path.write_text(draft_request(hit), encoding="utf-8")
                stats.drafted += 1
                stats.new_slugs.append(hit.slug)
            except OSError as exc:
                logger.warning(f"TestimonialHunter — écriture {hit.slug} : {exc}")

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and (stats.drafted or stats.high_score_hits):
            try:
                await send_embed(webhook, build_hunter_embed(stats))
            except Exception as exc:
                logger.warning(f"TestimonialHunter — notif Discord : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DAILY_MAX",
    "DRAFTS_DIR",
    "NPS_PATH",
    "HunterStats",
    "NpsHit",
    "TestimonialHunter",
    "build_hunter_embed",
    "draft_request",
    "load_nps",
]
