"""Tests unitaires de :mod:`argos_ops.agents.log_anomaly` (P22.D).

Couvre la logique pure : classification, build_report, embed.
Pas d'I/O DB ici — la requête ``agent_runs`` est testée indirectement
via ``classify``/``build_report`` qui prennent les compteurs en entrée.
"""

from __future__ import annotations

from argos_ops.agents.log_anomaly import (
    SPIKE_ABSOLUTE_CRITICAL,
    SPIKE_ABSOLUTE_MIN,
    build_anomaly_embed,
    build_report,
    classify,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def test_classify_normal_under_absolute_min() -> None:
    # même si ratio infini (baseline 0), tant que <5 → silence
    assert classify(current_count=SPIKE_ABSOLUTE_MIN - 1, baseline_hourly=0.0) == "normal"


def test_classify_warn_when_ratio_3x() -> None:
    # 10 / 3 = 3.33 → warn (>= 3x)
    assert classify(current_count=10, baseline_hourly=3.0) == "spike_warn"


def test_classify_critical_when_ratio_5x() -> None:
    # 15 / 3 = 5.0 → critical
    assert classify(current_count=15, baseline_hourly=3.0) == "spike_critical"


def test_classify_critical_absolute_even_low_ratio() -> None:
    # 60 erreurs/heure, baseline 30/h → ratio 2x mais volume absolu > 50 → critical
    assert classify(current_count=60, baseline_hourly=30.0) == "spike_critical"


def test_classify_uses_floor_when_baseline_zero() -> None:
    # baseline 0 → floor 1.0 → 5/1 = 5x ratio → critical
    assert classify(current_count=5, baseline_hourly=0.0) == "spike_critical"


def test_build_report_green_when_normal() -> None:
    report = build_report(current_count=2, baseline_hourly=1.0, top_agents=[])
    assert report.alert_color == GREEN
    assert report.should_alert is False
    assert "2 erreurs" in report.summary


def test_build_report_yellow_when_warn() -> None:
    report = build_report(
        current_count=10, baseline_hourly=3.0, top_agents=[("FooBot", 7)]
    )
    assert report.alert_color == YELLOW
    assert report.should_alert is True
    assert "ratio 3.3x" in report.summary


def test_build_report_red_when_critical() -> None:
    report = build_report(
        current_count=60, baseline_hourly=10.0, top_agents=[("FooBot", 40)]
    )
    assert report.alert_color == RED
    assert report.should_alert is True


def test_build_report_caps_to_critical_on_absolute_threshold() -> None:
    # Edge: pile 50 erreurs/h, baseline 30/h → ratio 1.66x mais absolute >= 50 → red
    report = build_report(
        current_count=SPIKE_ABSOLUTE_CRITICAL, baseline_hourly=30.0, top_agents=[]
    )
    assert report.alert_color == RED


def test_embed_includes_top_agents_field() -> None:
    report = build_report(
        current_count=12, baseline_hourly=3.0, top_agents=[("FooBot", 8), ("BarBot", 4)]
    )
    embed = build_anomaly_embed(report)
    field_names = {f.name for f in embed.fields}
    assert "Top agents" in field_names
    assert any("FooBot" in f.value for f in embed.fields)


def test_embed_skips_top_agents_field_when_empty() -> None:
    report = build_report(current_count=12, baseline_hourly=3.0, top_agents=[])
    embed = build_anomaly_embed(report)
    field_names = {f.name for f in embed.fields}
    assert "Top agents" not in field_names
