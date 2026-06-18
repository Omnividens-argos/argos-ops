"""Tests de l'audit du câblage inter-pôles — CapabilityRouter v2 (archi v2, S7)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.memoire.wiring import audit_wiring


def _pole(root: Path, pid: str, *, agent: str | None, reads: list[str]) -> None:
    (root / pid).mkdir(parents=True, exist_ok=True)
    reads_yaml = "[" + ", ".join(f'"{r}"' for r in reads) + "]"
    agent_block = "agent: null\n" if agent is None else f"agent:\n  name: {agent}\n"
    (root / pid / "pole.yaml").write_text(
        f"id: {pid}\nname: {pid}\n{agent_block}scripts: []\n"
        f"reads_cross_pole: {reads_yaml}\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


async def test_sane_wiring_no_warning(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=[])
    _pole(tmp_path, "direction", agent="DirectionAgent", reads=["*"])
    _pole(tmp_path, "memoire", agent="MemoireAgent", reads=["*"])
    await memory.write_memory("veille", "s", "un fait", poles_root=tmp_path)

    audit = await audit_wiring(poles_root=tmp_path)
    assert audit.should_alert is False
    assert audit.n_warning == 0
    # veille est lu par direction ET memoire (wildcards).
    readers = {e.source for e in audit.edges if e.target == "veille"}
    assert {"direction", "memoire"} <= readers


async def test_wildcard_edges_flagged(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=[])
    _pole(tmp_path, "memoire", agent="MemoireAgent", reads=["*"])
    audit = await audit_wiring(poles_root=tmp_path)
    edge = next(e for e in audit.edges if e.source == "memoire" and e.target == "veille")
    assert edge.via_wildcard is True


async def test_orphan_target_is_warning(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=["ghost"])
    audit = await audit_wiring(poles_root=tmp_path)
    orphans = [a for a in audit.anomalies if a.kind == "orphan"]
    assert len(orphans) == 1
    assert orphans[0].pole == "veille"
    assert orphans[0].severity == "warning"
    assert audit.should_alert is True


async def test_self_reference_is_info(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=["veille"])
    audit = await audit_wiring(poles_root=tmp_path)
    selfs = [a for a in audit.anomalies if a.kind == "self_reference"]
    assert len(selfs) == 1
    assert selfs[0].severity == "info"
    # Pas d'arête vers soi-même.
    assert all(not (e.source == "veille" and e.target == "veille") for e in audit.edges)


async def test_empty_explicit_target_is_info(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", reads=["pub"])
    _pole(tmp_path, "pub", agent="PubAgent", reads=[])  # pas de mémoire
    audit = await audit_wiring(poles_root=tmp_path)
    empties = [a for a in audit.anomalies if a.kind == "empty_target"]
    assert len(empties) == 1
    assert empties[0].severity == "info"
    assert audit.should_alert is False  # info seul ne déclenche pas d'alerte


async def test_unread_producer_is_warning(tmp_path: Path) -> None:
    # Deux pôles isolés, aucun wildcard. A produit de la mémoire mais personne ne le lit.
    _pole(tmp_path, "alpha", agent="AlphaAgent", reads=[])
    _pole(tmp_path, "beta", agent="BetaAgent", reads=[])
    await memory.write_memory("alpha", "s", "fait orphelin", poles_root=tmp_path)
    audit = await audit_wiring(poles_root=tmp_path)
    unread = [a for a in audit.anomalies if a.kind == "unread_producer"]
    assert any(a.pole == "alpha" for a in unread)
    # beta n'a pas de mémoire → pas flaggé.
    assert all(a.pole != "beta" for a in unread)
    assert audit.should_alert is True


async def test_agentless_pole_reads_nothing(tmp_path: Path) -> None:
    # Le SRE (agent null) ne lit rien — aucune arête sortante depuis lui.
    _pole(tmp_path, "sre", agent=None, reads=[])
    _pole(tmp_path, "memoire", agent="MemoireAgent", reads=["*"])
    audit = await audit_wiring(poles_root=tmp_path)
    assert all(e.source != "sre" for e in audit.edges)
