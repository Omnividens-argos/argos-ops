"""Tests unitaires de :mod:`argos_ops.agents.orchestrator` (P22.B).

Couvrent la logique de planification (verdicts par agent) et
l'exécution parallèle capée. Les ops DB et l'agent runner sont mockés
— pas de Postgres requis.

Les 6 cas du brief (« simulate 6 agents avec différents états ») sont
matérialisés dans :func:`test_plan_execution_full_fleet_mix`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from argos_ops.agents import orchestrator
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.agents.orchestrator import (
    AGENT_FLEET,
    AgentDecision,
    FleetEntry,
    OrchestrationPlan,
    execute_plan,
    plan_execution,
)
from argos_ops.crm.models import AgentConfig, AgentRun


# =============================================================================
# Fixtures
# =============================================================================
class _StubAgent(BaseAgent):
    """Agent vide juste pour fournir une factory aux fleets de test."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name

    async def run(self) -> RunResult:
        return RunResult(status="success", output_summary="stub")


def _make_entry(
    name: str, *, interval_hours: float = 1.0, breaker: str | None = None
) -> FleetEntry:
    return FleetEntry(
        name=name,
        interval_hours=interval_hours,
        factory=lambda: _StubAgent(name),
        breaker_name=breaker,
    )


def _make_run(agent: str, hours_ago: float) -> AgentRun:
    started = datetime.now(UTC) - timedelta(hours=hours_ago)
    return AgentRun(
        agent_name=agent,
        command=None,
        status="success",
        started_at=started,
        ended_at=started + timedelta(seconds=1.0),
    )


def _patch_db(
    *,
    last_runs: dict[str, AgentRun],
    configs: dict[str, AgentConfig] | None = None,
    tripped: set[str] | None = None,
    runs_today: dict[str, int] | None = None,
):
    """Helper context manager qui patch toutes les ops DB en bloc."""
    configs = configs or {}
    tripped = tripped or set()
    runs_today = runs_today or {}

    async def _get_cfg(_session, agent_name: str) -> AgentConfig:
        return configs.get(agent_name, AgentConfig(agent_name=agent_name))

    async def _runs_today(_session, agent_name: str) -> int:
        return runs_today.get(agent_name, 0)

    async def _breaker(_session, name: str) -> bool:
        return name in tripped

    @asynccontextmanager_compat
    async def _fake_session_scope():
        yield object()

    return [
        patch.object(orchestrator, "session_scope", _fake_session_scope),
        patch.object(
            orchestrator,
            "get_last_run_per_agent",
            new=AsyncMock(return_value=last_runs),
        ),
        patch.object(orchestrator, "get_agent_config", new=AsyncMock(side_effect=_get_cfg)),
        patch.object(orchestrator, "count_runs_today", new=AsyncMock(side_effect=_runs_today)),
        patch.object(orchestrator, "is_breaker_tripped", new=AsyncMock(side_effect=_breaker)),
    ]


def asynccontextmanager_compat(func):
    """Shim pour utiliser ``async with`` sur une fonction de test."""
    from contextlib import asynccontextmanager

    return asynccontextmanager(func)


def _apply_patches(patches):
    """Active une liste de patches comme un seul context manager."""
    from contextlib import ExitStack

    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


# =============================================================================
# plan_execution — décisions individuelles
# =============================================================================
@pytest.mark.asyncio
async def test_plan_launches_when_due_and_enabled() -> None:
    fleet = (_make_entry("AgentA", interval_hours=1.0),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=3.0)},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert len(plan.to_launch) == 1
    assert plan.decisions[0].verdict == "launch"


@pytest.mark.asyncio
async def test_plan_skipped_not_due_when_recent() -> None:
    fleet = (_make_entry("AgentA", interval_hours=24.0),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=1.0)},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "skipped_not_due"


@pytest.mark.asyncio
async def test_plan_skipped_breaker_takes_priority() -> None:
    fleet = (_make_entry("AgentA", interval_hours=1.0, breaker="breaker_x"),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=99.0)},
        tripped={"breaker_x"},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "skipped_breaker"
    assert "breaker_x" in plan.decisions[0].reason


