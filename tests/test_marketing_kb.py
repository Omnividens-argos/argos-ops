"""Tests de la KB éditoriale éditable du pôle Marketing (archi v2, S2)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.marketing import kb


def test_upsert_derives_slug_and_roundtrips(tmp_path: Path) -> None:
    entry = kb.upsert_kb_entry(
        title="Proposition de valeur Argos",
        body="on scanne, vous corrigez",
        tags=("pitch",),
        poles_root=tmp_path,
    )
    assert entry.slug == "proposition-de-valeur-argos"
    loaded = kb.load_kb_entry(entry.slug, poles_root=tmp_path)
    assert loaded is not None
    assert loaded.title == "Proposition de valeur Argos"
    assert loaded.tags == ("pitch",)


def test_upsert_updates_existing(tmp_path: Path) -> None:
    kb.upsert_kb_entry(title="Personas", body="v1", slug="personas", poles_root=tmp_path)
    kb.upsert_kb_entry(title="Personas", body="v2", slug="personas", poles_root=tmp_path)
    entries = kb.load_kb(poles_root=tmp_path)
    assert len(entries) == 1
    assert entries[0].body == "v2"


def test_delete(tmp_path: Path) -> None:
    kb.upsert_kb_entry(title="À jeter", body="x", slug="a-jeter", poles_root=tmp_path)
    assert kb.delete_kb_entry("a-jeter", poles_root=tmp_path) is True
    assert kb.delete_kb_entry("a-jeter", poles_root=tmp_path) is False
    assert kb.load_kb_entry("a-jeter", poles_root=tmp_path) is None


def test_load_empty(tmp_path: Path) -> None:
    assert kb.load_kb(poles_root=tmp_path) == []


def test_load_kb_skips_corrupt_file(tmp_path: Path) -> None:
    kb.upsert_kb_entry(title="Bonne fiche", body="x", slug="ok", poles_root=tmp_path)
    bad = kb.kb_dir(poles_root=tmp_path) / "bad.md"
    bad.write_text("---\nfoo: [unclosed\n---\n\nbody\n", encoding="utf-8")
    entries = kb.load_kb(poles_root=tmp_path)  # best-effort
    assert [e.slug for e in entries] == ["ok"]
