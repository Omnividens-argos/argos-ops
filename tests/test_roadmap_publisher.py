"""Tests unitaires de ``argos_ops.agents.roadmap_publisher`` (P22.G)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.roadmap_publisher import (
    RoadmapStats,
    _public_status,
    build_roadmap_embed,
    render_public_roadmap,
)
from argos_ops.product.annexe_d_parser import BotEntry, count_states, parse_annexe_d


def _entry(name: str, state: str, **overrides: object) -> BotEntry:
    return BotEntry(
        name=name,
        role=overrides.get("role", "Role"),  # type: ignore[arg-type]
        description=overrides.get("description", "Description"),  # type: ignore[arg-type]
        state=state,
        status_note=overrides.get("status_note"),  # type: ignore[arg-type]
        service=overrides.get("service", "Service Test"),  # type: ignore[arg-type]
    )


def test_parse_annexe_d_handles_missing_file(tmp_path: Path) -> None:
    assert parse_annexe_d(tmp_path / "missing.md") == []


def test_parse_annexe_d_real_format(tmp_path: Path) -> None:
    fake = tmp_path / "plan.md"
    fake.write_text(
        "# Annexe D — Catalogue\n\n"
        "### 1. Direction & Stratégie\n\n"
        "- [x] ✅ **DigestBuilder** · VP · KPIs jour J-1. *P4 livré 2026-05-08.*\n"
        "- [ ] ⬜ **StrategyBot** · CSO · Synthèse hebdo. *Sprint 9.*\n"
        "\n# Annexe E\n",
        encoding="utf-8",
    )
    entries = parse_annexe_d(fake)
    assert len(entries) == 2
    assert entries[0].name == "DigestBuilder"
    assert entries[0].state == "done"
    assert entries[1].state == "roadmap"


def test_public_status_strips_sprint_code() -> None:
    entry = _entry("X", "done", status_note="P22.C livré 2026-05-23.")
    public = _public_status(entry)
    assert "livré" in public
    assert "mai 2026" in public
    assert "P22" not in public


def test_render_public_roadmap_groups_by_service() -> None:
    entries = [
        _entry("A", "done", service="Service A", status_note="livré 2026-05-01"),
        _entry("B", "roadmap", service="Service A"),
        _entry("C", "done", service="Service B", status_note="livré 2026-04-01"),
    ]
    md = render_public_roadmap(entries)
    assert "## Service A" in md
    assert "## Service B" in md
    assert "**Livré**" in md
    assert "**À venir**" in md


def test_count_states() -> None:
    entries = [
        _entry("A", "done"),
        _entry("B", "done"),
        _entry("C", "partial"),
        _entry("D", "roadmap"),
    ]
    counts = count_states(entries)
    assert counts == {"done": 2, "partial": 1, "roadmap": 1}


def test_build_roadmap_embed_yellow_when_entries() -> None:
    stats = RoadmapStats(entries_total=10, done=5, partial=1, roadmap=4, services=3)
    embed = build_roadmap_embed(stats)
    assert embed.color == 0xF1C40F