@pytest.mark.asyncio
async def test_plan_skipped_disabled() -> None:
    fleet = (_make_entry("AgentA", interval_hours=1.0),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=10.0)},
        configs={"AgentA": AgentConfig(agent_name="AgentA", enabled=False)},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "skipped_disabled"


@pytest.mark.asyncio
async def test_plan_skipped_paused_when_paused_until_future() -> None:
    paused_until = datetime.now(UTC) + timedelta(hours=2)
    fleet = (_make_entry("AgentA", interval_hours=1.0),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=10.0)},
        configs={"AgentA": AgentConfig(agent_name="AgentA", paused_until=paused_until)},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "skipped_paused"


@pytest.mark.asyncio
async def test_plan_skipped_daily_limit_reached() -> None:
    fleet = (_make_entry("AgentA", interval_hours=1.0),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=10.0)},
        configs={"AgentA": AgentConfig(agent_name="AgentA", daily_limit=5)},
        runs_today={"AgentA": 5},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "skipped_daily_limit"


@pytest.mark.asyncio
async def test_plan_skipped_intensity_zero() -> None:
    fleet = (_make_entry("AgentA", interval_hours=1.0),)
    patches = _patch_db(
        last_runs={"AgentA": _make_run("AgentA", hours_ago=10.0)},
        configs={"AgentA": AgentConfig(agent_name="AgentA", intensity_level=0)},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "skipped_intensity_zero"


@pytest.mark.asyncio
async def test_plan_launches_when_never_run() -> None:
    fleet = (_make_entry("AgentA", interval_hours=1.0),)
    patches = _patch_db(last_runs={})
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)
    assert plan.decisions[0].verdict == "launch"
    assert plan.decisions[0].age_hours is None
    assert "never run" in plan.decisions[0].reason


# =============================================================================
# Scénario complet — 6 agents avec différents états (cf. brief)
# =============================================================================
@pytest.mark.asyncio
async def test_plan_execution_full_fleet_mix() -> None:
    fleet = (
        _make_entry("A_due", interval_hours=1.0),  # 1
        _make_entry("B_not_due", interval_hours=24.0),  # 2
        _make_entry("C_breaker", interval_hours=1.0, breaker="brk"),  # 3
        _make_entry("D_disabled", interval_hours=1.0),  # 4
        _make_entry("E_daily_limit", interval_hours=1.0),  # 5
        _make_entry("F_never_run", interval_hours=1.0),  # 6
    )
    patches = _patch_db(
        last_runs={
            "A_due": _make_run("A_due", hours_ago=3.0),
            "B_not_due": _make_run("B_not_due", hours_ago=1.0),
            "C_breaker": _make_run("C_breaker", hours_ago=99.0),
            "D_disabled": _make_run("D_disabled", hours_ago=10.0),
            "E_daily_limit": _make_run("E_daily_limit", hours_ago=10.0),
            # F_never_run absent → jamais run
        },
        configs={
            "D_disabled": AgentConfig(agent_name="D_disabled", enabled=False),
            "E_daily_limit": AgentConfig(agent_name="E_daily_limit", daily_limit=3),
        },
        tripped={"brk"},
        runs_today={"E_daily_limit": 3},
    )
    with _apply_patches(patches):
        plan = await plan_execution(fleet=fleet)

    by_name = {d.agent_name: d for d in plan.decisions}
    assert by_name["A_due"].verdict == "launch"
    assert by_name["B_not_due"].verdict == "skipped_not_due"
    assert by_name["C_breaker"].verdict == "skipped_breaker"
    assert by_name["D_disabled"].verdict == "skipped_disabled"
    assert by_name["E_daily_limit"].verdict == "skipped_daily_limit"
    assert by_name["F_never_run"].verdict == "launch"
    assert len(plan.to_launch) == 2

    # Priorité tri : F (jamais run = +inf retard) avant A
    launch_order = [d.agent_name for d in plan.decisions if d.verdict == "launch"]
    assert launch_order == ["F_never_run", "A_due"]


