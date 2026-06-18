"""Tests des primitives mémoire de script (socle archi v2).

Hermétique : toute la mémoire est écrite sous ``tmp_path`` (jamais le vrai
``data/poles/``). Pas de DB, pas de réseau.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from argos_ops.poles import memory


async def test_write_then_read(tmp_path: Path) -> None:
    rec = await memory.write_memory(
        "veille",
        "trend_spotter",
        "Sujet chaud : faille VPN Fortinet exploitée dans la nature.",
        kind="signal",
        tags=("cyber", "vpn"),
        poles_root=tmp_path,
    )
    assert rec.kind == "signal"
    assert rec.tags == ("cyber", "vpn")
    assert rec.important is False

    got = await memory.read_memory("veille", "trend_spotter", poles_root=tmp_path)
    assert len(got) == 1
    assert got[0].id == rec.id
    assert got[0].body.startswith("Sujet chaud")


async def test_write_is_idempotent_and_preserves_created_at(tmp_path: Path) -> None:
    early = datetime(2026, 1, 1, tzinfo=UTC)
    first = await memory.write_memory(
        "veille", "s", "même corps exact", created_at=early, poles_root=tmp_path
    )
    second = await memory.write_memory("veille", "s", "même corps exact", poles_root=tmp_path)

    assert first.id == second.id
    assert second.created_at == early  # created_at de la 1re écriture préservé
    got = await memory.read_memory("veille", "s", poles_root=tmp_path)
    assert len(got) == 1  # pas de doublon


async def test_id_normalizes_whitespace_and_case(tmp_path: Path) -> None:
    a = await memory.write_memory("veille", "s", "Un Fait", poles_root=tmp_path)
    b = await memory.write_memory("veille", "s", "  un   fait ", poles_root=tmp_path)
    assert a.id == b.id


async def test_flag_important_and_no_downgrade(tmp_path: Path) -> None:
    rec = await memory.write_memory("veille", "s", "fait à protéger", poles_root=tmp_path)
    flagged = await memory.flag_important("veille", "s", rec.id, poles_root=tmp_path)
    assert flagged is not None
    assert flagged.important is True

    # Ré-écrire le même corps avec important=False ne doit JAMAIS déclasser.
    again = await memory.write_memory(
        "veille", "s", "fait à protéger", important=False, poles_root=tmp_path
    )
    assert again.important is True


async def test_unflag_important(tmp_path: Path) -> None:
    rec = await memory.write_memory("veille", "s", "x", important=True, poles_root=tmp_path)
    unflagged = await memory.flag_important(
        "veille", "s", rec.id, important=False, poles_root=tmp_path
    )
    assert unflagged is not None
    assert unflagged.important is False


async def test_flag_missing_returns_none(tmp_path: Path) -> None:
    assert await memory.flag_important("veille", "s", "deadbeef0000", poles_root=tmp_path) is None


async def test_read_missing_script_is_empty(tmp_path: Path) -> None:
    assert await memory.read_memory("veille", "ghost", poles_root=tmp_path) == []


async def test_empty_body_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="corps vide"):
        await memory.write_memory("veille", "s", "   ", poles_root=tmp_path)


async def test_read_pole_memory_groups_by_script(tmp_path: Path) -> None:
    await memory.write_memory("veille", "a", "fait a", poles_root=tmp_path)
    await memory.write_memory("veille", "b", "fait b1", poles_root=tmp_path)
    await memory.write_memory("veille", "b", "fait b2", poles_root=tmp_path)

    pole_mem = await memory.read_pole_memory("veille", poles_root=tmp_path)
    assert set(pole_mem) == {"a", "b"}
    assert len(pole_mem["a"]) == 1
    assert len(pole_mem["b"]) == 2


async def test_records_sorted_newest_first(tmp_path: Path) -> None:
    old = datetime(2026, 1, 1, tzinfo=UTC)
    new = datetime(2026, 6, 1, tzinfo=UTC)
    await memory.write_memory("veille", "s", "ancien", created_at=old, poles_root=tmp_path)
    await memory.write_memory("veille", "s", "récent", created_at=new, poles_root=tmp_path)
    got = await memory.read_memory("veille", "s", poles_root=tmp_path)
    assert [r.body for r in got] == ["récent", "ancien"]


def test_compute_record_id_is_stable() -> None:
    assert memory.compute_record_id("hello") == memory.compute_record_id("  HELLO ")
    assert len(memory.compute_record_id("x")) == 12
