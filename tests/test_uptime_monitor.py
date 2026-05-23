"""Tests unitaires de :mod:`argos_ops.agents.uptime_monitor` (P22.C).

Couvre la logique pure : lecture YAML, classification report, formatting.
Aucun ping HTTP réel — les tests `check_all` sont volontairement absents
(I/O httpx).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.agents.uptime_monitor import (
    EndpointConfig,
    UptimeCheckResult,
    _format_check_value,
    build_report,
    load_endpoints,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _result(
    name: str,
    status: str,
    *,
    http_status: int | None = 200,
    latency_ms: float | None = 42.0,
    error: str | None = None,
) -> UptimeCheckResult:
    return UptimeCheckResult(
        endpoint=EndpointConfig(name=name, url=f"https://{name}.test/"),
        status=status,  # type: ignore[arg-type]
        http_status=http_status,
        latency_ms=latency_ms,
        error=error,
    )


# =============================================================================
# load_endpoints
# =============================================================================
def test_load_endpoints_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_endpoints(tmp_path / "nope.yaml") == []


def test_load_endpoints_raises_on_malformed_entry(tmp_path: Path) -> None:
    path = tmp_path / "endpoints.yaml"
    path.write_text(
        "endpoints:\n  - name: only-name\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mal form"):
        load_endpoints(path)


def test_load_endpoints_parses_valid_entries(tmp_path: Path) -> None:
    path = tmp_path / "endpoints.yaml"
    path.write_text(
        "endpoints:\n"
        "  - name: Site public\n"
        '    url: "https://omnividens.fr/"\n'
        "  - name: Admin\n"
        '    url: "https://ops.omnividens.fr/"\n'
        "    timeout_seconds: 5\n",
        encoding="utf-8",
    )
    endpoints = load_endpoints(path)
    assert len(endpoints) == 2
    assert endpoints[0].method == "GET"
    assert endpoints[1].timeout_seconds == 5.0


# =============================================================================
# build_report
# =============================================================================
def test_build_report_green_when_all_up() -> None:
    report = build_report([_result("a", "up"), _result("b", "up")])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_4xx_no_down() -> None:
    report = build_report(
        [_result("a", "up"), _result("b", "degraded", http_status=404)]
    )
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_any_down() -> None:
    report = build_report(
        [
            _result("a", "up"),
            _result("b", "degraded", http_status=404),
            _result("c", "down", http_status=None, error="timeout"),
        ]
    )
    assert report.alert_color == RED
    assert report.should_alert is True
    assert "1 down" in report.summary


# =============================================================================
# _format_check_value
# =============================================================================
def test_format_check_value_includes_status_and_latency() -> None:
    formatted = _format_check_value(_result("foo", "up", http_status=200, latency_ms=123.0))
    assert "HTTP 200" in formatted
    assert "123ms" in formatted
    assert "https://foo.test/" in formatted


def test_format_check_value_includes_error_when_present() -> None:
    formatted = _format_check_value(
        _result("foo", "down", http_status=None, error="ConnectError: refused")
    )
    assert "ConnectError" in formatted