# =============================================================================
# OrchestrationPlan helpers
# =============================================================================
def test_plan_summary_format() -> None:
    decisions = [
        AgentDecision(
            agent_name="X",
            verdict="launch",
            reason="due",
            last_run_at=None,
            age_hours=None,
            interval_hours=1.0,
            enabled=True,
            intensity_level=5,
            runs_today=0,
            daily_limit=None,
        ),
        AgentDecision(
            agent_name="Y",
            verdict="skipped_not_due",
            reason="0.1h < 1h",
            last_run_at=None,
            age_hours=0.1,
            interval_hours=1.0,
            enabled=True,
            intensity_level=5,
            runs_today=0,
            daily_limit=None,
        ),
    ]
    plan = OrchestrationPlan(decisions=decisions, max_concurrent=2, dry_run=True)
    summary = plan.summary()
    assert "1 to launch" in summary
    assert "1 skipped" in summary
    assert "dry_run=True" in summary


# =============================================================================
# execute_plan — dry-run + parallélisme capé
# =============================================================================
@pytest.mark.asyncio
async def test_execute_plan_noop_in_dry_run() -> None:
    fleet = (_make_entry("A"),)
    decisions = [
        AgentDecision(
            agent_name="A",
            verdict="launch",
            reason="due",
            last_run_at=None,
            age_hours=None,
            interval_hours=1.0,
            enabled=True,
            intensity_level=5,
            runs_today=0,
            daily_limit=None,
        )
    ]
    plan = OrchestrationPlan(decisions=decisions, max_concurrent=1, dry_run=True)

    called = False

    async def _runner(_agent: BaseAgent) -> RunResult:
        nonlocal called
        called = True
        return RunResult(status="success")

    outcomes = await execute_plan(plan, fleet=fleet, runner=_runner)
    assert outcomes == []
    assert called is False


@pytest.mark.asyncio
async def test_execute_plan_respects_max_concurrent() -> None:
    """Sémaphore = 2 → jamais plus de 2 agents in-flight simultanément."""
    fleet = tuple(_make_entry(f"A{i}") for i in range(5))
    decisions = [
        AgentDecision(
            agent_name=f"A{i}",
            verdict="launch",
            reason="due",
            last_run_at=None,
            age_hours=None,
            interval_hours=1.0,
            enabled=True,
            intensity_level=5,
            runs_today=0,
            daily_limit=None,
        )
        for i in range(5)
    ]
    plan = OrchestrationPlan(decisions=decisions, max_concurrent=2, dry_run=False)

    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def _runner(agent: BaseAgent) -> RunResult:
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        async with lock:
            in_flight -= 1
        return RunResult(status="success", output_summary=f"{agent.name} done")

    outcomes = await execute_plan(plan, fleet=fleet, runner=_runner)
    assert len(outcomes) == 5
    assert all(o.status == "success" for o in outcomes)
    assert peak <= 2, f"max_concurrent breached — peak={peak}"


@pytest.mark.asyncio
async def test_execute_plan_handles_unknown_agent_gracefully() -> None:
    """Décision pour un agent absent de la fleet → ExecutionOutcome failed
    plutôt que crash."""
    fleet = (_make_entry("A"),)
    decisions = [
        AgentDecision(
            agent_name="ghost",
            verdict="launch",
            reason="due",
            last_run_at=None,
            age_hours=None,
            interval_hours=1.0,
            enabled=True,
            intensity_level=5,
            runs_today=0,
            daily_limit=None,
        )
    ]
    plan = OrchestrationPlan(decisions=decisions, max_concurrent=2, dry_run=False)

    async def _runner(_agent: BaseAgent) -> RunResult:
        raise AssertionError("ne devrait pas être appelé")

    outcomes = await execute_plan(plan, fleet=fleet, runner=_runner)
    assert len(outcomes) == 1
    assert outcomes[0].status == "failed"
    assert outcomes[0].error is not None
    assert "ghost" in outcomes[0].error


# =============================================================================
# AGENT_FLEET sanity check
# =============================================================================
def test_real_fleet_contains_active_sprint1_bots() -> None:
    """Sanity check du catalogue Python — change ce test si on ajoute
    intentionnellement un nouveau bot à la fleet."""
    names = {entry.name for entry in AGENT_FLEET}
    assert {"DigestBuilder", "EmailBot", "FinanceBot", "FleetWatchdog"} <= names


def test_real_fleet_intervals_are_positive() -> None:
    for entry in AGENT_FLEET:
        assert entry.interval_hours > 0, f"{entry.name} interval_hours must be > 0"
