"""Tests unitaires de ``argos_ops.agents.changelog_bot`` (P22.G)."""

from __future__ import annotations

from argos_ops.agents.changelog_bot import (
    ChangelogResult,
    build_changelog_embed,
    render_changelog,
)
from argos_ops.product.git_history import Commit, group_by_type


def _commit(type_: str, desc: str, scope: str | None = None, breaking: bool = False) -> Commit:
    return Commit(
        sha="abc1234",
        type=type_,
        scope=scope,
        description=desc,
        breaking=breaking,
        raw_subject=f"{type_}: {desc}",
    )


def test_render_changelog_groups_by_type() -> None:
    commits = [
        _commit("feat", "ajout export PDF"),
        _commit("fix", "fix crash SSL"),
        _commit("chore", "bump deps"),
    ]
    sections = group_by_type(commits)
    md = render_changelog(
        period_label="v0.6 → v0.7",
        from_ref="v0.6",
        to_ref="v0.7",
        sections=sections,
    )
    assert "Nouveautés" in md
    assert "Corrections" in md
    assert "Maintenance" in md
    assert "ajout export PDF" in md


def test_render_marks_breaking_changes() -> None:
    commits = [_commit("feat", "nouvelle API auth", breaking=True)]
    sections = group_by_type(commits)
    md = render_changelog(
        period_label="recent",
        from_ref=None,
        to_ref="HEAD",
        sections=sections,
    )
    assert "💥" in md


def test_render_includes_scope_when_present() -> None:
    commits = [_commit("feat", "ajout export", scope="reports")]
    sections = group_by_type(commits)
    md = render_changelog(
        period_label="x",
        from_ref=None,
        to_ref="HEAD",
        sections=sections,
    )
    assert "**reports**" in md


def test_build_changelog_embed_yellow_when_drafted() -> None:
    result = ChangelogResult(period="x", commits_total=3, sections={"feat": []}, path=None)
    embed = build_changelog_embed(result)
    assert embed.color == 0xF1C40F


def test_build_changelog_embed_green_when_skipped() -> None:
    result = ChangelogResult(period="x", commits_total=0, sections={}, skipped_existing=True)
    embed = build_changelog_embed(result)
    assert embed.color == 0x2ECC71
