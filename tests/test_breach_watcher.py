"""Tests unitaires de :mod:`argos_ops.agents.breach_watcher` (P22.D)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.agents.breach_watcher import (
    BreachEvent,
    Customer,
    _extract_domain,
    _is_critical,
    build_report,
    cross_with_customers,
    load_customers,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _event(
    *,
    domain: str | None,
    title: str = "Test breach",
    summary: str = "",
    published_at: datetime | None = None,
) -> BreachEvent:
    return BreachEvent(
        source="HIBP",
        title=title,
        published_at=published_at,
        summary=summary,
        affected_domain=domain,
    )


def test_extract_domain_finds_first_match() -> None:
    assert _extract_domain("breach at example.com today") == "example.com"
    assert _extract_domain("no domain here") is None


def test_is_critical_flags_keyword_passwords() -> None:
    assert _is_critical(_event(domain="x.test", summary="passwords leaked")) is True
    assert _is_critical(_event(domain="x.test", summary="emails leaked")) is False


def test_load_customers_empty_when_missing(tmp_path: Path) -> None:
    assert load_customers(tmp_path / "absent.yaml") == []


def test_load_customers_parses_entries(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    path.write_text(
        "customers:\n"
        "  - name: Acme\n"
        "    domain: acme.test\n",
        encoding="utf-8",
    )
    customers = load_customers(path)
    assert len(customers) == 1
    assert customers[0].domain == "acme.test"


def test_cross_with_customers_returns_empty_when_no_match() -> None:
    events = [_event(domain="other.test")]
    customers = [Customer(name="Acme", domain="acme.test")]
    assert cross_with_customers(events, customers) == []


def test_cross_with_customers_matches_domain() -> None:
    events = [_event(domain="acme.test", summary="passwords leaked")]
    customers = [Customer(name="Acme", domain="acme.test")]
    matches = cross_with_customers(events, customers)
    assert len(matches) == 1
    assert matches[0].is_critical is True


def test_cross_with_customers_skips_events_outside_window() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    old_event = _event(domain="acme.test", published_at=now - timedelta(days=60))
    customers = [Customer(name="Acme", domain="acme.test")]
    assert cross_with_customers([old_event], customers, now=now) == []


def test_build_report_green_when_no_match() -> None:
    report = build_report([], total_breaches=10)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_warn_only() -> None:
    matches = cross_with_customers(
        [_event(domain="acme.test", summary="emails leaked")],
        [Customer(name="Acme", domain="acme.test")],
    )
    report = build_report(matches, total_breaches=1)
    assert report.alert_color == YELLOW


def test_build_report_red_when_critical() -> None:
    matches = cross_with_customers(
        [_event(domain="acme.test", summary="passwords leaked")],
        [Customer(name="Acme", domain="acme.test")],
    )
    report = build_report(matches, total_breaches=1)
    assert report.alert_color == RED
