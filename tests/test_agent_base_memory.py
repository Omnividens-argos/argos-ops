"""Tests du réflexe « se souvenir » câblé dans ``run_agent`` (Cockpit LOT 3).

Mocke les dépendances DB / runtime de ``run_agent`` et vérifie que les faits
exposés via ``RunResult.extras['fleet_facts']`` sont conservés — uniquement
sur un run réussi, jamais quand le run échoue ou n'expose rien.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops.agents import base as base_module
from argos_ops.agents.base import BaseAgent, RunResult, run_agent


class _Agent(BaseAgent):
    name = "TrendSpotter"
    command = "/run-trend-spot"

    def __init__(self, result: RunResult) -> None:
        self._result = result

    async def run(self) -> RunResult:
        return self._result


@asynccontextmanager
async def _fake_scope():  # type: ignore[no-untyped-def]
    yield MagicMock(name="session")


def _patches(remember_mock: AsyncMock):  # type: ignore[no-untyped-def]
    return (
        patch.object(base_module, "session_scope", _fake_scope),
        patch.object(
            base_module,
            "check_runtime_state",
            AsyncMock(return_value=MagicMock(verdict="allowed", reason=None)),
        ),
        patch.object(base_module, "start_agent_run", AsyncMock(return_value=MagicMock(id=7))),
        patch.object(base_module, "complete_agent_run", AsyncMock()),
        patch.object(base_module.fleet_memory, "remember", remember_mock),
    )


async def _run_with(result: RunResult, remember_mock: AsyncMock) -> None:
    p = _patches(remember_mock)
    with p[0], p[1], p[2], p[3], p[4]:
        await run_agent(_Agent(result))


@pytest.mark.asyncio
async def test_success_with_facts_persists() -> None:
    remember_mock = AsyncMock(return_value=[MagicMock()])
    facts = [{"body": "Sujet chaud : faille VPN", "kind": "trend"}]
    await _run_with(RunResult(status="success", extras={"fleet_facts": facts}), remember_mock)
    remember_mock.assert_awaited_once()
    args, kwargs = remember_mock.call_args
    assert args[0] == "TrendSpotter"
    assert args[1] == facts
    # Provenance : source lisible run#N (commande) + run_id structuré
    # (start_agent_run est mocké avec id=7).
    assert kwargs["default_source"] == "run#7 (/run-trend-spot)"
    assert kwargs["run_id"] == 7


@pytest.mark.asyncio
async def test_success_without_facts_does_not_persist() -> None:
    remember_mock = AsyncMock()
    await _run_with(RunResult(status="success"), remember_mock)
    remember_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_run_does_not_persist() -> None:
    remember_mock = AsyncMock()
    # Un run qui retourne failed n'écrit pas en mémoire.
    await _run_with(
        RunResult(status="failed", extras={"fleet_facts": [{"body": "x"}]}), remember_mock
    )
    remember_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_failure_does_not_break_run() -> None:
    remember_mock = AsyncMock(side_effect=RuntimeError("disk full"))
    facts = [{"body": "fait", "kind": "trend"}]
    # Ne doit pas lever : la mémoire ne fait jamais échouer un run.
    p = _patches(remember_mock)
    with p[0], p[1], p[2], p[3], p[4]:
        result = await run_agent(_Agent(RunResult(status="success", extras={"fleet_facts": facts})))
    assert result.status == "success"
    remember_mock.assert_awaited_once()
