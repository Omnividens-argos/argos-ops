"""Tests des scripts du pôle Mémoire : ``memory_scan`` + ``capability_router`` (S7).

(``memory_cleaner`` est couvert par ``test_memoire_cleaner.py``.)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.memoire.scripts import CapabilityRouterScript, MemorySweepScript

OLD = datetime(2026, 6, 18, tzinfo=UTC) - timedelta(days=400)


def _pole(root: Path, pid: str, *, agent: str | None, reads: list[str]) -> None:
    (root / pid).mkdir(parents=True, exist_ok=True)
    reads_yaml = "[" + ", ".join(f'"{r}"' for r in reads) + "]"
    agent_block = "agent: null\n" if agent is None else f"agent:\n  name: {agent}\n"
    (root / pid / "pole.yaml").write_text(
        f"id: {pid}\nname: {pid}\n{agent_block}scripts: []\n"
        f"reads_cross_pole: {reads_yaml}\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


def _policy(root: Path, active: list[str]) -> None:
    (root / "memoire").mkdir(parents=True, exist_ok=True)
    active_yaml = "[" + ", ".join(active) + "]"
    (root / "memoire" / "policy.yaml").write_text(
        f"protect_important: true\nactive_for: {active_yaml}\ndefault_ttl_days: 180\n",
        encoding="utf-8",
    )


# =============================================================================
# memory_scan
# =============================================================================
async def test_scan_writes_plan_per_active_pole(tmp_path: Path) -> None:
    _policy(tmp_path, ["veille", "pub"])
    await memory.write_memory("veille", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    # pub : aucune mémoire → sera sauté.
    result = await MemorySweepScript(poles_root=tmp_path).run()
    assert result.status == "success"
    assert len(result.written) == 1  # seul veille a de la mémoire
    assert result.written[0].kind == "curation-plan"
    assert "veille" in result.written[0].tags


async def test_scan_skips_when_no_active_pole(tmp_path: Path) -> None:
    _policy(tmp_path, [])
    result = await MemorySweepScript(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.written == []


async def test_scan_is_idempotent(tmp_path: Path) -> None:
    _policy(tmp_path, ["veille"])
    await memory.write_memory("veille", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    await MemorySweepScript(poles_root=tmp_path).run()
    await MemorySweepScript(poles_root=tmp_path).run()
    # Même état mémoire ⇒ même corps de fait ⇒ pas de doublon.
    scan_mem = await memory.read_memory("memoire", "memory_scan", poles_root=tmp_path)
    assert len(scan_mem) == 1


# =============================================================================
# capability_router
# =============================================================================
async def test_router_writes_audit_fact_sane(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=[])
    _pole(tmp_path, "memoire", agent="MemoireAgent", reads=["*"])
    await memory.write_memory("veille", "s", "fait", poles_root=tmp_path)
    result = await CapabilityRouterScript(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.written[0].kind == "wiring-audit"
    # Sain ⇒ pas important.
    assert result.written[0].important is False


async def test_router_flags_important_on_warning(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=["ghost"])  # orphan → warning
    _pole(tmp_path, "memoire", agent="MemoireAgent", reads=["*"])
    result = await CapabilityRouterScript(poles_root=tmp_path).run()
    assert result.written[0].important is True
