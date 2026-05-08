"""DigestBuilder — premier agent Argos Ops, sert à valider la chaîne complète.

Lit les KPIs des dernières 24 h dans Postgres, formate un embed Discord,
push sur le webhook ``DISCORD_WEBHOOK_DIGEST`` et logge dans ``agent_runs``.

Cf. P4 du plan : « valider la chaîne cron → Claude Code → action → log DB
avec l'agent le plus simple ». Stripe n'est branché qu'en P7 (FinanceBot),
donc le MRR est marqué « non branché » pour l'instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import get_settings
from argos_ops.crm.db import session_scope
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)


# =============================================================================
# KPIs DTO
# =============================================================================
@dataclass
class DigestKPIs:
    """Photo des dernières 24 h — entrée du formatteur."""

    leads_total: int
    leads_by_source: dict[str, int]  # ex : {"inbound_chat": 8, "outbound": 3}
    new_customers: int
    open_tickets: int
    pending_human_tickets: int
    active_breakers: list[str]
    mrr_eur: int | None = None  # None = Stripe non branché (avant P7)
    mrr_delta_pct: float | None = None  # None si baseline insuffisante


# =============================================================================
# Collecte KPIs
# =============================================================================
async def collect_kpis(session: AsyncSession) -> DigestKPIs:
    """Charge les KPIs des dernières 24 h depuis Postgres."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    # Leads créés J-1 par source (jointure companies → leads pour récupérer la source)
    leads_by_source_stmt = text(
        """
        SELECT COALESCE(c.source, 'unknown') AS source, COUNT(*) AS n
        FROM leads l
        LEFT JOIN companies c ON c.id = l.company_id
        WHERE l.created_at > :cutoff
        GROUP BY COALESCE(c.source, 'unknown')
        """
    )
    rows = (await session.execute(leads_by_source_stmt, {"cutoff": cutoff})).all()
    leads_by_source = {r.source: r.n for r in rows}
    leads_total = sum(leads_by_source.values())

    # Nouveaux clients J-1 (status passé à 'customer')
    new_customers_stmt = text(
        """
        SELECT COUNT(*) AS n FROM leads
        WHERE status = 'customer' AND updated_at > :cutoff
        """
    )
    new_customers = (await session.execute(new_customers_stmt, {"cutoff": cutoff})).scalar_one()

    # Tickets en cours
    tickets_stmt = text(
        """
        SELECT
          COUNT(*) FILTER (WHERE status IN ('open', 'pending_human')) AS open_total,
          COUNT(*) FILTER (WHERE status = 'pending_human') AS pending_human
        FROM tickets
        """
    )
    ticket_row = (await session.execute(tickets_stmt)).one()

    # Breakers actifs (non reset)
    now = datetime.now(UTC)
    breakers_stmt = text(
        """
        SELECT name FROM breakers
        WHERE tripped = TRUE
          AND (reset_after IS NULL OR reset_after > :now)
        """
    )
    active_breakers = [r.name for r in (await session.execute(breakers_stmt, {"now": now})).all()]

    return DigestKPIs(
        leads_total=leads_total,
        leads_by_source=leads_by_source,
        new_customers=int(new_customers),
        open_tickets=int(ticket_row.open_total),
        pending_human_tickets=int(ticket_row.pending_human),
        active_breakers=active_breakers,
        mrr_eur=None,  # branché en P7
        mrr_delta_pct=None,
    )


# =============================================================================
# Formatting
# =============================================================================
def _format_leads_breakdown(by_source: dict[str, int]) -> str:
    if not by_source:
        return "0"
    parts = [f"{n} {src}" for src, n in sorted(by_source.items(), key=lambda kv: -kv[1])]
    total = sum(by_source.values())
    return f"{total} ({' / '.join(parts)})"


def _digest_color(kpis: DigestKPIs) -> int:
    """Vert si tout OK, jaune si escalades, rouge si breakers actifs."""
    if kpis.active_breakers:
        return RED
    if kpis.pending_human_tickets > 0:
        return YELLOW
    return GREEN


def build_digest_embed(kpis: DigestKPIs, *, today: datetime | None = None) -> Embed:
    """Convertit des KPIs en embed Discord prêt à push."""
    today = today or datetime.now(UTC)
    title = f"Argos — Digest {today.strftime('%Y-%m-%d')}"

    if kpis.mrr_eur is not None:
        delta = f" ({kpis.mrr_delta_pct:+.1f}% vs S-1)" if kpis.mrr_delta_pct is not None else ""
        mrr_str = f"{kpis.mrr_eur:,} €{delta}".replace(",", " ")
    else:
        mrr_str = "Stripe non branché (P7)"

    fields = [
        EmbedField(name="MRR", value=mrr_str, inline=True),
        EmbedField(
            name="Leads J-1", value=_format_leads_breakdown(kpis.leads_by_source), inline=True
        ),
        EmbedField(name="Nouveaux clients J-1", value=str(kpis.new_customers), inline=True),
        EmbedField(
            name="Tickets ouverts",
            value=f"{kpis.open_tickets} (dont {kpis.pending_human_tickets} à traiter humain)",
            inline=False,
        ),
        EmbedField(
            name="Breakers actifs",
            value=", ".join(kpis.active_breakers) if kpis.active_breakers else "aucun",
            inline=False,
        ),
    ]

    return Embed(
        title=title,
        color=_digest_color(kpis),
        fields=fields,
        footer="Argos Ops • DigestBuilder",
        timestamp=today.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class DigestBuilder(BaseAgent):
    """Premier agent Argos Ops — digest quotidien Discord."""

    name = "DigestBuilder"
    command = "/morning-digest"
    breaker_name = "DigestBuilder"  # peut être désactivé via le panel admin (P16)

    async def run(self) -> RunResult:
        settings = get_settings()
        if settings.discord_webhook_digest is None:
            return RunResult(
                status="failed",
                error="DISCORD_WEBHOOK_DIGEST manquant dans .env.local — voir P1.B",
            )

        async with session_scope() as session:
            kpis = await collect_kpis(session)

        embed = build_digest_embed(kpis)
        await send_embed(settings.discord_webhook_digest, embed)

        summary = (
            f"leads={kpis.leads_total} customers={kpis.new_customers} "
            f"tickets_open={kpis.open_tickets} pending_human={kpis.pending_human_tickets} "
            f"breakers={len(kpis.active_breakers)}"
        )
        logger.info(f"Digest pushé : {summary}")
        return RunResult(status="success", output_summary=summary)


__all__ = ["DigestBuilder", "DigestKPIs", "build_digest_embed", "collect_kpis"]
