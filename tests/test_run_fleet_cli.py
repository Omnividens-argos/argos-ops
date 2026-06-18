"""Tests du wrapper CLI ``scripts/run_fleet.py`` (archi v2, S9).

Couvre le garde-fou dry-run (court-circuit avant tout lancement) et le code de
sortie (1 dès qu'un script OU un agent échoue, 0 sinon). On monkeypatch
``plan_fleet`` / ``run_fleet_cycle`` dans le module CLI pour rester hermétique et
ne lancer aucun script réel. asyncio_mode = "auto" → pas de décorateur.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

import scripts.run_fleet as rf
from argos_ops.poles.fleet import (
    AgentOutcome,
    FleetCycleResult,
    FleetPlan,
    ScriptOutcome,
)

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _empty_plan(*, dry_run: bool) -> FleetPlan:
    return FleetPlan(
        decisions=[], max_concurrent=2, dry_run=dry_run, trigger_agents=True, generated_at=NOW
    )


async def test_amain_dry_run_returns_zero_without_executing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle_called = {"hit": False}

    async def fake_plan(**_kwargs: object) -> FleetPlan:
        return _empty_plan(dry_run=True)

    async def fake_cycle(*_a: object, **_k: object) -> FleetCycleResult:
        cycle_called["hit"] = True
        return FleetCycleResult(script_outcomes=[], agent_outcomes=[], dry_run=True)

    monkeypatch.setattr(rf, "plan_fleet", fake_plan)
    monkeypatch.setattr(rf, "run_fleet_cycle", fake_cycle)

    rc = await rf.amain(live=False, trigger_agents=True, max_concurrent=None)
    assert rc == 0
    assert cycle_called["hit"] is False  # garde-fou : dry-run ne lance jamais le cycle


async def test_amain_live_exit_code_reflects_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_plan(**_kwargs: object) -> FleetPlan:
        return _empty_plan(dry_run=False)

    monkeypatch.setattr(rf, "plan_fleet", fake_plan)

    ok = ScriptOutcome(
        pole="veille", script="trend_spotter", status="success", summary=None, error=None
    )
    ok_agent = AgentOutcome(
        pole="veille", agent="VeilleAgent", status="success", summary=None, error=None, actions=1
    )

    async def all_ok(*_a: object, **_k: object) -> FleetCycleResult:
        return FleetCycleResult(script_outcomes=[ok], agent_outcomes=[ok_agent], dry_run=False)

    monkeypatch.setattr(rf, "run_fleet_cycle", all_ok)
    assert await rf.amain(live=True, trigger_agents=True, max_concurrent=2) == 0

    # Un agent en échec ⇒ code 1.
    bad_agent = AgentOutcome(
        pole="veille", agent="VeilleAgent", status="failed", summary=None, error="boom", actions=0
    )

    async def agent_failed(*_a: object, **_k: object) -> FleetCycleResult:
        return FleetCycleResult(script_outcomes=[ok], agent_outcomes=[bad_agent], dry_run=False)

    monkeypatch.setattr(rf, "run_fleet_cycle", agent_failed)
    assert await rf.amain(live=True, trigger_agents=True, max_concurrent=2) == 1

    # Un script en échec ⇒ code 1.
    bad_script = ScriptOutcome(
        pole="veille", script="trend_spotter", status="failed", summary=None, error="x"
    )

    async def script_failed(*_a: object, **_k: object) -> FleetCycleResult:
        return FleetCycleResult(script_outcomes=[bad_script], agent_outcomes=[], dry_run=False)

    monkeypatch.setattr(rf, "run_fleet_cycle", script_failed)
    assert await rf.amain(live=True, trigger_agents=True, max_concurrent=2) == 1
