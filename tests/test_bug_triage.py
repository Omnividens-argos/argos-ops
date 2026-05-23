"""Tests unitaires de ``argos_ops.agents.bug_triage`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.bug_triage import (
    BugTriageStats,
    _persist_triage,
    build_bug_triage_embed,
    classify_severity,
    triage_issues,
)


def test_classify_severity_p0_security_keyword() -> None:
    assert classify_severity("XSS dans le rapport", "Stack trace...") == "P0"


def test_classify_severity_p1_bug_keyword() -> None:
    assert classify_severity("Le scan crash sur API", "...") == "P1"


def test_classify_severity_p2_default() -> None:
    assert classify_severity("Question sur la doc", "...") == "P2"


def test_classify_severity_respects_explicit_label() -> None:
    # Pas d'override implicite — c'est le rôle du founder via PR labels.
    # Mais si un label "security/critical" est dans la liste, c'est P0.
    assert classify_severity("Petite question", "...", labels=["security"]) == "P0"


def test_triage_issues_orders_by_severity() -> None:
    issues = [
        {"number": 1, "title": "Question UI", "body": "", "labels": []},
        {"number": 2, "title": "Bug crash export", "body": "", "labels": []},
        {"number": 3, "title": "XSS dans rapport", "body": "", "labels": []},
    ]
    stats = triage_issues(issues)
    # Trié P0 → P1 → P2
    assert stats.triaged[0].severity == "P0"
    assert stats.triaged[1].severity == "P1"
    assert stats.triaged[2].severity == "P2"
    assert stats.p0 == 1 and stats.p1 == 1 and stats.p2 == 1


def test_persist_triage_writes_yaml(tmp_path: Path) -> None:
    issues = [{"number": 42, "title": "Bug crash", "body": "", "labels": []}]
    stats = triage_issues(issues)
    path = tmp_path / "triage_2026-05-23.yaml"
    _persist_triage(path, stats, day=date(2026, 5, 23))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["triage_date"] == "2026-05-23"
    assert raw["issues"][0]["severity"] == "P1"
    assert raw["issues"][0]["suggested_label"] == "severity/major"


def test_embed_red_when_p0() -> None:
    stats = BugTriageStats(issues_total=1, p0=1)
    assert build_bug_triage_embed(stats).color == 0xE74C3C


def test_embed_orange_when_p1_only() -> None:
    stats = BugTriageStats(issues_total=1, p1=1)
    assert build_bug_triage_embed(stats).color == 0xE67E22


def test_embed_green_when_no_issues() -> None:
    stats = BugTriageStats()
    assert build_bug_triage_embed(stats).color == 0x2ECC71
