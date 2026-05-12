"""Tests des endpoints FastAPI du Admin Control Panel (P16.A).

Mockent ``session_scope`` et les fonctions repository pour valider la
sérialisation des modèles Pydantic et la logique de mapping. Pas de DB
réelle nécessaire — un fake context manager suffit.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from argos_ops.crm.models import AgentRun, Breaker
from argos_ops.ops_dashboard import app as app_module
from argos_ops.ops_dashboard.app import app


@asynccontextmanager
async def _fake_session_scope() -> object:  # type: ignore[misc]
    yield MagicMock(name="fake-session")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =============================================================================
# /api/health
# =============================================================================
def test_health_db_ok(client: TestClient) -> None:
    fake_session = MagicMock(name="fake-session")
    fake_session.execute = AsyncMock()

    @asynccontextmanager
    async def _scope():  # type: ignore[no-untyped-def]
        yield fake_session

    with patch.object(app_module, "session_scope", _scope):
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "ops_dashboard"
    assert "timestamp" in body


def test_health_db_down(client: TestClient) -> None:
    @asynccontextmanager
    async def _broken_scope():  # type: ignore[no-untyped-def]
        raise RuntimeError("DB unreachable")
        yield  # pragma: no cover — pour faire un async generator

    with patch.object(app_module, "session_scope", _broken_scope):
        response = client.get("/api/health")
    assert response.status_code == 200  # healthcheck doit toujours répondre 200
    assert response.json()["ok"] is False


# =============================================================================
# /api/agents
# =============================================================================
def test_list_agents_returns_known_agents(client: TestClient) -> None:
    now = datetime.now(UTC)
    fake_run = AgentRun(
        id=1,
        agent_name="DigestBuilder",
        command="/morning-digest",
        started_at=now - timedelta(minutes=5),
        ended_at=now - timedelta(minutes=4),
        status="success",
        output_summary="leads=0 customers=0",
    )
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(
            app_module,
            "get_last_run_per_agent",
            AsyncMock(return_value={"DigestBuilder": fake_run}),
        ),
        patch.object(app_module, "list_tripped_breakers", AsyncMock(return_value=[])),
    ):
        response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 4  # KNOWN_AGENTS = DigestBuilder, EmailBot, SupportBot, FinanceBot
    names = [a["name"] for a in agents]
    assert names == ["DigestBuilder", "EmailBot", "SupportBot", "FinanceBot"]
    digest = next(a for a in agents if a["name"] == "DigestBuilder")
    assert digest["last_run_status"] == "success"
    assert digest["last_run_duration_seconds"] == pytest.approx(60.0)
    # Agents sans run récent : tous les champs run sont None
    email = next(a for a in agents if a["name"] == "EmailBot")
    assert email["last_run_status"] is None
    assert email["breaker_tripped"] is False


def test_list_agents_marks_breaker_tripped(client: TestClient) -> None:
    breaker = Breaker(name="EmailBot", tripped=True, reason="paused for vacation")
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "get_last_run_per_agent", AsyncMock(return_value={})),
        patch.object(app_module, "list_tripped_breakers", AsyncMock(return_value=[breaker])),
    ):
        response = client.get("/api/agents")
    email = next(a for a in response.json() if a["name"] == "EmailBot")
    assert email["breaker_tripped"] is True
    assert email["breaker_reason"] == "paused for vacation"


# =============================================================================
# /api/agents/{name}/runs
# =============================================================================
def test_get_agent_runs_returns_rows(client: TestClient) -> None:
    now = datetime.now(UTC)
    runs = [
        AgentRun(
            id=2,
            agent_name="FinanceBot",
            command="/daily-finance-sync",
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(hours=1, seconds=-30),
            status="success",
            output_summary="mrr=0 active_subs=0/0",
            cost_estimate_eur=Decimal("0.00"),
        ),
    ]
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "list_recent_agent_runs", AsyncMock(return_value=runs)),
    ):
        response = client.get("/api/agents/FinanceBot/runs?limit=10")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["agent_name"] == "FinanceBot"
    assert rows[0]["cost_estimate_eur"] == 0.0


def test_get_agent_runs_404_for_unknown_agent(client: TestClient) -> None:
    response = client.get("/api/agents/UnknownBot/runs")
    assert response.status_code == 404


def test_get_agent_runs_validates_limit(client: TestClient) -> None:
    response = client.get("/api/agents/EmailBot/runs?limit=9999")
    assert response.status_code == 422  # validation Query(le=500)


# =============================================================================
# /api/runs (global)
# =============================================================================
def test_list_runs_global(client: TestClient) -> None:
    now = datetime.now(UTC)
    runs = [
        AgentRun(
            id=10,
            agent_name="DigestBuilder",
            started_at=now,
            status="success",
        ),
        AgentRun(
            id=9,
            agent_name="EmailBot",
            started_at=now - timedelta(minutes=10),
            status="failed",
            error="IMAP timeout",
        ),
    ]
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "list_recent_agent_runs", AsyncMock(return_value=runs)),
    ):
        response = client.get("/api/runs")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert rows[0]["agent_name"] == "DigestBuilder"
    assert rows[1]["error"] == "IMAP timeout"


# =============================================================================
# /api/breakers
# =============================================================================
def test_list_breakers_maps_severity(client: TestClient) -> None:
    breakers = [
        Breaker(name="mrr_drop_critical", tripped=True, reason="MRR -12 %"),
        Breaker(name="EmailBot", tripped=True, reason="vacation kill switch"),
        Breaker(name="weird_unknown_breaker", tripped=True, reason="?"),
    ]
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "list_tripped_breakers", AsyncMock(return_value=breakers)),
    ):
        response = client.get("/api/breakers")
    assert response.status_code == 200
    items = response.json()
    by_name = {b["name"]: b for b in items}
    assert by_name["mrr_drop_critical"]["severity"] == "critical"
    assert by_name["EmailBot"]["severity"] == "info"  # kill switch global → info
    assert by_name["weird_unknown_breaker"]["severity"] == "unknown"


def test_list_breakers_empty(client: TestClient) -> None:
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "list_tripped_breakers", AsyncMock(return_value=[])),
    ):
        response = client.get("/api/breakers")
    assert response.status_code == 200
    assert response.json() == []


# =============================================================================
# /api/kpis/overview
# =============================================================================
def test_kpis_overview_returns_all_fields(client: TestClient) -> None:
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "sum_active_mrr_eur", AsyncMock(return_value=Decimal("249.00"))),
        patch.object(app_module, "_count_active_subscriptions", AsyncMock(return_value=1)),
        patch.object(app_module, "count_recent_leads", AsyncMock(return_value=3)),
        patch.object(app_module, "count_open_tickets", AsyncMock(return_value=2)),
        patch.object(
            app_module,
            "list_tripped_breakers",
            AsyncMock(return_value=[Breaker(name="x", tripped=True)]),
        ),
    ):
        response = client.get("/api/kpis/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["mrr_eur"] == 249.0
    assert body["arr_eur"] == 2988.0  # 249 * 12
    assert body["active_subscriptions"] == 1
    assert body["leads_last_24h"] == 3
    assert body["open_tickets"] == 2
    assert body["tripped_breakers"] == 1
    assert "last_refreshed_at" in body


def test_kpis_overview_empty_state(client: TestClient) -> None:
    """État early stage : 0 sub, 0 MRR, 0 leads. Le dashboard doit servir des zéros, pas crasher."""
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "sum_active_mrr_eur", AsyncMock(return_value=Decimal("0.00"))),
        patch.object(app_module, "_count_active_subscriptions", AsyncMock(return_value=0)),
        patch.object(app_module, "count_recent_leads", AsyncMock(return_value=0)),
        patch.object(app_module, "count_open_tickets", AsyncMock(return_value=0)),
        patch.object(app_module, "list_tripped_breakers", AsyncMock(return_value=[])),
    ):
        response = client.get("/api/kpis/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["mrr_eur"] == 0.0
    assert body["arr_eur"] == 0.0
    assert body["active_subscriptions"] == 0
    assert body["tripped_breakers"] == 0
