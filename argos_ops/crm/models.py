"""Modèles SQLModel pour le CRM + KB Argos Ops (P3.1).

Doit rester strictement aligné avec ``argos_ops/crm/migrations/0001_init.sql``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Index
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


# =============================================================================
# Identités
# =============================================================================
class Company(SQLModel, table=True):
    __tablename__ = "companies"

    id: int | None = Field(default=None, primary_key=True)
    domain: str | None = Field(default=None, unique=True, index=True)
    name: str | None = None
    industry: str | None = None
    size_band: str | None = None
    source: str | None = None
    # Stripe (P7) — populated by FinanceBot
    stripe_customer_id: str | None = Field(default=None, unique=True, index=True)
    subscription_status: str | None = Field(default=None, index=True)
    mrr_eur: Decimal | None = None
    stripe_synced_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Lead(SQLModel, table=True):
    __tablename__ = "leads"

    id: int | None = Field(default=None, primary_key=True)
    company_id: int | None = Field(default=None, foreign_key="companies.id", index=True)
    email: str | None = Field(default=None, unique=True, index=True)
    full_name: str | None = None
    job_title: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    status: str | None = Field(default=None, index=True)
    bant_score: int | None = None
    consent_email: bool = Field(default=False, nullable=False)
    consent_phone: bool = Field(default=False, nullable=False)
    bloctel_checked_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class Interaction(SQLModel, table=True):
    __tablename__ = "interactions"

    id: int | None = Field(default=None, primary_key=True)
    lead_id: int | None = Field(default=None, foreign_key="leads.id", index=True)
    channel: str | None = None
    direction: str | None = None
    agent_name: str | None = None
    subject: str | None = None
    body: str | None = None
    judge_score: int | None = None
    judge_verdict: str | None = None
    occurred_at: datetime = Field(default_factory=_utcnow, nullable=False, index=True)


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    id: int | None = Field(default=None, primary_key=True)
    lead_id: int | None = Field(default=None, foreign_key="leads.id", index=True)
    status: str | None = Field(default=None, index=True)
    priority: str | None = None
    summary: str | None = None
    resolution: str | None = None
    opened_at: datetime = Field(default_factory=_utcnow, nullable=False)
    closed_at: datetime | None = None


# =============================================================================
# Observabilité agents
# =============================================================================
class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: int | None = Field(default=None, primary_key=True)
    agent_name: str = Field(nullable=False, index=True)
    command: str | None = None
    started_at: datetime = Field(default_factory=_utcnow, nullable=False, index=True)
    ended_at: datetime | None = None
    status: str | None = None
    output_summary: str | None = None
    error: str | None = None
    cost_estimate_eur: Decimal | None = None


# =============================================================================
# Knowledge Base vectorielle — 768 dims natif (D-017)
# Modèle : sentence-transformers/paraphrase-multilingual-mpnet-base-v2 via fastembed
# =============================================================================
KB_EMBEDDING_DIM = 768


class KBChunk(SQLModel, table=True):
    __tablename__ = "kb_chunks"
    __table_args__ = (Index("uq_kb_chunks_doc_chunk", "doc_path", "chunk_index", unique=True),)

    id: int | None = Field(default=None, primary_key=True)
    doc_path: str = Field(nullable=False)
    chunk_index: int = Field(nullable=False)
    content: str = Field(nullable=False)
    content_hash: str = Field(nullable=False)
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(KB_EMBEDDING_DIM)))
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


# =============================================================================
# Circuit breakers state
# =============================================================================
class Breaker(SQLModel, table=True):
    __tablename__ = "breakers"

    name: str = Field(primary_key=True)
    tripped: bool = Field(default=False, nullable=False)
    tripped_at: datetime | None = None
    reason: str | None = None
    reset_after: datetime | None = None


# =============================================================================
# Configuration runtime des agents
# =============================================================================
class AgentConfig(SQLModel, table=True):
    __tablename__ = "agent_config"

    agent_name: str = Field(primary_key=True)
    enabled: bool = Field(default=True, nullable=False)
    intensity_level: int = Field(default=5, nullable=False)
    schedule_cron: str | None = None
    daily_limit: int | None = None
    max_tokens_per_day: int | None = None
    tier1_threshold: int = Field(default=80, nullable=False)
    paused_until: datetime | None = None
    notes: str | None = None
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_by: str | None = None


# =============================================================================
# Sessions d'authentification du Admin Control Panel
# =============================================================================
class AdminSession(SQLModel, table=True):
    __tablename__ = "admin_sessions"

    token: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False, index=True)
    ip_address: str | None = None
    user_agent: str | None = None
    revoked: bool = Field(default=False, nullable=False)


__all__ = [
    "KB_EMBEDDING_DIM",
    "AdminSession",
    "AgentConfig",
    "AgentRun",
    "Breaker",
    "Company",
    "Interaction",
    "KBChunk",
    "Lead",
    "Ticket",
]
