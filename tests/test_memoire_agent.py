"""Tests du ``MemoireAgent`` (archi v2, S7) — propose, ne supprime jamais."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.agent import AgentContext
from argos_ops.poles.memoire.agent import MemoireAgent
from argos_ops.poles.memoire.policy import MemoryPolicy

NOW = datetime(2026, 6, 18, tzinfo=UTC)
OLD = NOW - timedelta(days=400)

# Contexte minimal : ``act`` n'en dépend pas (il (re)lit le pôle ciblé en direct).
_CTX = AgentContext(pole="memoire")


def _seed_memoire_pole(root: Path) -> None:
    (root / "memoire").mkdir(parents=True, exist_ok=True)
    (root / "memoire" / "pole.yaml").write_text(
        "id: memoire\nname: Mémoire\nagent:\n  name: MemoireAgent\n  trigger: script\n"
        'scripts: []\nreads_cross_pole: ["*"]\nfront_tools: [memory_table]\n',
        encoding="utf-8",
    )


async def test_build_plan_proposes_candidates(tmp_path: Path) -> None:
    await memory.write_memory("veille", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    await memory.write_memory(
        "veille", "s", "important", important=True, created_at=OLD, poles_root=tmp_path
    )
    policy = MemoryPolicy(active_for=("veille",), default_ttl_days=180)
    agent = MemoireAgent("veille", poles_root=tmp_path, policy=policy, now=NOW)
    plan = await agent.build_plan()
    assert plan.n_delete == 1
    assert plan.n_important == 1
    assert plan.n_saved_from_delete == 1


async def test_act_skipped_when_no_memory(tmp_path: Path) -> None:
    policy = MemoryPolicy(active_for=("veille",))
    agent = MemoireAgent("veille", poles_root=tmp_path, policy=policy, now=NOW)
    result = await agent.act(_CTX)
    assert result.status == "skipped"
    assert "aucune mémoire" in (result.summary or "")


async def test_act_skipped_when_inactive(tmp_path: Path) -> None:
    await memory.write_memory("pub", "s", "un fait", created_at=OLD, poles_root=tmp_path)
    policy = MemoryPolicy(active_for=())  # pub non actif
    agent = MemoireAgent("pub", poles_root=tmp_path, policy=policy, now=NOW)
    result = await agent.act(_CTX)
    assert result.status == "skipped"
    assert "non actif" in (result.summary or "")


async def test_act_success_summary(tmp_path: Path) -> None:
    await memory.write_memory("veille", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    await memory.write_memory(
        "veille", "s", "important", important=True, created_at=OLD, poles_root=tmp_path
    )
    policy = MemoryPolicy(active_for=("veille",), default_ttl_days=180)
    agent = MemoireAgent("veille", poles_root=tmp_path, policy=policy, now=NOW)
    result = await agent.act(_CTX)
    assert result.status == "success"
    assert "safe-to-delete" in (result.summary or "")
    assert len(result.actions) == 1  # un candidat


async def test_run_loads_context_and_acts(tmp_path: Path) -> None:
    # run() passe par load_context() (lit la flotte en cross-pôle "*").
    _seed_memoire_pole(tmp_path)
    await memory.write_memory("veille", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    policy = MemoryPolicy(active_for=("veille",), default_ttl_days=180)
    agent = MemoireAgent("veille", poles_root=tmp_path, policy=policy, now=NOW)
    result = await agent.run()
    assert result.status == "success"
