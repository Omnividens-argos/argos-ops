"""Tests unitaires de :mod:`argos_ops.agents.cve_monitor` (P22.D)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.cve_monitor import (
    CVEAlert,
    StackPackage,
    build_report,
    load_seen_vulns,
    load_stack_packages,
    save_seen_vulns,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _alert(severity: str) -> CVEAlert:
    return CVEAlert(
        package=StackPackage(
            customer_name="Acme", ecosystem="PyPI", name="django", version="4.0.0"
        ),
        vuln_id=f"GHSA-{severity}",
        severity=severity,  # type: ignore[arg-type]
        summary=f"test {severity}",
    )


def test_load_stack_packages_empty_when_missing(tmp_path: Path) -> None:
    assert load_stack_packages(tmp_path / "absent.yaml") == []


def test_load_stack_packages_parses_entries(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    path.write_text(
        "customers:\n"
        "  - name: Acme\n"
        "    domain: acme.test\n"
        "    stack:\n"
        "      - ecosystem: PyPI\n"
        "        name: django\n"
        "        version: '4.2.1'\n"
        "      - ecosystem: npm\n"
        "        name: lodash\n",
        encoding="utf-8",
    )
    packages = load_stack_packages(path)
    assert len(packages) == 2
    assert packages[0].name == "django"
    assert packages[1].version is None


def test_save_and_load_seen_vulns_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen_vulns({"CVE-1", "CVE-2"}, path=path)
    assert load_seen_vulns(path=path) == {"CVE-1", "CVE-2"}


def test_build_report_green_when_no_alert() -> None:
    report = build_report([], total_packages=5)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_medium_only() -> None:
    report = build_report([_alert("MEDIUM")], total_packages=5)
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_high() -> None:
    report = build_report([_alert("HIGH")], total_packages=5)
    assert report.alert_color == RED


def test_build_report_red_when_critical() -> None:
    report = build_report([_alert("CRITICAL")], total_packages=5)
    assert report.alert_color == RED
