"""Tests unitaires de :mod:`argos_ops.agents.dw_monitor` (P22.D)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.dw_monitor import (
    DomainHit,
    build_report,
    cross_domains_with_breaches,
    load_domains,
    load_seen_hits,
    save_seen_hits,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def _hit(domain: str, breach: str, pwn_count: int = 1000) -> DomainHit:
    return DomainHit(
        customer_name=domain,
        domain=domain,
        breach_name=breach,
        pwn_count=pwn_count,
        breach_date="2025-01-01",
    )


def test_load_domains_empty_when_missing(tmp_path: Path) -> None:
    assert load_domains(tmp_path / "absent.yaml") == []


def test_load_domains_lowercases(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    path.write_text(
        "customers:\n  - name: Acme\n    domain: ACME.test\n", encoding="utf-8"
    )
    domains = load_domains(path)
    assert domains == [("Acme", "acme.test")]


def test_seen_hits_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen_hits({"a::b"}, path=path)
    assert load_seen_hits(path=path) == {"a::b"}


def test_cross_domains_finds_matches() -> None:
    breaches = [
        {"Domain": "acme.test", "Name": "AcmeBreach", "PwnCount": 1234, "BreachDate": "2025-01-01"},
        {"Domain": "other.test", "Name": "OtherBreach", "PwnCount": 0, "BreachDate": "2025-02-01"},
    ]
    hits = cross_domains_with_breaches([("Acme", "acme.test")], breaches)
    assert len(hits) == 1
    assert hits[0].breach_name == "AcmeBreach"
    assert hits[0].pwn_count == 1234


def test_cross_domains_returns_empty_when_no_match() -> None:
    breaches = [{"Domain": "other.test", "Name": "X", "PwnCount": 0, "BreachDate": ""}]
    hits = cross_domains_with_breaches([("Acme", "acme.test")], breaches)
    assert hits == []


def test_build_report_green_when_no_hit() -> None:
    report = build_report([], total_domains=2)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_hits() -> None:
    report = build_report([_hit("acme.test", "AcmeBreach")], total_domains=2)
    assert report.alert_color == YELLOW
    assert report.should_alert is True
