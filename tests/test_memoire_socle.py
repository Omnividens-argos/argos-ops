"""Tests des primitives socle ajoutées en S7 : ``read_record`` + ``delete_memory``.

Hermétique (tmp_path), pas de DB ni de réseau. Ces primitives sont la brique
bas-niveau du pôle Mémoire (re-vérification + hard delete) — leur garde-fou
``important`` vit dans le pôle Mémoire, pas ici.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory


async def test_read_record_roundtrip(tmp_path: Path) -> None:
    rec = await memory.write_memory("veille", "s", "un fait", poles_root=tmp_path)
    got = await memory.read_record("veille", "s", rec.id, poles_root=tmp_path)
    assert got is not None
    assert got.id == rec.id
    assert got.body == "un fait"


async def test_read_record_missing_is_none(tmp_path: Path) -> None:
    assert await memory.read_record("veille", "s", "deadbeef0000", poles_root=tmp_path) is None


async def test_delete_memory_removes_file(tmp_path: Path) -> None:
    rec = await memory.write_memory("veille", "s", "à supprimer", poles_root=tmp_path)
    assert await memory.delete_memory("veille", "s", rec.id, poles_root=tmp_path) is True
    # Plus lisible après suppression.
    assert await memory.read_record("veille", "s", rec.id, poles_root=tmp_path) is None
    assert await memory.read_memory("veille", "s", poles_root=tmp_path) == []


async def test_delete_memory_idempotent_on_missing(tmp_path: Path) -> None:
    # Supprimer un id absent renvoie False (pas d'exception).
    assert await memory.delete_memory("veille", "s", "deadbeef0000", poles_root=tmp_path) is False


async def test_delete_is_low_level_no_important_guard(tmp_path: Path) -> None:
    # delete_memory est volontairement SANS garde-fou : il supprime même un fait
    # important. La protection vit dans le pôle Mémoire (cleaner), testée ailleurs.
    rec = await memory.write_memory("veille", "s", "x", important=True, poles_root=tmp_path)
    assert await memory.delete_memory("veille", "s", rec.id, poles_root=tmp_path) is True
