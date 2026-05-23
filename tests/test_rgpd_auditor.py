"""Tests unitaires de :mod:`argos_ops.agents.rgpd_auditor` (P22.E)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.rgpd_auditor import (
    build_report,
    cross_reference,
    load_registry_paths,
    scan_repo,
)
from argos_ops.compliance import PIIFinding
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _finding(rel_path: Path, *, category: str = "email") -> PIIFinding:
    return PIIFinding(path=rel_path, line_no=1, category=category, snippet="email = 'x'")  # type: ignore[arg-type]


# =============================================================================
# load_registry_paths
# =============================================================================
def test_load_registry_paths_missing(tmp_path: Path) -> None:
    assert load_registry_paths(tmp_path / "nope.yaml") == []


def test_load_registry_paths_parses(tmp_path: Path) -> None:
    p = tmp_path / "reg.yaml"
    p.write_text(
        "traitements:\n"
        "  - nom: 'lead'\n"
        "    paths:\n"
        "      - argos_ops/agents/outbound_bot.py\n"
        "      - argos_ops/sales/\n",
        encoding="utf-8",
    )
    prefixes = load_registry_paths(p)
    assert "argos_ops/agents/outbound_bot.py" in prefixes
    assert "argos_ops/sales" in prefixes  # trailing slash stripped


# =============================================================================
# scan_repo
# =============================================================================
def test_scan_repo_recurses(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.py").write_text("email = 'x'\n", encoding="utf-8")
    (sub / "b.py").write_text("# nothing\n", encoding="utf-8")
    findings = scan_repo(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "email"


def test_scan_repo_missing_root(tmp_path: Path) -> None:
    assert scan_repo(tmp_path / "nope") == []


# =============================================================================
# cross_reference
# =============================================================================
def test_cross_reference_covered(tmp_path: Path) -> None:
    repo_root = tmp_path
    finding = _finding(repo_root / "argos_ops" / "agents" / "outbound_bot.py")
    out = cross_reference([finding], ["argos_ops/agents/outbound_bot.py"], repo_root=repo_root)
    assert out[0].covered is True


def test_cross_reference_prefix_match(tmp_path: Path) -> None:
    repo_root = tmp_path
    finding = _finding(repo_root / "argos_ops" / "sales" / "scraper.py")
    out = cross_reference([finding], ["argos_ops/sales"], repo_root=repo_root)
    assert out[0].covered is True


def test_cross_reference_uncovered(tmp_path: Path) -> None:
    repo_root = tmp_path
    finding = _finding(repo_root / "argos_ops" / "agents" / "outbound_bot.py")
    out = cross_reference([finding], ["argos_ops/sales/"], repo_root=repo_root)
    assert out[0].covered is False


# =============================================================================
# build_report
# =============================================================================
def test_build_report_red_when_registry_missing() -> None:
    report = build_report([], total_scanned=10, registry_present=False)
    assert report.alert_color == RED
    assert report.should_alert is True


def test_build_report_green_when_all_covered(tmp_path: Path) -> None:
    repo_root = tmp_path
    finding = _finding(repo_root / "argos_ops" / "agents" / "x.py")
    coverage = cross_reference([finding], ["argos_ops/agents"], repo_root=repo_root)
    report = build_report(coverage, total_scanned=5, registry_present=True)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_some_uncovered(tmp_path: Path) -> None:
    repo_root = tmp_path
    finding = _finding(repo_root / "argos_ops" / "agents" / "x.py")
    coverage = cross_reference([finding], [], repo_root=repo_root)
    report = build_report(coverage, total_scanned=5, registry_present=True)
    assert report.alert_color == YELLOW