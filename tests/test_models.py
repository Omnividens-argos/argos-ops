"""Tests des modèles SQLModel — instanciation, types, valeurs par défaut."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from argos_ops.crm.models import (
    KB_EMBEDDING_DIM,
    AdminSession,
    AgentConfig,
    AgentRun,
    Breaker,
    Company,
    Interaction,
    KBChunk,
    Lead,
    Ticket,
)


def test_company_defaults() -> None:
    c = Company(domain="omnividens.fr", name="Omnividens", source="inbound_chat")
    assert c.id is None
    assert c.domain == "omnividens.fr"
    assert isinstance(c.created_at, datetime)
    assert c.created_at.tzinfo is not None


def test_lead_consent_defaults_false() -> None:
    lead = Lead(email="rssi@acme.com")
    assert lead.consent_email is False
    assert lead.consent_phone is False
    assert lead.bloctel_checked_at is None


def test_interaction_minimal() -> None:
    i = Interaction(channel="email", direction="in", agent_name="EmailBot")
    assert i.judge_score is None
    assert i.judge_verdict is None


def test_ticket_minimal() -> None:
    t = Ticket(summary="Bug SAML", priority="P1", status="open")
    assert t.closed_at is None
    assert isinstance(t.opened_at, datetime)


def test_agent_run_decimal_cost() -> None:
    run = AgentRun(agent_name="EmailBot", cost_estimate_eur=Decimal("0.0021"))
    assert run.cost_estimate_eur == Decimal("0.0021")


def test_kb_chunk_embedding_dim_constant() -> None:
    assert KB_EMBEDDING_DIM == 768
    chunk = KBChunk(
        doc_path="data/knowledge_base/pricing.md",
        chunk_index=0,
        content="Pro Max 70 €",
        content_hash="a" * 64,
        embedding=[0.1] * KB_EMBEDDING_DIM,
    )
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 768


def test_breaker_starts_untripped() -> None:
    b = Breaker(name="adbot_daily")
    assert b.tripped is False
    assert b.tripped_at is None


def test_agent_config_defaults() -> None:
    cfg = AgentConfig(agent_name="EmailBot")
    assert cfg.enabled is True
    assert cfg.intensity_level == 5
    assert cfg.tier1_threshold == 80


def test_admin_session_min() -> None:
    s = AdminSession(token="abc", expires_at=datetime.now(UTC) + timedelta(hours=12))
    assert s.revoked is False
