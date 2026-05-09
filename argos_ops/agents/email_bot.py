"""EmailBot — ingestion automatique de la boîte ``contact@omnividens.fr``.

Pattern (D-017) : ce module ne fait QUE de la plomberie. Pas d'appel LLM
ici. La cron ``*/15`` tire les emails non lus, les logge dans le CRM,
positionne ``\\Seen`` et notifie Discord. Le drafting + envoi se font
ensuite via le slash command ``/check-emails`` (Claude Code Pro Max +
skills) en mode humain-in-the-loop.

Cf. P5 du plan, alignement D-018 (OVH Zimbra IMAP/SMTP).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import get_settings
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import Company, Lead
from argos_ops.crm.repository import (
    add_interaction,
    get_or_create_company,
    get_or_create_lead,
)
from argos_ops.integrations.zimbra import (
    EmailMessage,
    extract_domain,
    fetch_unread,
    is_noreply,
    mark_seen,
)
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)


@dataclass
class IngestStats:
    """Photo d'un run d'EmailBot — sérialisé dans ``agent_runs.output_summary``."""

    fetched: int = 0
    ingested: int = 0
    skipped_noreply: int = 0
    new_leads: int = 0
    new_companies: int = 0
    failures: int = 0
    subjects: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"fetched={self.fetched} ingested={self.ingested} "
            f"new_leads={self.new_leads} new_companies={self.new_companies} "
            f"skipped_noreply={self.skipped_noreply} failures={self.failures}"
        )


# =============================================================================
# Persistence d'un email
# =============================================================================
async def _persist_email(session: AsyncSession, msg: EmailMessage, stats: IngestStats) -> None:
    """Crée company + lead + interaction. Mute ``stats`` au passage."""
    company_id: int | None = None
    domain = extract_domain(msg.from_email)
    if domain:
        existing_company = (
            await session.execute(select(Company).where(col(Company.domain) == domain))
        ).scalar_one_or_none()
        company = await get_or_create_company(session, domain=domain, source="email_inbound")
        if existing_company is None:
            stats.new_companies += 1
        company_id = company.id

    existing_lead = (
        await session.execute(select(Lead).where(col(Lead.email) == msg.from_email))
    ).scalar_one_or_none()
    lead = await get_or_create_lead(
        session,
        email=msg.from_email,
        company_id=company_id,
        full_name=msg.from_name,
    )
    if existing_lead is None:
        stats.new_leads += 1

    await add_interaction(
        session,
        lead_id=lead.id,
        channel="email",
        direction="in",
        agent_name="EmailBot",
        subject=msg.subject,
        body=msg.body_text or msg.body_html or "",
    )


# =============================================================================
# Notification Discord
# =============================================================================
def build_inbox_embed(stats: IngestStats) -> Embed:
    """Embed Discord récap d'un run EmailBot."""
    color = YELLOW if stats.ingested > 0 else GREEN
    fields: list[EmbedField] = [
        EmbedField(name="Récupérés", value=str(stats.fetched), inline=True),
        EmbedField(name="Ingérés", value=str(stats.ingested), inline=True),
        EmbedField(name="Nouveaux leads", value=str(stats.new_leads), inline=True),
        EmbedField(name="Nouvelles companies", value=str(stats.new_companies), inline=True),
        EmbedField(name="Skip noreply", value=str(stats.skipped_noreply), inline=True),
        EmbedField(name="Échecs", value=str(stats.failures), inline=True),
    ]
    if stats.subjects:
        preview_lines = [f"• {s[:80]}" for s in stats.subjects[:5]]
        if len(stats.subjects) > 5:
            preview_lines.append(f"... +{len(stats.subjects) - 5} autres")
        fields.append(EmbedField(name="Sujets", value="\n".join(preview_lines), inline=False))

    desc = (
        "Lance `/check-emails` dans Claude Code pour drafter les réponses."
        if stats.ingested > 0
        else "Aucun email à traiter."
    )
    return Embed(
        title=f"Argos — Inbox ({stats.ingested} nouveaux)",
        description=desc,
        color=color,
        fields=fields,
        footer="Argos Ops • EmailBot",
    )


# =============================================================================
# Agent
# =============================================================================
class EmailBot(BaseAgent):
    """Ingestion async de l'INBOX OVH Zimbra. Pas de drafting ici."""

    name = "EmailBot"
    command = "/run-email-bot"
    breaker_name = "EmailBot"

    async def run(self) -> RunResult:
        settings = get_settings()
        if settings.email_user is None or settings.email_password is None:
            return RunResult(
                status="failed",
                error="EMAIL_USER ou EMAIL_PASSWORD manquant dans .env.local — voir D-005",
            )

        try:
            messages = await fetch_unread(
                host=settings.email_imap_host,
                port=settings.email_imap_port,
                user=settings.email_user,
                password=settings.email_password,
                limit=50,
            )
        except Exception as exc:
            logger.error(f"EmailBot — IMAP fetch a échoué : {type(exc).__name__}")
            return RunResult(status="failed", error=f"IMAP fetch: {type(exc).__name__}: {exc}")

        stats = IngestStats(fetched=len(messages))
        logger.info(f"EmailBot — {len(messages)} email(s) non lu(s) récupéré(s)")

        for msg in messages:
            if is_noreply(msg.from_email):
                stats.skipped_noreply += 1
                logger.debug(f"Skip noreply : {msg.from_email}")
                await self._mark_seen_safe(msg.uid)
                continue

            try:
                async with session_scope() as session:
                    await _persist_email(session, msg, stats)
                stats.ingested += 1
                stats.subjects.append(msg.subject or "(sans sujet)")
            except Exception as exc:
                stats.failures += 1
                logger.exception(f"EmailBot — persist a échoué pour UID {msg.uid} : {exc}")
                continue

            await self._mark_seen_safe(msg.uid)

        webhook = settings.discord_webhook_inbox or settings.discord_webhook_escalations
        if webhook is not None:
            try:
                await send_embed(webhook, build_inbox_embed(stats))
            except Exception as exc:
                logger.warning(f"EmailBot — notif Discord a échoué : {exc}")
        else:
            logger.warning("EmailBot — aucun webhook Discord configuré (inbox/escalations)")

        return RunResult(status="success", output_summary=stats.summary())

    async def _mark_seen_safe(self, uid: str) -> None:
        """Wrap mark_seen pour qu'un échec IMAP n'avorte pas le run entier."""
        settings = get_settings()
        if settings.email_user is None or settings.email_password is None:
            return
        try:
            await mark_seen(
                host=settings.email_imap_host,
                port=settings.email_imap_port,
                user=settings.email_user,
                password=settings.email_password,
                uid=uid,
            )
        except Exception as exc:
            logger.warning(f"mark_seen a échoué pour UID {uid} : {exc}")


__all__ = ["EmailBot", "IngestStats", "build_inbox_embed"]
