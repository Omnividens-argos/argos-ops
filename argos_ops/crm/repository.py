"""Repository CRUD pour le CRM Argos Ops.

Fonctions async qui prennent une ``AsyncSession`` en paramètre. Pas de
classe : chaque agent compose ce dont il a besoin et garde la transaction
sous contrôle (cf. ``session_scope`` dans ``db.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from argos_ops.crm.models import (
    AgentConfig,
    AgentRun,
    Breaker,
    Company,
    Interaction,
    KBChunk,
    Lead,
    Ticket,
)


# =============================================================================
# Companies
# =============================================================================
async def get_or_create_company(
    session: AsyncSession,
    *,
    domain: str,
    name: str | None = None,
    source: str | None = None,
) -> Company:
    """Idempotent : un company par domaine."""
    stmt = select(Company).where(col(Company.domain) == domain)
    company = (await session.execute(stmt)).scalar_one_or_none()
    if company is not None:
        return company
    company = Company(domain=domain, name=name, source=source)
    session.add(company)
    await session.flush()
    return company


# =============================================================================
# Leads
# =============================================================================
async def get_or_create_lead(
    session: AsyncSession,
    *,
    email: str,
    company_id: int | None = None,
    full_name: str | None = None,
    job_title: str | None = None,
) -> Lead:
    stmt = select(Lead).where(col(Lead.email) == email)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if lead is not None:
        return lead
    lead = Lead(
        email=email,
        company_id=company_id,
        full_name=full_name,
        job_title=job_title,
        status="new",
    )
    session.add(lead)
    await session.flush()
    return lead


async def update_lead_status(
    session: AsyncSession, lead_id: int, status: str, bant_score: int | None = None
) -> None:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} introuvable")
    lead.status = status
    if bant_score is not None:
        lead.bant_score = bant_score
    lead.updated_at = datetime.now(UTC)


# =============================================================================
# Interactions
# =============================================================================
async def add_interaction(
    session: AsyncSession,
    *,
    lead_id: int | None,
    channel: str,
    direction: str,
    agent_name: str,
    subject: str | None = None,
    body: str | None = None,
    judge_score: int | None = None,
    judge_verdict: str | None = None,
) -> Interaction:
    interaction = Interaction(
        lead_id=lead_id,
        channel=channel,
        direction=direction,
        agent_name=agent_name,
        subject=subject,
        body=body,
        judge_score=judge_score,
        judge_verdict=judge_verdict,
    )
    session.add(interaction)
    await session.flush()
    return interaction


# =============================================================================
# Tickets
# =============================================================================
async def create_ticket(
    session: AsyncSession,
    *,
    lead_id: int | None,
    summary: str,
    priority: str = "P2",
    status: str = "open",
) -> Ticket:
    ticket = Ticket(lead_id=lead_id, summary=summary, priority=priority, status=status)
    session.add(ticket)
    await session.flush()
    return ticket


async def close_ticket(session: AsyncSession, ticket_id: int, resolution: str) -> None:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} introuvable")
    ticket.status = "closed"
    ticket.resolution = resolution
    ticket.closed_at = datetime.now(UTC)


# =============================================================================
# AgentRuns
# =============================================================================
async def start_agent_run(
    session: AsyncSession, *, agent_name: str, command: str | None = None
) -> AgentRun:
    run = AgentRun(agent_name=agent_name, command=command, status="success")
    session.add(run)
    await session.flush()
    return run


async def complete_agent_run(
    session: AsyncSession,
    run_id: int,
    *,
    status: str,
    output_summary: str | None = None,
    error: str | None = None,
    cost_estimate_eur: Decimal | None = None,
) -> None:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise ValueError(f"AgentRun {run_id} introuvable")
    run.status = status
    run.ended_at = datetime.now(UTC)
    run.output_summary = output_summary
    run.error = error
    run.cost_estimate_eur = cost_estimate_eur


async def list_recent_agent_runs(
    session: AsyncSession,
    *,
    agent_name: str | None = None,
    limit: int = 50,
) -> list[AgentRun]:
    """Liste les ``agent_runs`` les plus récents, filtrés optionnellement par agent.

    Utilisé par le Admin Control Panel (P16.A) — page Runs et drawer logs
    par agent.
    """
    stmt = select(AgentRun).order_by(col(AgentRun.started_at).desc()).limit(limit)
    if agent_name is not None:
        stmt = stmt.where(col(AgentRun.agent_name) == agent_name)
    return list((await session.execute(stmt)).scalars().all())


async def get_last_run_per_agent(session: AsyncSession) -> dict[str, AgentRun]:
    """Dernier ``agent_run`` (par ``started_at``) pour chaque agent vu en DB.

    Renvoyé sous forme de dict ``{agent_name: AgentRun}``. Utilisé par
    l'endpoint dashboard ``GET /api/agents`` pour afficher l'état des
    agents en une seule vue. Implémenté en SQL pour éviter le N+1 ;
    fenêtre sur les 30 derniers jours pour borner le volume scanné.
    """
    cutoff = datetime.now(UTC) - timedelta(days=30)
    stmt = (
        select(AgentRun)
        .where(col(AgentRun.started_at) >= cutoff)
        .order_by(col(AgentRun.agent_name), col(AgentRun.started_at).desc())
    )
    runs = list((await session.execute(stmt)).scalars().all())
    out: dict[str, AgentRun] = {}
    for run in runs:
        if run.agent_name not in out:
            out[run.agent_name] = run
    return out


async def count_open_tickets(session: AsyncSession) -> int:
    """KPI Overview — nombre de tickets ``status='open'``."""
    stmt = select(Ticket).where(col(Ticket.status) == "open")
    return len(list((await session.execute(stmt)).scalars().all()))


async def count_recent_leads(session: AsyncSession, *, window_hours: int = 24) -> int:
    """KPI Overview — leads créés sur la fenêtre temporelle."""
    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    stmt = select(Lead).where(col(Lead.created_at) >= cutoff)
    return len(list((await session.execute(stmt)).scalars().all()))


async def sum_active_mrr_eur(session: AsyncSession) -> Decimal:
    """KPI Overview — somme MRR des companies en subscription active/trialing.

    Source de vérité : ``companies.mrr_eur`` (synchronisé par FinanceBot
    depuis Stripe à chaque run quotidien).
    """
    stmt = select(Company).where(col(Company.subscription_status).in_(["active", "trialing"]))
    companies = list((await session.execute(stmt)).scalars().all())
    return sum((c.mrr_eur or Decimal("0.00") for c in companies), start=Decimal("0.00"))


# =============================================================================
# Knowledge Base — upsert + similarité
# =============================================================================
async def upsert_kb_chunk(
    session: AsyncSession,
    *,
    doc_path: str,
    chunk_index: int,
    content: str,
    content_hash: str,
    embedding: list[float] | None,
) -> bool:
    """Upsert sur (doc_path, chunk_index). Retourne True si insertion/update,
    False si le chunk existait avec le même hash (idempotent — pas de
    re-embedding inutile).
    """
    existing_stmt = select(KBChunk).where(
        (col(KBChunk.doc_path) == doc_path) & (col(KBChunk.chunk_index) == chunk_index)
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None and existing.content_hash == content_hash:
        return False

    stmt = (
        pg_insert(KBChunk)
        .values(
            doc_path=doc_path,
            chunk_index=chunk_index,
            content=content,
            content_hash=content_hash,
            embedding=embedding,
            updated_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["doc_path", "chunk_index"],
            set_={
                "content": content,
                "content_hash": content_hash,
                "embedding": embedding,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(stmt)
    return True


async def search_kb_similar(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    limit: int = 5,
) -> list[tuple[KBChunk, float]]:
    """Recherche cosine. Retourne ``[(chunk, distance), ...]`` triés par
    similarité décroissante (distance croissante). Distance pgvector = 1 - cos.
    """
    sql = text(
        """
        SELECT id, doc_path, chunk_index, content, content_hash, updated_at,
               embedding <=> CAST(:q AS vector) AS distance
        FROM kb_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :limit
        """
    )
    result = await session.execute(sql, {"q": str(query_embedding), "limit": limit})
    rows = result.all()
    out: list[tuple[KBChunk, float]] = []
    for row in rows:
        chunk = KBChunk(
            id=row.id,
            doc_path=row.doc_path,
            chunk_index=row.chunk_index,
            content=row.content,
            content_hash=row.content_hash,
            updated_at=row.updated_at,
        )
        out.append((chunk, float(row.distance)))
    return out


# =============================================================================
# Circuit breakers
# =============================================================================
async def is_breaker_tripped(session: AsyncSession, name: str) -> bool:
    breaker = await session.get(Breaker, name)
    if breaker is None:
        return False
    if not breaker.tripped:
        return False
    if breaker.reset_after is not None and breaker.reset_after <= datetime.now(UTC):
        breaker.tripped = False
        return False
    return True


async def trip_breaker(
    session: AsyncSession,
    name: str,
    reason: str,
    reset_after: datetime | None = None,
) -> None:
    breaker = await session.get(Breaker, name)
    now = datetime.now(UTC)
    if breaker is None:
        breaker = Breaker(
            name=name, tripped=True, tripped_at=now, reason=reason, reset_after=reset_after
        )
        session.add(breaker)
    else:
        breaker.tripped = True
        breaker.tripped_at = now
        breaker.reason = reason
        breaker.reset_after = reset_after


async def reset_breaker(session: AsyncSession, name: str) -> None:
    breaker = await session.get(Breaker, name)
    if breaker is None:
        return
    breaker.tripped = False
    breaker.reason = None
    breaker.reset_after = None


async def get_breaker(session: AsyncSession, name: str) -> Breaker | None:
    """Lecture brute du breaker (None si jamais tripped)."""
    return await session.get(Breaker, name)


async def list_tripped_breakers(session: AsyncSession) -> list[Breaker]:
    """Liste tous les breakers actuellement tripped (auto-reset par délai pris en compte).

    Utilisé par :
    - ``/reset-breaker`` (slash command) pour l'auto-complétion
    - Admin Control Panel P16 pour afficher le panneau « breakers actifs »
    - DigestBuilder pour mentionner les breakers actifs dans le récap matin
    """
    stmt = select(Breaker).where(col(Breaker.tripped).is_(True))
    breakers = list((await session.execute(stmt)).scalars().all())
    now = datetime.now(UTC)
    return [b for b in breakers if b.reset_after is None or b.reset_after > now]


async def count_recent_failed_runs(
    session: AsyncSession, *, agent_name: str, window_minutes: int = 60 * 24
) -> int:
    """Compte les runs ``status='failed'`` d'un agent sur une fenêtre temporelle.

    Utilisé par la logique de trip auto : si un agent enchaîne N échecs
    consécutifs sur une fenêtre courte, on trip un breaker métier pour
    alerter le fondateur (cf. P15).
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    stmt = (
        select(AgentRun)
        .where(col(AgentRun.agent_name) == agent_name)
        .where(col(AgentRun.status) == "failed")
        .where(col(AgentRun.started_at) >= cutoff)
    )
    runs = list((await session.execute(stmt)).scalars().all())
    return len(runs)


# =============================================================================
# Agent config (pilotage P16 Admin Panel)
# =============================================================================
async def get_agent_config(session: AsyncSession, agent_name: str) -> AgentConfig | None:
    return await session.get(AgentConfig, agent_name)


async def upsert_agent_config(session: AsyncSession, agent_name: str, **fields: Any) -> AgentConfig:
    config = await session.get(AgentConfig, agent_name)
    if config is None:
        config = AgentConfig(agent_name=agent_name, **fields)
        session.add(config)
    else:
        for key, value in fields.items():
            setattr(config, key, value)
        config.updated_at = datetime.now(UTC)
    await session.flush()
    return config


__all__ = [
    "add_interaction",
    "close_ticket",
    "complete_agent_run",
    "create_ticket",
    "get_agent_config",
    "get_or_create_company",
    "get_or_create_lead",
    "is_breaker_tripped",
    "reset_breaker",
    "search_kb_similar",
    "start_agent_run",
    "trip_breaker",
    "update_lead_status",
    "upsert_agent_config",
    "upsert_kb_chunk",
]
