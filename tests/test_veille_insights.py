"""Tests de la synthèse d'insights Veille (archi v2, S1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.veille.insights import (
    record_severity,
    routing_for,
    severity_rank,
    synthesize_insights,
)


def _rec(
    kind: str,
    body: str,
    *,
    important: bool = False,
    tags: tuple[str, ...] = (),
    minutes_ago: int = 0,
) -> MemoryRecord:
    return MemoryRecord(
        id=f"{kind}-{body}",
        pole="veille",
        script=f"{kind}_script",
        kind=kind,
        body=body,
        important=important,
        tags=tags,
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


def test_record_severity_levels() -> None:
    assert record_severity(_rec("cve", "x", tags=("critical",))) == "critical"
    assert record_severity(_rec("cve", "x", important=True)) == "warning"
    assert record_severity(_rec("trend", "x")) == "info"


def test_severity_rank_orders_correctly() -> None:
    assert severity_rank("critical") > severity_rank("warning") > severity_rank("info")
    assert severity_rank("unknown") == 0


def test_routing_maps_known_and_unknown_kinds() -> None:
    theme, poles = routing_for("breach")
    assert theme == "menace"
    assert poles == ("vente",)
    assert routing_for("competitor")[1] == ("marketing", "pub", "vente")
    assert routing_for("mystery") == ("autre", ())


def test_synthesize_groups_one_insight_per_kind() -> None:
    records = [
        _rec("trend", "A"),
        _rec("trend", "B"),
        _rec("competitor", "C"),
    ]
    insights = synthesize_insights(records)
    kinds = {i.kind for i in insights}
    assert kinds == {"trend", "competitor"}
    trend = next(i for i in insights if i.kind == "trend")
    assert trend.count == 2
    assert trend.suggested_poles == ("marketing", "pub")


def test_synthesize_sorts_critical_first() -> None:
    records = [
        _rec("trend", "info-level"),
        _rec("cve", "critical-cve", tags=("critical",)),
        _rec("press", "warning", important=True),
    ]
    insights = synthesize_insights(records)
    assert insights[0].kind == "cve"
    assert insights[0].severity == "critical"


def test_synthesize_empty_returns_empty() -> None:
    assert synthesize_insights([]) == []
