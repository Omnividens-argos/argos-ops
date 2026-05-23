"""Tests unitaires de :mod:`argos_ops.agents.board_reporter` (P22.E)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from argos_ops.agents.board_reporter import (
    BoardMetrics,
    count_incidents_in_month,
    load_burn,
    render_board_pack,
)


# =============================================================================
# load_burn
# =============================================================================
def test_load_burn_missing(tmp_path: Path) -> None:
    burn, runway = load_burn(tmp_path / "nope.yaml")
    assert burn is None
    assert runway is None


def test_load_burn_parses(tmp_path: Path) -> None:
    p = tmp_path / "burn.yaml"
    p.write_text("burn_eur: 4500\nrunway_months: 14.5\n", encoding="utf-8")
    burn, runway = load_burn(p)
    assert burn == Decimal("4500")
    assert runway == 14.5


def test_load_burn_partial(tmp_path: Path) -> None:
    p = tmp_path / "burn.yaml"
    p.write_text("burn_eur: 3200\n", encoding="utf-8")
    burn, runway = load_burn(p)
    assert burn == Decimal("3200")
    assert runway is None


# =============================================================================
# count_incidents_in_month
# =============================================================================
def test_count_incidents_in_month(tmp_path: Path) -> None:
    (tmp_path / "2026-05-23-x.md").write_text("", encoding="utf-8")
    (tmp_path / "2026-05-12-y.md").write_text("", encoding="utf-8")
    (tmp_path / "2026-04-30-z.md").write_text("", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("", encoding="utf-8")
    assert count_incidents_in_month(tmp_path, 2026, 5) == 2
    assert count_incidents_in_month(tmp_path, 2026, 4) == 1


def test_count_incidents_missing_dir(tmp_path: Path) -> None:
    assert count_incidents_in_month(tmp_path / "nope", 2026, 5) == 0


# =============================================================================
# render_board_pack
# =============================================================================
def test_render_board_pack_includes_mrr_and_runway() -> None:
    metrics = BoardMetrics(
        period="2026-05",
        mrr_eur=Decimal("4500.00"),
        arr_eur=Decimal("54000.00"),
        burn_eur=Decimal("3200.00"),
        runway_months=14.5,
        nrr_pct=None,
        runs_month=45,
        breakers_tripped=0,
        incidents_month=2,
    )
    body = render_board_pack(metrics)
    assert "Board Pack — 2026-05" in body
    assert "4500.00" in body
    assert "14.5 mois" in body
    assert "45" in body
    assert "Pandoc-ready" in body


def test_render_board_pack_handles_missing_burn() -> None:
    metrics = BoardMetrics(
        period="2026-05",
        mrr_eur=Decimal("0"),
        arr_eur=Decimal("0"),
        burn_eur=None,
        runway_months=None,
        nrr_pct=None,
        runs_month=0,
        breakers_tripped=0,
        incidents_month=0,
    )
    body = render_board_pack(metrics)
    assert "_non tracké_" in body
    assert "placeholder" in body
