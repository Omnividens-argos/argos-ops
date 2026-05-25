"""BacklinkOutreach — prospecte sites cyber pour échanges de liens (SEO off-page).

Pipeline shadow strict (Sprint 12) :

1. Lit ``data/seo/backlink_targets.yaml`` (liste maintenue par le founder
   ou enrichie par TrendSpotter / veille concurrence)
2. Filtre les cibles ``status: queued`` non encore contactées
3. Pour chaque cible, drafte un email outbound personnalisé dans
   ``data/seo/backlink_drafts/<slug>.md`` (frontmatter : status: drafted,
   target_url, target_domain, contact_email, body)
4. Pas d'envoi — humain-in-the-loop via zimbra-ops après validation

Garde-fou volume : on ne drafte pas plus de
``BACKLINK_DAILY_MAX`` (défaut 5) prospects par run pour ne pas inonder
la queue de drafts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

TARGETS_PATH = REPO_ROOT / "data" / "seo" / "backlink_targets.yaml"
DRAFTS_DIR = REPO_ROOT / "data" / "seo" / "backlink_drafts"
DAILY_MAX = 5


@dataclass
class BacklinkTarget:
    slug: str
    site_url: str
    contact_email: str
    angle: str  # ex : "ressource invitée", "interview", "guest post"
    status: str = "queued"


@dataclass
class OutreachStats:
    targets_read: int = 0
    drafted: int = 0
    skipped_existing: int = 0
    skipped_invalid: int = 0
    new_slugs: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"read={self.targets_read} drafted={self.drafted} "
            f"skipped_existing={self.skipped_existing} invalid={self.skipped_invalid}"
        )


def load_targets(path: Path | None = None) -> list[BacklinkTarget]:
    path = path or TARGETS_PATH
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[BacklinkTarget] = []
    for entry in data.get("targets", []):
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug", "")).strip()
        site = str(entry.get("site_url", "")).strip()
        email = str(entry.get("contact_email", "")).strip()
        angle = str(entry.get("angle", "ressource invitée")).strip()
        if not (slug and site and email and "@" in email):
            continue
        out.append(
            BacklinkTarget(
                slug=slug,
                site_url=site,
                contact_email=email,
                angle=angle,
                status=str(entry.get("status", "queued")),
            )
        )
    return out


def draft_email(target: BacklinkTarget) -> str:
    """Drafte le body d'un email outbound pour un échange de lien."""
    return (
        f"---\nstatus: drafted\nslug: {target.slug}\n"
        f"site_url: {target.site_url}\n"
        f"contact_email: {target.contact_email}\n"
        f"angle: {target.angle}\n---\n\n"
        f"Bonjour,\n\n"
        f"Je suis le founder d'Argos (omnividens.fr), pentest BtoB pour PME tech "
        f"françaises. J'ai lu votre travail sur {target.site_url} et je pense "
        f"qu'on peut se rendre service mutuellement sur l'angle « {target.angle} ».\n\n"
        f"Concrètement, je vous propose :\n"
        f"- Une contribution écrite (étude de cas anonymisée, retour terrain "
        f"pentest, position sur une CVE récente) en échange d'un lien naturel "
        f"vers omnividens.fr.\n"
        f"- OU une mise en avant croisée si vous avez un sujet où Argos peut "
        f"apporter une donnée chiffrée.\n\n"
        f"Ouvert à discuter le format. Si non pertinent : un simple « pas pour "
        f"nous » suffit, je n'insiste pas.\n\n"
        f"Bien cordialement,\n"
        f"L'équipe Argos\n"
        f"Argos — on scanne, vous corrigez.\n"
        f"https://omnividens.fr\n"
        f"Email rédigé par notre assistant Argos Ops.\n"
    )


def build_outreach_embed(stats: OutreachStats) -> Embed:
    color = YELLOW if stats.skipped_invalid > 0 else GREEN
    fields = [
        EmbedField(name="Lus", value=str(stats.targets_read), inline=True),
        EmbedField(name="Draftés", value=str(stats.drafted), inline=True),
        EmbedField(name="Déjà draftés", value=str(stats.skipped_existing), inline=True),
        EmbedField(name="Invalides", value=str(stats.skipped_invalid), inline=True),
    ]
    if stats.new_slugs:
        fields.append(
            EmbedField(
                name="Nouveaux drafts",
                value="\n".join(f"• {s}" for s in stats.new_slugs[:5]),
                inline=False,
            )
        )
    return Embed(
        title=f"Argos — BacklinkOutreach ({stats.drafted} draftés)",
        color=color,
        fields=fields,
        footer="Argos Ops • BacklinkOutreach",
    )


class BacklinkOutreach(BaseAgent):
    """Drafte des cold emails de demande de backlink — pas d'envoi auto."""

    name = "BacklinkOutreach"
    command = "/run-backlink-outreach"
    breaker_name = "BacklinkOutreach"
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        targets = load_targets()
        stats = OutreachStats(targets_read=len(targets))

        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        queued = [t for t in targets if t.status == "queued"]
        for target in queued[:DAILY_MAX]:
            out_path = DRAFTS_DIR / f"{target.slug}.md"
            if out_path.exists():
                stats.skipped_existing += 1
                continue
            try:
                out_path.write_text(draft_email(target), encoding="utf-8")
                stats.drafted += 1
                stats.new_slugs.append(target.slug)
            except OSError as exc:
                logger.warning(f"BacklinkOutreach — échec écriture {target.slug} : {exc}")
                stats.skipped_invalid += 1

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and (stats.drafted or stats.skipped_invalid):
            try:
                await send_embed(webhook, build_outreach_embed(stats))
            except Exception as exc:
                logger.warning(f"BacklinkOutreach — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DAILY_MAX",
    "DRAFTS_DIR",
    "TARGETS_PATH",
    "BacklinkOutreach",
    "BacklinkTarget",
    "OutreachStats",
    "build_outreach_embed",
    "draft_email",
    "load_targets",
]
