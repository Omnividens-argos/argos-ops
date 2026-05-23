"""Tests unitaires de :mod:`argos_ops.agents.secret_rotator` (P22.C).

Couvre :
- ``_parse_date`` : date / datetime / str / invalid
- ``_classify`` : ok / due / overdue / invalid selon les seuils
- ``load_entries`` : fichier absent → ``[]``
- ``build_report`` : couleur RED/YELLOW/GREEN
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from argos_ops.agents.secret_rotator import (
    SecretEntry,
    _classify,
    _parse_date,
    build_report,
    load_entries,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _entry(name: str, status: str, *, age: int | None = 10) -> SecretEntry:
    return SecretEntry(
        name=name,
        last_rotated=date(2024, 1, 1),
        notes=None,
        age_days=age,
        status=status,  # type: ignore[arg-type]
    )


# =============================================================================
# _parse_date
# =============================================================================
def test_parse_date_accepts_date_object() -> None:
    assert _parse_date(date(2024, 5, 12)) == date(2024, 5, 12)


def test_parse_date_accepts_datetime_object() -> None:
    assert _parse_date(datetime(2024, 5, 12, 10, 0, tzinfo=UTC)) == date(2024, 5, 12)


def test_parse_date_accepts_iso_string() -> None:
    assert _parse_date("2024-05-12") == date(2024, 5, 12)


def test_parse_date_returns_none_on_invalid_string() -> None:
    assert _parse_date("not-a-date") is None


def test_parse_date_returns_none_on_other_types() -> None:
    assert _parse_date(12345) is None
    assert _parse_date(None) is None


# =============================================================================
# _classify
# =============================================================================
def test_classify_ok_under_max_age() -> None:
    assert _classify(30) == "ok"
    assert _classify(90) == "ok"


def test_classify_due_between_max_and_overdue() -> None:
    assert _classify(91) == "due"
    assert _classify(180) == "due"


def test_classify_overdue_above_overdue_days() -> None:
    assert _classify(181) == "overdue"
    assert _classify(365) == "overdue"


def test_classify_invalid_when_none() -> None:
    assert _classify(None) == "invalid"


# =============================================================================
# load_entries
# =============================================================================
def test_load_entries_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_entries(tmp_path / "nope.yaml") == []


def test_load_entries_parses_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "rot.yaml"
    path.write_text(
        "secrets:\n"
        "  - name: DISCORD_WEBHOOK\n"
        '    last_rotated: "2024-01-01"\n'
        "    notes: roté manuellement\n",
        encoding="utf-8",
    )
    entries = load_entries(path, today=date(2024, 6, 1))
    assert len(entries) == 1
    assert entries[0].name == "DISCORD_WEBHOOK"
    assert entries[0].age_days is not None
    assert entries[0].age_days > 90


# =============================================================================
# build_report
# =============================================================================
def test_build_report_green_when_all_ok() -> None:
    report = build_report([_entry("a", "ok"), _entry("b", "ok")])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_only_due() -> None:
    report = build_report([_entry("a", "ok"), _entry("b", "due", age=120)])
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_overdue() -> None:
    report = build_report([_entry("a", "overdue", age=200)])
    assert report.alert_color == RED


def test_build_report_red_when_invalid() -> None:
    report = build_report([_entry("a", "invalid", age=None)])
    assert report.alert_color == RED
