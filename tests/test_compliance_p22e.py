"""Tests unitaires des extensions P22.E de :mod:`argos_ops.compliance`.

Couvre les nouveaux checks ajoutés pour les watchers Compliance :
- ``scan_pii_collectors`` : détection PII dans le code
- ``classify_ai_act_risk`` : normalisation tag AI Act
- ``normalize_phone_fr`` + ``is_phone_on_bloctel`` : Bloctel
- ``next_renewal_date`` + ``days_until`` : contrats
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from argos_ops.compliance import (
    classify_ai_act_risk,
    days_until,
    is_phone_on_bloctel,
    next_renewal_date,
    normalize_phone_fr,
    scan_pii_collectors,
)


# =============================================================================
# scan_pii_collectors
# =============================================================================
def test_scan_pii_detects_email(tmp_path: Path) -> None:
    f = tmp_path / "model.py"
    f.write_text("class User:\n    email = 'a@b.com'\n", encoding="utf-8")
    findings = scan_pii_collectors(f)
    assert len(findings) == 1
    assert findings[0].category == "email"
    assert findings[0].line_no == 2


def test_scan_pii_detects_phone(tmp_path: Path) -> None:
    f = tmp_path / "model.py"
    f.write_text("phone = '06 12'\n", encoding="utf-8")
    findings = scan_pii_collectors(f)
    assert findings and findings[0].category == "phone"


def test_scan_pii_skip_comments(tmp_path: Path) -> None:
    f = tmp_path / "model.py"
    f.write_text("# email = 'leak'\n", encoding="utf-8")
    assert scan_pii_collectors(f) == []


def test_scan_pii_missing_file(tmp_path: Path) -> None:
    assert scan_pii_collectors(tmp_path / "nope.py") == []


def test_scan_pii_not_python(tmp_path: Path) -> None:
    f = tmp_path / "config.yaml"
    f.write_text("email: a@b.com\n", encoding="utf-8")
    assert scan_pii_collectors(f) == []


# =============================================================================
# classify_ai_act_risk
# =============================================================================
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("minimal", "minimal"),
        ("limited", "limited"),
        ("high", "high"),
        ("prohibited", "prohibited"),
        ("MINIMAL", "minimal"),  # case-insensitive
        ("  high  ", "high"),
        (None, "unclassified"),
        ("invalid", "unclassified"),
        (42, "unclassified"),
    ],
)
def test_classify_ai_act_risk(raw: object, expected: str) -> None:
    assert classify_ai_act_risk(raw) == expected


# =============================================================================
# normalize_phone_fr
# =============================================================================
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("06 12 34 56 78", "+33612345678"),
        ("0612345678", "+33612345678"),
        ("+33 6 12 34 56 78", "+33612345678"),
        ("0033612345678", "+33612345678"),
        ("06.12.34.56.78", "+33612345678"),
        ("(06)-12-34-56-78", "+33612345678"),
    ],
)
def test_normalize_phone_fr_valid(raw: str, expected: str) -> None:
    assert normalize_phone_fr(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "not a phone",
        "1234",
        "+1 555 555 5555",  # pas FR
        "0012345678",  # ne commence pas par +33 ni 0X
        "",
    ],
)
def test_normalize_phone_fr_invalid(raw: str) -> None:
    assert normalize_phone_fr(raw) is None


# =============================================================================
# is_phone_on_bloctel
# =============================================================================
def test_is_phone_on_bloctel_match(tmp_path: Path) -> None:
    list_path = tmp_path / "bloctel.txt"
    list_path.write_text("+33612345678\n+33687654321\n", encoding="utf-8")
    assert is_phone_on_bloctel("0612345678", bloctel_list_path=list_path)


def test_is_phone_on_bloctel_no_match(tmp_path: Path) -> None:
    list_path = tmp_path / "bloctel.txt"
    list_path.write_text("+33687654321\n", encoding="utf-8")
    assert not is_phone_on_bloctel("0612345678", bloctel_list_path=list_path)


def test_is_phone_on_bloctel_missing_file(tmp_path: Path) -> None:
    assert not is_phone_on_bloctel("0612345678", bloctel_list_path=tmp_path / "nope.txt")


def test_is_phone_on_bloctel_normalizes_list_entries(tmp_path: Path) -> None:
    """Liste avec format non normalisé doit quand même matcher."""
    list_path = tmp_path / "bloctel.txt"
    list_path.write_text("06.12.34.56.78\n# comment ignored\n", encoding="utf-8")
    assert is_phone_on_bloctel("+33 6 12 34 56 78", bloctel_list_path=list_path)


# =============================================================================
# next_renewal_date
# =============================================================================
def test_next_renewal_date_future_first_renewal() -> None:
    start = date(2025, 1, 15)
    today = date(2025, 8, 1)  # avant le 1er renouvellement
    assert next_renewal_date(start=start, term_months=12, today=today) == date(2026, 1, 15)


def test_next_renewal_date_skip_past_renewals() -> None:
    start = date(2023, 1, 15)
    today = date(2026, 5, 23)
    # Renouvellements 2024-01-15, 2025-01-15, 2026-01-15 sont passés
    assert next_renewal_date(start=start, term_months=12, today=today) == date(2027, 1, 15)


def test_next_renewal_date_month_overflow() -> None:
    """Démarrage en novembre + 6 mois → mai année suivante."""
    start = date(2025, 11, 15)
    today = date(2026, 2, 1)
    assert next_renewal_date(start=start, term_months=6, today=today) == date(2026, 5, 15)


def test_next_renewal_date_day_31_to_short_month() -> None:
    """Bord du mois : 31 jan + 1 mois → 28 fév (pas crash)."""
    start = date(2025, 1, 31)
    today = date(2025, 2, 1)
    result = next_renewal_date(start=start, term_months=1, today=today)
    assert result == date(2025, 2, 28)


def test_next_renewal_date_invalid_term() -> None:
    with pytest.raises(ValueError):
        next_renewal_date(start=date(2025, 1, 1), term_months=0, today=date(2025, 2, 1))


# =============================================================================
# days_until
# =============================================================================
def test_days_until_future() -> None:
    assert days_until(date(2026, 6, 1), today=date(2026, 5, 23)) == 9


def test_days_until_past() -> None:
    assert days_until(date(2026, 5, 1), today=date(2026, 5, 23)) == -22


def test_days_until_same_day() -> None:
    assert days_until(date(2026, 5, 23), today=date(2026, 5, 23)) == 0
