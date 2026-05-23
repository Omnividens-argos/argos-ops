"""Tests unitaires des helpers de :mod:`argos_ops.agents._watcher_base`.

Couvre les helpers de formatage purs (``format_age``, ``format_duration``,
``format_rate``, ``color_title``) sans toucher à ``emit_alert_or_silence``
qui est de l'I/O (testé indirectement via les watchers).
"""

from __future__ import annotations

from argos_ops.agents._watcher_base import (
    color_title,
    format_age,
    format_duration,
    format_rate,
)


# =============================================================================
# format_age
# =============================================================================
def test_format_age_none_returns_jamais() -> None:
    assert format_age(None) == "jamais"


def test_format_age_under_one_hour_returns_minutes() -> None:
    assert format_age(0.5) == "30min"
    assert format_age(0.25) == "15min"


def test_format_age_between_1h_and_48h_returns_hours() -> None:
    assert format_age(1.5) == "1.5h"
    assert format_age(12.0) == "12.0h"
    assert format_age(47.9) == "47.9h"


def test_format_age_above_48h_returns_days() -> None:
    assert format_age(48.0) == "2.0j"
    assert format_age(72.0) == "3.0j"
    assert format_age(240.0) == "10.0j"


# =============================================================================
# format_duration
# =============================================================================
def test_format_duration_none_returns_na() -> None:
    assert format_duration(None) == "n/a"


def test_format_duration_under_one_second_returns_ms() -> None:
    assert format_duration(0.5) == "500ms"
    assert format_duration(0.001) == "1ms"


def test_format_duration_between_1s_and_60s_returns_seconds() -> None:
    assert format_duration(1.0) == "1.0s"
    assert format_duration(42.5) == "42.5s"
    assert format_duration(59.9) == "59.9s"


def test_format_duration_above_60s_returns_minutes() -> None:
    assert format_duration(60.0) == "1.0min"
    assert format_duration(120.0) == "2.0min"


# =============================================================================
# format_rate
# =============================================================================
def test_format_rate_none_returns_na() -> None:
    assert format_rate(None) == "n/a"


def test_format_rate_returns_percentage() -> None:
    assert format_rate(0.0) == "0.0%"
    assert format_rate(0.5) == "50.0%"
    assert format_rate(1.0) == "100.0%"
    assert format_rate(0.123) == "12.3%"


# =============================================================================
# color_title
# =============================================================================
def test_color_title_matches_red() -> None:
    assert color_title(0xFF0000, green=0x00FF00, yellow=0xFFFF00, red=0xFF0000) == "RED"


def test_color_title_matches_yellow() -> None:
    assert (
        color_title(0xFFFF00, green=0x00FF00, yellow=0xFFFF00, red=0xFF0000) == "YELLOW"
    )


def test_color_title_matches_green() -> None:
    assert color_title(0x00FF00, green=0x00FF00, yellow=0xFFFF00, red=0xFF0000) == "GREEN"


def test_color_title_unknown_color_returns_other() -> None:
    assert color_title(0x123456, green=0x00FF00, yellow=0xFFFF00, red=0xFF0000) == "OTHER"
