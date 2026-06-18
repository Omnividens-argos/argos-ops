"""Tests unitaires de :mod:`argos_ops.agents.bloctel_guard` (P22.E)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.agents.bloctel_guard import (
    BloctelMatch,
    build_report,
    find_latest_list,
    list_age,
    load_lead_phones,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# find_latest_list
# =============================================================================
def test_find_latest_list_returns_most_recent(tmp_path: Path) -> None:
    (tmp_path / "bloctel_2026-04.txt").write_text("", encoding="utf-8")
    (tmp_path / "bloctel_2026-05.txt").write_text("", encoding="utf-8")
    latest = find_latest_list(tmp_path)
    assert latest is not None
    assert latest.name == "bloctel_2026-05.txt"


def test_find_latest_list_none_when_empty(tmp_path: Path) -> None:
    assert find_latest_list(tmp_path) is None


def test_find_latest_list_none_when_missing_dir(tmp_path: Path) -> None:
    assert find_latest_list(tmp_path / "nope") is None


# =============================================================================
# list_age
# =============================================================================
def test_list_age_correct(tmp_path: Path) -> None:
    f = tmp_path / "bloctel_2026-04.txt"
    f.write_text("", encoding="utf-8")
    # 1er mai → 30 jours depuis 1er avril
    assert list_age(f, today=date(2026, 5, 1)) == 30


def test_list_age_malformed(tmp_path: Path) -> None:
    f = tmp_path / "weird.txt"
    f.write_text("", encoding="utf-8")
    assert list_age(f, today=date(2026, 5, 1)) is None


# =============================================================================
# load_lead_phones
# =============================================================================
def test_load_lead_phones_csv(tmp_path: Path) -> None:
    csv = tmp_path / "leads.csv"
    csv.write_text(
        "email,phone,name\na@b.com,0612345678,Alice\nc@d.com,,Bob\n",
        encoding="utf-8",
    )
    out = load_lead_phones(csv)
    assert out == [("a@b.com", "0612345678")]


def test_load_lead_phones_no_phone_column(tmp_path: Path) -> None:
    csv = tmp_path / "leads.csv"
    csv.write_text("email,name\na@b.com,Alice\n", encoding="utf-8")
    assert load_lead_phones(csv) == []


def test_load_lead_phones_missing_file(tmp_path: Path) -> None:
    assert load_lead_phones(tmp_path / "nope.csv") == []


# =============================================================================
# build_report
# =============================================================================
def test_build_report_red_when_list_missing() -> None:
    report = build_report(
        list_path=None,
        list_age_days=None,
        matches=[],
        leads_checked=0,
    )
    assert report.alert_color == RED


def test_build_report_red_when_list_too_old(tmp_path: Path) -> None:
    report = build_report(
        list_path=tmp_path / "bloctel.txt",
        list_age_days=60,
        matches=[],
        leads_checked=5,
    )
    assert report.alert_color == RED


def test_build_report_yellow_with_matches(tmp_path: Path) -> None:
    report = build_report(
        list_path=tmp_path / "bloctel.txt",
        list_age_days=10,
        matches=[BloctelMatch(phone="+33612345678", lead_identifier="x@y.com")],
        leads_checked=3,
    )
    assert report.alert_color == YELLOW


def test_build_report_green_when_fresh_and_no_match(tmp_path: Path) -> None:
    report = build_report(
        list_path=tmp_path / "bloctel.txt",
        list_age_days=10,
        matches=[],
        leads_checked=3,
    )
    assert report.alert_color == GREEN
    assert report.should_alert is False
