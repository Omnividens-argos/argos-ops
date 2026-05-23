"""Tests :mod:`argos_ops.agents.adr_writer`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from argos_ops.agents.adr_writer import (
    ADRDraft,
    build_draft,
    find_existing_adr,
    next_adr_number,
    render_adr,
    write_adr,
)


def _draft(slug: str = "test-decision", title: str = "Test Decision") -> ADRDraft:
    return ADRDraft(
        slug=slug,
        title=title,
        status="proposed",
        context="Pourquoi cette décision est nécessaire.",
        decision="On choisit l'option A.",
        consequences="L'option B n'est plus possible.",
        decided_on=date(2026, 5, 23),
    )


# =============================================================================
# build_draft
# =============================================================================
def test_build_draft_normalizes_status() -> None:
    d = build_draft(
        title="X", context="c", decision="d", consequences="cs", status="accepted"
    )
    assert d.status == "accepted"


def test_build_draft_rejects_invalid_status() -> None:
    with pytest.raises(ValueError):
        build_draft(
            title="X", context="c", decision="d", consequences="cs", status="invalid"
        )


def test_build_draft_auto_slug_from_title() -> None:
    d = build_draft(title="Migrer vers PostgreSQL 16", context="c", decision="d", consequences="cs")
    assert d.slug == "migrer-vers-postgresql-16"


# =============================================================================
# numbering
# =============================================================================
def test_next_adr_number_starts_at_1_when_empty(tmp_path: Path) -> None:
    assert next_adr_number(tmp_path) == 1


def test_next_adr_number_increments_from_existing(tmp_path: Path) -> None:
    (tmp_path / "ADR-0003-foo.md").write_text("x", encoding="utf-8")
    (tmp_path / "ADR-0007-bar.md").write_text("x", encoding="utf-8")
    assert next_adr_number(tmp_path) == 8


def test_find_existing_adr_matches_slug(tmp_path: Path) -> None:
    target = tmp_path / "ADR-0002-known.md"
    target.write_text("x", encoding="utf-8")
    assert find_existing_adr(tmp_path, "known") == target
    assert find_existing_adr(tmp_path, "ghost") is None


# =============================================================================
# write_adr (idempotence)
# =============================================================================
def test_write_adr_creates_file(tmp_path: Path) -> None:
    target, number, created = write_adr(_draft(), adr_dir=tmp_path)
    assert created is True
    assert number == 1
    assert target.name == "ADR-0001-test-decision.md"
    text = target.read_text(encoding="utf-8")
    assert "Test Decision" in text
    assert "proposed" in text


def test_write_adr_updates_existing_with_same_slug(tmp_path: Path) -> None:
    write_adr(_draft(slug="re", title="Original"), adr_dir=tmp_path)
    updated_draft = ADRDraft(
        slug="re",
        title="Updated Title",
        status="accepted",
        context="c",
        decision="d",
        consequences="cs",
        decided_on=date(2026, 6, 1),
    )
    target, number, created = write_adr(updated_draft, adr_dir=tmp_path)
    assert created is False
    assert number == 1
    text = target.read_text(encoding="utf-8")
    assert "Updated Title" in text
    assert "accepted" in text


def test_write_adr_assigns_next_number_for_new_slug(tmp_path: Path) -> None:
    write_adr(_draft(slug="one"), adr_dir=tmp_path)
    _, number, _ = write_adr(_draft(slug="two", title="Other"), adr_dir=tmp_path)
    assert number == 2


# =============================================================================
# render_adr
# =============================================================================
def test_render_adr_contains_sections() -> None:
    md = render_adr(_draft(), number=42)
    assert "ADR-0042 — Test Decision" in md
    assert "## Contexte" in md
    assert "## Décision" in md
    assert "## Conséquences" in md
