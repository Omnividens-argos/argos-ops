"""Tests unitaires de :mod:`argos_ops.agents.ssl_expirer` (P22.C).

Couvre :
- ``_extract_host_port`` : skip non-HTTPS, défaut port 443
- ``_parse_cert_expiry`` : parsing format stdlib + tolérance
- ``build_report`` : couleur RED/YELLOW/GREEN
"""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.agents.ssl_expirer import (
    SslCheckResult,
    _extract_host_port,
    _parse_cert_expiry,
    build_report,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _result(name: str, status: str, *, days: float | None = 100.0) -> SslCheckResult:
    return SslCheckResult(
        name=name,
        host=f"{name}.test",
        port=443,
        expires_at=datetime.now(UTC),
        days_remaining=days,
        status=status,  # type: ignore[arg-type]
        error=None,
    )


# =============================================================================
# _extract_host_port
# =============================================================================
def test_extract_host_port_returns_none_for_http() -> None:
    assert _extract_host_port("http://omnividens.fr/") is None


def test_extract_host_port_returns_none_for_invalid_url() -> None:
    assert _extract_host_port("not-a-url") is None


def test_extract_host_port_default_443_for_https() -> None:
    assert _extract_host_port("https://omnividens.fr/") == ("omnividens.fr", 443)


def test_extract_host_port_explicit_port() -> None:
    assert _extract_host_port("https://ops.omnividens.fr:8443/foo") == (
        "ops.omnividens.fr",
        8443,
    )


# =============================================================================
# _parse_cert_expiry
# =============================================================================
def test_parse_cert_expiry_standard_format() -> None:
    cert = {"notAfter": "Jun 15 12:00:00 2030 GMT"}
    parsed = _parse_cert_expiry(cert)
    assert parsed is not None
    assert parsed.year == 2030
    assert parsed.tzinfo is UTC


def test_parse_cert_expiry_returns_none_when_not_after_absent() -> None:
    assert _parse_cert_expiry({}) is None


def test_parse_cert_expiry_returns_none_when_not_string() -> None:
    assert _parse_cert_expiry({"notAfter": 12345}) is None


# =============================================================================
# build_report
# =============================================================================
def test_build_report_green_when_all_ok() -> None:
    report = build_report([_result("a", "ok"), _result("b", "ok")])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_expiring_soon() -> None:
    report = build_report(
        [_result("a", "ok"), _result("b", "expiring_soon", days=15.0)]
    )
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_critical() -> None:
    report = build_report(
        [_result("a", "ok"), _result("b", "critical", days=3.0)]
    )
    assert report.alert_color == RED
    assert report.should_alert is True


def test_build_report_red_when_error() -> None:
    """Error de connexion compte comme critique (cert unverifiable)."""
    err = SslCheckResult(
        name="a",
        host="a.test",
        port=443,
        expires_at=None,
        days_remaining=None,
        status="error",
        error="ConnectionRefusedError",
    )
    report = build_report([err])
    assert report.alert_color == RED
