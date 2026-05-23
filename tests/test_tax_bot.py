"""Tests :mod:`argos_ops.agents.tax_bot` + helpers TVA / IS."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from argos_ops.agents.tax_bot import render_tax_markdown, write_tax_draft
from argos_ops.finance.tva import (
    IS_REDUCED_THRESHOLD,
    compute_ca3,
    estimate_is,
)


# =============================================================================
# compute_ca3
# =============================================================================
def test_compute_ca3_applies_20pct_normal_rate() -> None:
    report = compute_ca3(period_month="2026-05", ca_ht_eur=Decimal("1000.00"))
    assert report.tva_collected_eur == Decimal("200.00")
    assert report.tva_net_due_eur == Decimal("200.00")
    assert report.ca_ht_eur == Decimal("1000.00")


def test_compute_ca3_subtracts_deductible() -> None:
    report = compute_ca3(
        period_month="2026-05",
        ca_ht_eur=Decimal("1000.00"),
        tva_deductible_eur=Decimal("30.00"),
    )
    assert report.tva_net_due_eur == Decimal("170.00")


def test_compute_ca3_summary_string() -> None:
    report = compute_ca3(period_month="2026-05", ca_ht_eur=Decimal("500.00"))
    summary = report.summary()
    assert "ca_ht=500" in summary
    assert "tva_collected=100" in summary


# =============================================================================
# estimate_is
# =============================================================================
def test_estimate_is_uses_reduced_rate_under_threshold() -> None:
    fc = estimate_is(Decimal("20000.00"))
    assert fc.is_reduced_part_eur == Decimal("3000.00")  # 20000 x 15 %
    assert fc.is_normal_part_eur == Decimal("0.00")
    assert fc.is_total_eur == Decimal("3000.00")


def test_estimate_is_applies_two_brackets_above_threshold() -> None:
    profit = IS_REDUCED_THRESHOLD + Decimal("10000.00")  # 52 500
    fc = estimate_is(profit)
    # 42 500 x 15 % = 6 375
    assert fc.is_reduced_part_eur == Decimal("6375.00")
    # 10 000 x 25 % = 2 500
    assert fc.is_normal_part_eur == Decimal("2500.00")
    assert fc.is_total_eur == Decimal("8875.00")


def test_estimate_is_returns_zero_on_loss() -> None:
    fc = estimate_is(Decimal("-1000.00"))
    assert fc.is_total_eur == Decimal("0.00")


# =============================================================================
# render + write
# =============================================================================
def test_render_tax_markdown_includes_ca3_and_is() -> None:
    ca3 = compute_ca3(period_month="2026-05", ca_ht_eur=Decimal("1000.00"))
    is_fc = estimate_is(Decimal("20000.00"))
    md = render_tax_markdown(ca3, is_fc)
    assert "TVA CA3 — 2026-05" in md
    assert "200.00 €" in md  # TVA collectée
    assert "3000.00 €" in md  # IS estimé


def test_write_tax_draft_creates_file(tmp_path: Path) -> None:
    ca3 = compute_ca3(period_month="2026-05", ca_ht_eur=Decimal("100.00"))
    target = write_tax_draft(ca3, None, target_dir=tmp_path)
    assert target.exists()
    assert target.name == "ca3_2026-05.md"
    text = target.read_text(encoding="utf-8")
    assert "20.00 €" in text  # TVA collectée = 100 x 20%
