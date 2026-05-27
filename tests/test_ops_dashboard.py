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

from argos_ops.crm.models import AgentConfig, AgentRun, Breaker
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
    # KNOWN_AGENTS étendu post P22.E/F/G/H/I — vérifier juste la présence des 6 originaux
    # et l'ordre canonique (ils restent en tête de la tuple).
    assert len(agents) == len(app_module.KNOWN_AGENTS)
    names = [a["name"] for a in agents]
    for canonical in (
        "DigestBuilder",
        "EmailBot",
        "SupportBot",
        "FinanceBot",
        "BotHealthBot",
        "OrchestratorBot",
    ):
        assert canonical in names
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


# =============================================================================
# Mutations P16.B
# =============================================================================
def test_get_agent_config_returns_defaults(client: TestClient) -> None:
    config = AgentConfig(agent_name="FinanceBot", enabled=True, intensity_level=5)
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "get_agent_config", AsyncMock(return_value=config)),
    ):
        response = client.get("/api/agents/FinanceBot/config")
    assert response.status_code == 200
    body = response.json()
    assert body["agent_name"] == "FinanceBot"
    assert body["enabled"] is True
    assert body["intensity_level"] == 5


def test_get_agent_config_404_for_unknown(client: TestClient) -> None:
    response = client.get("/api/agents/UnknownBot/config")
    assert response.status_code == 404


def test_patch_agent_config_disables_agent(client: TestClient) -> None:
    updated = AgentConfig(
        agent_name="FinanceBot",
        enabled=False,
        intensity_level=5,
        notes="Pause vacation",
    )
    fake_update = AsyncMock(return_value=updated)
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "update_agent_config", fake_update),
    ):
        response = client.patch(
            "/api/agents/FinanceBot/config",
            json={"enabled": False, "notes": "Pause vacation"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["notes"] == "Pause vacation"
    # update_agent_config doit recevoir enabled=False, notes="Pause vacation"
    call_kwargs = fake_update.call_args.kwargs
    assert call_kwargs["enabled"] is False
    assert call_kwargs["notes"] == "Pause vacation"
    assert call_kwargs["updated_by"] == "admin_panel"


def test_patch_agent_config_404_for_unknown(client: TestClient) -> None:
    response = client.patch("/api/agents/UnknownBot/config", json={"enabled": False})
    assert response.status_code == 404


def test_patch_agent_config_clear_paused(client: TestClient) -> None:
    """clear_paused=true doit effacer paused_until — testé via le kwarg passé au repo."""
    updated = AgentConfig(agent_name="FinanceBot", enabled=True, intensity_level=5)
    fake_update = AsyncMock(return_value=updated)
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "update_agent_config", fake_update),
    ):
        response = client.patch(
            "/api/agents/FinanceBot/config",
            json={"clear_paused": True},
        )
    assert response.status_code == 200
    assert fake_update.call_args.kwargs["clear_paused"] is True


def test_trip_breaker_endpoint(client: TestClient) -> None:
    breaker = Breaker(
        name="manual_kill",
        tripped=True,
        tripped_at=datetime.now(UTC),
        reason="vacation",
    )
    fake_trip = AsyncMock()
    fake_get = AsyncMock(return_value=breaker)
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "trip_breaker_facade", fake_trip),
        patch.object(app_module, "get_breaker", fake_get),
    ):
        response = client.post(
            "/api/breakers/manual_kill/trip",
            json={"reason": "vacation"},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "manual_kill"
    assert body["tripped"] is True
    assert body["reason"] == "vacation"
    fake_trip.assert_awaited_once()


def test_reset_breaker_endpoint(client: TestClient) -> None:
    breaker = Breaker(name="manual_kill", tripped=False)
    fake_reset = AsyncMock()
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "reset_breaker_facade", fake_reset),
        patch.object(app_module, "get_breaker", AsyncMock(return_value=breaker)),
    ):
        response = client.post("/api/breakers/manual_kill/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["tripped"] is False
    fake_reset.assert_awaited_once()


def test_reset_breaker_never_tripped_returns_synthetic_state(client: TestClient) -> None:
    """Reset sur un breaker jamais tripped → renvoie un état synthétique, pas 404."""
    with (
        patch.object(app_module, "session_scope", _fake_session_scope),
        patch.object(app_module, "reset_breaker_facade", AsyncMock()),
        patch.object(app_module, "get_breaker", AsyncMock(return_value=None)),
    ):
        response = client.post("/api/breakers/never_seen/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "never_seen"
    assert body["tripped"] is False
    assert body["severity"] == "unknown"


# =============================================================================
# POST /api/agents/{name}/runs (P16.C — Run now manuel)
# =============================================================================
def test_run_agent_now_unknown_agent_404(client: TestClient) -> None:
    response = client.post("/api/agents/UnknownBot/runs")
    assert response.status_code == 404


def test_run_agent_now_interactive_agent_400(client: TestClient) -> None:
    """Vérifie le code path 400 pour un agent KNOWN mais hors RUNNABLE_AGENTS.

    Depuis P22.G tous les agents KNOWN sont aussi RUNNABLE (SupportBot/SEOBot/
    DecisionLogger ont des wrappers health-check passifs). On patche le set
    pour simuler un agent interactif-only et vérifier que le code path reste
    fonctionnel pour de futurs bots.
    """
    with patch.object(app_module, "RUNNABLE_AGENTS", frozenset()):
        response = client.post("/api/agents/DigestBuilder/runs")
    assert response.status_code == 400
    assert "interactif" in response.json()["detail"].lower()


def test_run_agent_now_dispatches_to_run_agent(client: TestClient) -> None:
    """Le endpoint instancie l'agent et passe par run_agent (qui applique les
    checks runtime). On mocke run_agent pour ne pas toucher la vraie DB."""
    from argos_ops.agents.base import RunResult

    fake_run = AsyncMock(
        return_value=RunResult(status="success", output_summary="leads=0 customers=0")
    )
    with patch.object(app_module, "run_agent", fake_run):
        response = client.post("/api/agents/DigestBuilder/runs")
    assert response.status_code == 202
    body = response.json()
    assert body["agent_name"] == "DigestBuilder"
    assert body["status"] == "success"
    assert body["output_summary"] == "leads=0 customers=0"
    fake_run.assert_awaited_once()


def test_run_agent_now_reports_failed_status(client: TestClient) -> None:
    """Si run_agent renvoie un verdict skip/failed, le endpoint le propage tel quel."""
    from argos_ops.agents.base import RunResult

    fake_run = AsyncMock(
        return_value=RunResult(status="skipped_disabled", error="agent disabled via Admin Panel")
    )
    with patch.object(app_module, "run_agent", fake_run):
        response = client.post("/api/agents/EmailBot/runs")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "skipped_disabled"
    assert body["error"] == "agent disabled via Admin Panel"
