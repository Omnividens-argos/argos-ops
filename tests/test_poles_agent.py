"""Tests du ``BaseAgent`` de pôle + mécanisme de lecture cross-pôle (archi v2).

Hermétique : pôles scaffoldés sous ``tmp_path``. Vérifie le garde-fou central —
un agent ne lit QUE les pôles déclarés dans ``reads_cross_pole`` (``"*"`` = tous).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent


class _ProbeAgent(BaseAgent):
    """Agent minimal : expose le contexte, n'agit pas réellement."""

    pole = "veille"
    name = "ProbeAgent"

    async def act(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            status="success",
            summary="probe",
            actions=[r.body for r in context.all_records()],
        )


def _scaffold_pole(root: Path, pole: str, *, reads: tuple[str, ...] = ()) -> None:
    d = root / pole
    d.mkdir(parents=True, exist_ok=True)
    reads_yaml = "[" + ", ".join(reads) + "]"
    (d / "pole.yaml").write_text(
        f"id: {pole}\nagent:\n  name: {pole.capitalize()}Agent\n  skills: [foo]\n"
        f"scripts: []\nreads_cross_pole: {reads_yaml}\nfront_tools: []\n",
        encoding="utf-8",
    )


async def test_agent_reads_own_memory_only_when_no_cross(tmp_path: Path) -> None:
    _scaffold_pole(tmp_path, "veille")
    await memory.write_memory("veille", "s", "fait veille", poles_root=tmp_path)
    await memory.write_memory("marketing", "s", "fait marketing", poles_root=tmp_path)

    ctx = await _ProbeAgent(poles_root=tmp_path).load_context()
    assert set(ctx.own) == {"s"}
    assert ctx.cross_pole == {}
    bodies = [r.body for r in ctx.all_records()]
    assert "fait veille" in bodies
    assert "fait marketing" not in bodies


async def test_agent_reads_only_declared_cross_pole(tmp_path: Path) -> None:
    _scaffold_pole(tmp_path, "veille", reads=("marketing",))
    _scaffold_pole(tmp_path, "marketing")
    await memory.write_memory("veille", "s", "fait veille", poles_root=tmp_path)
    await memory.write_memory("marketing", "x", "fait marketing", poles_root=tmp_path)
    await memory.write_memory("pub", "y", "fait pub", poles_root=tmp_path)  # non déclaré

    ctx = await _ProbeAgent(poles_root=tmp_path).load_context()
    assert "marketing" in ctx.cross_pole
    assert "pub" not in ctx.cross_pole  # non déclaré → invisible
    assert ctx.skills == ("foo",)
    bodies = [r.body for r in ctx.all_records()]
    assert {"fait veille", "fait marketing"} <= set(bodies)
    assert "fait pub" not in bodies


async def test_wildcard_reads_all_other_poles(tmp_path: Path) -> None:
    _scaffold_pole(tmp_path, "direction", reads=('"*"',))
    _scaffold_pole(tmp_path, "veille")
    _scaffold_pole(tmp_path, "marketing")
    await memory.write_memory("veille", "s", "v", poles_root=tmp_path)
    await memory.write_memory("marketing", "s", "m", poles_root=tmp_path)
    await memory.write_memory("direction", "s", "d", poles_root=tmp_path)

    agent = _ProbeAgent(poles_root=tmp_path)
    agent.pole = "direction"  # override l'attribut de classe pour ce test
    ctx = await agent.load_context()
    assert set(ctx.cross_pole) == {"veille", "marketing"}  # tous sauf soi-même


async def test_context_important_filters_protected_facts(tmp_path: Path) -> None:
    _scaffold_pole(tmp_path, "veille")
    await memory.write_memory("veille", "s", "fait normal", poles_root=tmp_path)
    await memory.write_memory("veille", "s", "fait clé", important=True, poles_root=tmp_path)

    ctx = await _ProbeAgent(poles_root=tmp_path).load_context()
    important = ctx.important()
    assert len(important) == 1
    assert important[0].body == "fait clé"


async def test_context_is_empty_when_no_memory(tmp_path: Path) -> None:
    _scaffold_pole(tmp_path, "veille")
    ctx = await _ProbeAgent(poles_root=tmp_path).load_context()
    assert ctx.is_empty()
    assert ctx.all_records() == []


async def test_run_loads_context_then_acts(tmp_path: Path) -> None:
    _scaffold_pole(tmp_path, "veille")
    await memory.write_memory("veille", "s", "x", poles_root=tmp_path)
    result = await _ProbeAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.actions == ["x"]
