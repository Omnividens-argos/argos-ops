"""Tests unitaires de ``argos_ops.agents.feedback_aggregator`` (P22.G)."""

from __future__ import annotations

from datetime import date

from argos_ops.agents.feedback_aggregator import (
    FeedbackReport,
    aggregate,
    build_feedback_embed,
    render_digest,
)


def test_aggregate_clusters_by_topic() -> None:
    items = [
        {"source": "email", "customer_id": "acme", "topic": "Export PDF FR"},
        {"source": "support", "customer_id": "beta", "topic": "Export PDF FR"},
        {"source": "discord", "customer_id": "acme", "topic": "SSO Microsoft"},
    ]
    themes = aggregate(items)
    assert len(themes) == 2
    top = themes[0]
    assert top.topic == "Export PDF FR"
    assert top.count == 2
    assert "acme" in top.customers and "beta" in top.customers


def test_aggregate_ignores_missing_topic() -> None:
    items = [
        {"source": "email", "topic": ""},
        {"source": "email", "topic": "Bug rapports"},
    ]
    themes = aggregate(items)
    assert len(themes) == 1


def test_render_digest_uses_today() -> None:
    items = [{"source": "email", "topic": "X"}]
    themes = aggregate(items)
    report = FeedbackReport(items_total=1, themes=themes)
    md = render_digest(report, today=date(2026, 5, 23))
    assert "2026-05-23" in md
    assert "## 1. X" in md


def test_build_feedback_embed_green_when_no_themes() -> None:
    embed = build_feedback_embed(FeedbackReport())
    assert embed.color == 0x2ECC71


def test_build_feedback_embed_yellow_when_themes() -> None:
    items = [{"source": "email", "topic": "X"}, {"source": "support", "topic": "X"}]
    themes = aggregate(items)
    report = FeedbackReport(items_total=2, themes=themes)
    embed = build_feedback_embed(report)
    assert embed.color == 0xF1C40F
