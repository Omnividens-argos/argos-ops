"""Tests du garde-fou budget + breaker ``ad_spend_runaway`` (Pub, archi v2, S3).

Hermétique : ``budget.yaml`` sous ``tmp_path``. Couvre l'évaluation pure, le
latch du breaker, le reset, le réglage d'enveloppe et le simulateur.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import budget


def test_evaluate_runaway_pure() -> None:
    assert budget.evaluate_runaway(100, 160, multiplier=1.5) is True  # 160 > 150
    assert budget.evaluate_runaway(100, 140, multiplier=1.5) is False  # 140 < 150
    assert budget.evaluate_runaway(0, 999) is False  # budget non réglé ⇒ jamais


def test_runaway_threshold() -> None:
    assert budget.runaway_threshold(100, multiplier=1.5) == 150
    assert budget.runaway_threshold(0) == 0


def test_load_defaults_when_absent(tmp_path: Path) -> None:
    b = budget.load_budget(poles_root=tmp_path)
    assert b.daily_budget_eur == 0.0
    assert b.is_set is False
    assert b.utilization == 0.0
    assert b.over_threshold is False
    assert b.breaker_tripped is False


def test_load_budget_tolerates_corrupt_values(tmp_path: Path) -> None:
    # Valeur hand-corrompue : ne doit jamais crasher (chemin chaud agent/cockpit).
    d = tmp_path / "pub"
    d.mkdir(parents=True)
    (d / "budget.yaml").write_text("daily_budget_eur: abc\nwindow_days: oops\n", encoding="utf-8")
    b = budget.load_budget(poles_root=tmp_path)
    assert b.daily_budget_eur == 0.0  # retombe sur les défauts


def test_set_daily_budget_roundtrip(tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    b = budget.load_budget(poles_root=tmp_path)
    assert b.daily_budget_eur == 50.0
    assert b.runaway_threshold_eur == 75.0


def test_update_spend_arms_breaker_and_latches(tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)  # seuil = 75/j
    # Dépense 700 sur 7 j = 100/j > 75/j ⇒ arme le breaker.
    b = budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)
    assert b.spent_per_day_eur == 100.0
    assert b.breaker_tripped is True
    assert b.breaker_reason and "seuil" in b.breaker_reason
    assert b.breaker_tripped_at is not None

    # Latch : une mesure ultérieure sous le seuil NE désarme PAS.
    b2 = budget.update_spend({"google_search": 70.0}, window_days=7, poles_root=tmp_path)
    assert b2.spent_per_day_eur == 10.0
    assert b2.over_threshold is False  # photo live sous le seuil
    assert b2.breaker_tripped is True  # mais le latch reste armé


def test_update_spend_no_trip_under_threshold(tmp_path: Path) -> None:
    budget.set_daily_budget(300.0, poles_root=tmp_path)  # seuil = 450/j
    b = budget.update_spend(
        {"google_search": 1290.0, "linkedin_sponsored": 700.0}, window_days=7, poles_root=tmp_path
    )
    assert round(b.spent_per_day_eur, 2) == 284.29
    assert b.over_threshold is False
    assert b.breaker_tripped is False


def test_reset_breaker(tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"x": 700.0}, window_days=7, poles_root=tmp_path)
    assert budget.load_budget(poles_root=tmp_path).breaker_tripped is True
    b = budget.reset_breaker(poles_root=tmp_path)
    assert b.breaker_tripped is False
    assert b.breaker_reason is None
    assert b.breaker_tripped_at is None
    # La dépense mesurée est conservée après reset.
    assert b.spent_per_day_eur == 100.0


def test_simulate_budget() -> None:
    sim = budget.simulate_budget(
        {"google_search": 100.0, "linkedin_sponsored": 50.0},
        daily_budget_eur=200.0,
        cpa_by_platform={"google_search": 80.0, "linkedin_sponsored": 0.0},
        multiplier=1.5,
        days=7,
    )
    assert sim.total_daily_eur == 150.0
    assert sim.weekly_spend_eur == 1050.0
    assert round(sim.weekly_leads, 2) == 8.75  # 700/80 ; linkedin CPA 0 ⇒ 0 lead
    assert sim.exceeds_budget is False  # 150 < 200
    assert sim.would_trip is False  # 150 < 300
    assert len(sim.allocations) == 2


def test_simulate_budget_flags_runaway() -> None:
    sim = budget.simulate_budget(
        {"google_search": 500.0},
        daily_budget_eur=300.0,
        cpa_by_platform={"google_search": 60.0},
    )
    assert sim.exceeds_budget is True  # 500 > 300
    assert sim.would_trip is True  # 500 > 450
