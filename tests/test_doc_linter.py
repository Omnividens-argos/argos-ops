"""Tests :mod:`argos_ops.agents.doc_linter`."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.doc_linter import (
    _extract_anchors,
    _slugify_heading,
    build_report,
    discover_docs,
    lint_file,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# slugify / anchors
# =============================================================================
def test_slugify_heading_lowercases_and_dashes() -> None:
    assert _slugify_heading("Section Importante !") == "section-importante"


def test_extract_anchors_collects_all_headings() -> None:
    text = "# Titre\n\n## Sous section\n\n### Détails"
    anchors = _extract_anchors(text)
    assert "titre" in anchors
    assert "sous-section" in anchors
    assert "détails" in anchors


# =============================================================================
# lint_file
# =============================================================================
def test_lint_file_detects_missing_file(tmp_path: Path) -> None:
    src = tmp_path / "src.md"
    src.write_text("Voir [autre](./missing.md) pour plus.", encoding="utf-8")
    _, issues = lint_file(src, root=tmp_path)
    assert len(issues) == 1
    assert issues[0].kind == "missing_file"


def test_lint_file_detects_missing_anchor(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Existant\n\n## Autre", encoding="utf-8")
    src = tmp_path / "src.md"
    src.write_text("[lien](./target.md#absent)", encoding="utf-8")
    _, issues = lint_file(src, root=tmp_path)
    assert len(issues) == 1
    assert issues[0].kind == "missing_anchor"


def test_lint_file_accepts_valid_link_with_anchor(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Section\n\n## Autre", encoding="utf-8")
    src = tmp_path / "src.md"
    src.write_text("[lien](./target.md#section)", encoding="utf-8")
    checked, issues = lint_file(src, root=tmp_path)
    assert checked == 1
    assert issues == []


def test_lint_file_skips_external_urls(tmp_path: Path) -> None:
    src = tmp_path / "src.md"
    src.write_text(
        "[ext](https://example.com) [mail](mailto:x@x.fr)", encoding="utf-8"
    )
    checked, issues = lint_file(src, root=tmp_path)
    assert checked == 0
    assert issues == []


def test_lint_file_ignores_images(tmp_path: Path) -> None:
    src = tmp_path / "src.md"
    src.write_text("![alt](./img.png)", encoding="utf-8")
    checked, _issues = lint_file(src, root=tmp_path)
    assert checked == 0


# =============================================================================
# build_report
# =============================================================================
def test_build_report_green_when_no_issue() -> None:
    report = build_report(files_scanned=2, links_checked=10, issues=[])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_only_anchor() -> None:
    from argos_ops.agents.doc_linter import LinkIssue

    issue = LinkIssue(
        source_file=Path("/x"),
        line_number=1,
        link_text="t",
        target="./x.md#absent",
        kind="missing_anchor",
        detail="x",
    )
    report = build_report(files_scanned=1, links_checked=1, issues=[issue])
    assert report.alert_color == YELLOW


def test_build_report_red_when_missing_file() -> None:
    from argos_ops.agents.doc_linter import LinkIssue

    issue = LinkIssue(
        source_file=Path("/x"),
        line_number=1,
        link_text="t",
        target="./gone.md",
        kind="missing_file",
        detail="x",
    )
    report = build_report(files_scanned=1, links_checked=1, issues=[issue])
    assert report.alert_color == RED


# =============================================================================
# discover_docs
# =============================================================================
def test_discover_docs_finds_md_in_docs_subdir(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    docs = discover_docs(tmp_path)
    names = {d.name for d in docs}
    assert "a.md" in names
    assert "README.md" in names
