"""Tests unitaires de :mod:`argos_ops.agents.dependency_auditor` (P22.C).

Couvre :
- ``parse_requirements`` : extraction + skip comments / -r / dedup
- ``_map_severity`` : mapping float et CVSS string
- ``build_report`` : couleur RED/YELLOW/GREEN
"""

from __future__ import annotations

from typing import Any

from argos_ops.agents.dependency_auditor import (
    Dependency,
    Vulnerability,
    _map_severity,
    build_report,
    parse_requirements,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _vuln(name: str, severity: str) -> Vulnerability:
    return Vulnerability(
        dep=Dependency(name=name, version="1.0.0"),
        vuln_id=f"GHSA-{name}",
        severity=severity,  # type: ignore[arg-type]
        summary=f"test vuln on {name}",
    )


# =============================================================================
# parse_requirements
# =============================================================================
def test_parse_requirements_extracts_name_version() -> None:
    content = "httpx==0.28.0\nfastapi==0.115.0\n"
    deps = parse_requirements(content)
    assert len(deps) == 2
    assert deps[0].name == "httpx"
    assert deps[0].version == "0.28.0"


def test_parse_requirements_skips_comments_and_directives() -> None:
    content = (
        "# this is a comment\n"
        "-r other.txt\n"
        "--index-url https://example.com\n"
        "httpx==0.28.0\n"
    )
    deps = parse_requirements(content)
    assert len(deps) == 1
    assert deps[0].name == "httpx"


def test_parse_requirements_dedups_identical_lines() -> None:
    content = "httpx==0.28.0\nhttpx==0.28.0\n"
    deps = parse_requirements(content)
    assert len(deps) == 1


def test_parse_requirements_skips_blank_lines_and_normalizes_case() -> None:
    content = "\n\nHTTPX==0.28.0\n"
    deps = parse_requirements(content)
    assert len(deps) == 1
    assert deps[0].name == "httpx"


# =============================================================================
# _map_severity
# =============================================================================
def test_map_severity_returns_unknown_on_none_or_empty() -> None:
    assert _map_severity(None) == "UNKNOWN"
    assert _map_severity([]) == "UNKNOWN"


def test_map_severity_maps_critical_from_float() -> None:
    raw: list[dict[str, Any]] = [{"score": 9.5}]
    assert _map_severity(raw) == "CRITICAL"


def test_map_severity_maps_high() -> None:
    assert _map_severity([{"score": 7.5}]) == "HIGH"


def test_map_severity_maps_medium() -> None:
    assert _map_severity([{"score": 5.0}]) == "MEDIUM"


def test_map_severity_maps_low() -> None:
    assert _map_severity([{"score": 2.0}]) == "LOW"


def test_map_severity_parses_numeric_string_score() -> None:
    """OSV.dev passe parfois ``score`` comme string ``"9.8"`` plutôt que float."""
    raw: list[dict[str, Any]] = [{"score": "9.8"}]
    assert _map_severity(raw) == "CRITICAL"


def test_map_severity_extracts_last_number_from_cvss_vector() -> None:
    """Le score réel dans un vector CVSS est toujours le dernier nombre :
    ``CVSS:3.1/AV:N/.../A:H/9.8`` → 9.8 (CRITICAL). On prend donc le
    dernier match du regex, pas le premier (sinon on récupèrerait la
    version CVSS ``3.1`` et on classerait LOW à tort)."""
    raw: list[dict[str, Any]] = [
        {"score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/9.8"}
    ]
    assert _map_severity(raw) == "CRITICAL"


def test_map_severity_takes_max_when_multiple() -> None:
    raw: list[dict[str, Any]] = [{"score": 2.0}, {"score": 8.0}]
    assert _map_severity(raw) == "HIGH"


# =============================================================================
# build_report
# =============================================================================
def test_build_report_green_when_no_vulns() -> None:
    report = build_report([], total_deps_scanned=50)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_green_when_only_low() -> None:
    report = build_report([_vuln("foo", "LOW")], total_deps_scanned=50)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_medium_only() -> None:
    report = build_report([_vuln("foo", "MEDIUM")], total_deps_scanned=50)
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_high() -> None:
    report = build_report(
        [_vuln("foo", "MEDIUM"), _vuln("bar", "HIGH")], total_deps_scanned=50
    )
    assert report.alert_color == RED
    assert report.should_alert is True


def test_build_report_red_when_critical() -> None:
    report = build_report([_vuln("foo", "CRITICAL")], total_deps_scanned=50)
    assert report.alert_color == RED
