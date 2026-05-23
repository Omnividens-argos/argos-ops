"""Tests unitaires de :mod:`argos_ops.agents.bounty_radar` (P22.D)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.bounty_radar import (
    DEFAULT_KEYWORDS,
    BountyProgram,
    _program_key,
    build_report,
    load_keywords,
    load_seen,
    save_seen,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def _prog(handle: str, name: str = "") -> BountyProgram:
    return BountyProgram(
        platform="YesWeHack",
        handle=handle,
        name=name or handle,
        url=f"https://yeswehack.com/programs/{handle}",
        matched_keywords=["saas"],
    )


def test_load_keywords_returns_defaults_when_missing(tmp_path: Path) -> None:
    assert load_keywords(tmp_path / "absent.yaml") == DEFAULT_KEYWORDS


def test_load_keywords_parses_yaml(tmp_path: Path) -> None:
    path = tmp_path / "filters.yaml"
    path.write_text("keywords: [foo, bar]\n", encoding="utf-8")
    kw = load_keywords(path)
    assert "foo" in kw
    assert "bar" in kw


def test_load_keywords_falls_back_to_defaults_on_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "filters.yaml"
    path.write_text("keywords: []\n", encoding="utf-8")
    assert load_keywords(path) == DEFAULT_KEYWORDS


def test_seen_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen({"HackerOne::shopify", "YesWeHack::acme"}, path=path)
    reloaded = load_seen(path=path)
    assert reloaded == {"HackerOne::shopify", "YesWeHack::acme"}


def test_program_key_uses_platform_and_handle() -> None:
    assert _program_key(_prog("acme")) == "YesWeHack::acme"


def test_build_report_green_when_no_new_programs() -> None:
    report = build_report([], total_scanned=20)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_new_programs() -> None:
    report = build_report([_prog("acme")], total_scanned=20)
    assert report.alert_color == YELLOW
    assert report.should_alert is True
