"""Tests unitaires de :mod:`argos_ops.agents.incident_logger` (P22.E)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from argos_ops.agents.incident_logger import scaffold_incident, slugify


# =============================================================================
# slugify
# =============================================================================
@pytest.mark.parametrize(
    "title,expected",
    [
        ("Fuite API key", "fuite-api-key"),
        ("DB DOWN — 2h", "db-down-2h"),
        ("  Espaces   trop  larges  ", "espaces-trop-larges"),
        ("", "untitled"),
        ("###", "untitled"),
    ],
)
def test_slugify(title: str, expected: str) -> None:
    assert slugify(title) == expected


def test_slugify_max_60_chars() -> None:
    long_title = "Lorem ipsum " * 20
    assert len(slugify(long_title)) <= 60


# =============================================================================
# scaffold_incident
# =============================================================================
def test_scaffold_creates_file(tmp_path: Path) -> None:
    result = scaffold_incident(
        title="Fuite token Discord",
        category="data_leak",
        severity="P1",
        incidents_dir=tmp_path,
        today=date(2026, 5, 23),
    )
    assert result.created is True
    assert result.path.exists()
    body = result.path.read_text(encoding="utf-8")
    assert "Fuite token Discord" in body
    assert "category: data_leak" in body
    assert "severity: P1" in body


def test_scaffold_idempotent(tmp_path: Path) -> None:
    first = scaffold_incident(
        title="Repeat",
        category="misconfig",
        severity="P2",
        incidents_dir=tmp_path,
        today=date(2026, 5, 23),
    )
    second = scaffold_incident(
        title="Repeat",
        category="misconfig",
        severity="P2",
        incidents_dir=tmp_path,
        today=date(2026, 5, 23),
    )
    assert first.created is True
    assert second.created is False
    assert first.path == second.path


def test_scaffold_rejects_invalid_category(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        scaffold_incident(
            title="x",
            category="invalid",  # type: ignore[arg-type]
            severity="P0",
            incidents_dir=tmp_path,
        )


def test_scaffold_rejects_invalid_severity(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        scaffold_incident(
            title="x",
            category="other",
            severity="P9",  # type: ignore[arg-type]
            incidents_dir=tmp_path,
        )
