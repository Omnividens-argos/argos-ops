"""Preuve du flux **script → mémoire → agent** via le pôle jouet ``_example``.

C'est le livrable « flux démontré » de la session S0 : un script déterministe
écrit un fait, l'agent du pôle le relit et agit dessus. Hermétique (``tmp_path``).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import run_script
from argos_ops.poles.example import ExampleAgent, HeartbeatScript


def _scaffold_example(root: Path) -> None:
    d = root / "_example"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: _example\nname: Exemple\nagent:\n  name: ExampleAgent\n  skills: []\n"
        "scripts:\n  - id: heartbeat\nreads_cross_pole: []\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


async def test_script_writes_memory_then_agent_reads_it(tmp_path: Path) -> None:
    _scaffold_example(tmp_path)

    # 1. Le SCRIPT (bras déterministe) écrit sa mémoire.
    script_result = await run_script(HeartbeatScript(poles_root=tmp_path))
    assert script_result.status == "success"
    assert len(script_result.written) == 1
    written = script_result.written[0]
    assert written.kind == "heartbeat"
    assert written.pole == "_example"

    # 2. L'AGENT (cerveau) lit cette mémoire et agit.
    agent_result = await ExampleAgent(poles_root=tmp_path).run()
    assert agent_result.status == "success"
    assert agent_result.actions
    assert agent_result.summary is not None
    assert "heartbeat" in agent_result.summary


async def test_script_run_is_idempotent(tmp_path: Path) -> None:
    _scaffold_example(tmp_path)
    await run_script(HeartbeatScript(poles_root=tmp_path))
    await run_script(HeartbeatScript(poles_root=tmp_path))

    # Deux runs → un seul fait (idempotence par hash de corps).
    agent = ExampleAgent(poles_root=tmp_path)
    ctx = await agent.load_context()
    assert len(ctx.all_records()) == 1


async def test_agent_skips_on_empty_memory(tmp_path: Path) -> None:
    _scaffold_example(tmp_path)
    result = await ExampleAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"
