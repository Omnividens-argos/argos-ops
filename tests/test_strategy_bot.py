"""Tests unitaires de :mod:`argos_ops.agents.strategy_bot` (P22.E)."""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.agents.strategy_bot import aggregate, render_digest
from argos_ops.crm.models import AgentRun


def _run(name: str, status: str) -> AgentRun:
    return AgentRun(
        agent_name=name,
        status=status,
        started_at=datetime.now(UTC),
    )


# =============================================================================
# aggregate
# =============================================================================
def test_aggregate_counts_success_fail_skip() -> None:
    runs = [
        _run("A", "success"),
        _run("A", "success"),
        _run("A", "failed"),
        _run("A", "skipped_disabled"),
        _run("B", "success"),
    ]
    metrics = aggregate(runs)
    by_name = {m.agent_name: m for m in metrics}
    assert by_name["A"].total_runs == 4
    assert by_name["A"].success_runs == 2
    assert by_name["A"].failed_runs == 1
    assert by_name["A"].skipped_runs == 1
    assert abs(by_name["A"].success_rate - 0.5) < 1e-9
    assert by_name["B"].total_runs == 1


def test_aggregate_sorts_by_volume_desc() -> None:
    runs = [_run("B", "success"), _run("A", "success"), _run("A", "success")]
    metrics = aggregate(runs)
    assert metrics[0].agent_name == "A"
    assert metrics[1].agent_name == "B"


def test_aggregate_empty() -> None:
    assert aggregate([]) == []


def test_aggregate_killed_counted_as_failed() -> None:
    runs = [_run("A", "killed_by_breaker"), _run("A", "success")]
    by_name = {m.agent_name: m for m in aggregate(runs)}
    assert by_name["A"].failed_runs == 1
    assert by_name["A"].success_runs == 1


# =============================================================================
# render_digest
# =============================================================================
def test_render_digest_includes_header_and_table() -> None:
    runs = [_run("A", "success"), _run("A", "failed")]
    metrics = aggregate(runs)
    body = render_digest(
        metrics,
        iso_year=2026,
        iso_week=21,
        window_start=datetime(2026, 5, 16, tzinfo=UTC),
        window_end=datetime(2026, 5, 23, tzinfo=UTC),
    )
    assert "Digest semaine 2026-W21" in body
    assert "| A |" in body
    assert "Total" in body


def test_render_digest_handles_empty_metrics() -> None:
    body = render_digest(
        [],
        iso_year=2026,
        iso_week=21,
        window_start=datetime(2026, 5, 16, tzinfo=UTC),
        window_end=datetime(2026, 5, 23, tzinfo=UTC),
    )
    assert "aucun run dans la fenêtre" in body
    assert "vérifier l'orchestrator" in body