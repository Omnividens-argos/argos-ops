"""Tests unitaires de ``argos_ops.agents.release_notes`` (P22.G)."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.release_notes import (
    ReleaseNotesStats,
    _draft_release,
    _load_spec,
    _persist_spec,
    build_release_notes_embed,
    render_release_notes,
)


def test_render_release_notes_includes_all_sections() -> None:
    entry = {
        "version": "v0.7",
        "date": "2026-06-01",
        "highlights": ["Nouveau scan 3 fois plus rapide"],
        "improvements": ["UI plus claire"],
        "fixes": ["Plus de crash sur SSL invalide"],
        "breaking_changes": ["L'ancien export CSV est retiré"],
    }
    md = render_release_notes(entry)
    assert "Argos v0.7" in md
    assert "Nouveau scan" in md
    assert "UI plus claire" in md
    assert "SSL invalide" in md
    assert "💥" in md or "Changements incompatibles" in md


def test_load_and_persist_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    payload = {
        "releases": [
            {"version": "v0.6", "date": "2026-05-01", "status": "drafted"},
            {"version": "v0.7", "date": "2026-06-01", "status": "pending"},
        ]
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    releases = _load_spec(path)
    assert len(releases) == 2
    releases[1]["status"] = "drafted"
    _persist_spec(path, releases)
    reloaded = _load_spec(path)
    assert reloaded[1]["status"] == "drafted"


def test_draft_release_writes_md_with_frontmatter(tmp_path: Path) -> None:
    entry = {
        "version": "v0.7",
        "date": "2026-06-01",
        "highlights": ["A"],
    }
    path = _draft_release(entry, tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    front = yaml.safe_load(content.split("---\n", 2)[1])
    assert front["version"] == "v0.7"
    assert front["status"] == "drafted"


def test_build_release_notes_embed_yellow_when_drafted() -> None:
    embed = build_release_notes_embed(
        ReleaseNotesStats(releases_seen=2, drafted=1, drafts=["v0.7.md"])
    )
    assert embed.color == 0xF1C40F
