"""Tests des 4 sections du FleetWatchdog (archi v2, S8).

Les sections sont pures : on leur passe des ``RunLogEntry`` / ``ScriptStatus``
fabriqués + un ``now`` fixe. On vérifie l'agrégation (couleur = la plus grave).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argos_ops.poles.sre.runlog import RunLogEntry
from argos_ops.poles.sre.scripts import fleet_watchdog as fw
from argos_ops.poles.sre.status import ScriptStatus

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _entry(script: str, *, status: str, sev: str, dur: float, at: datetime, err: str | None = None):  # type: ignore[no-untyped-def]
    return RunLogEntry(
        at=at, script=script, status=status, severity=sev, duration_ms=dur, summary="s", error=err
    )  # type: ignore[arg-type]


def _status(script: str, health: str) -> ScriptStatus:
    return ScriptStatus(
        script=script,
        description="",
        schedule="*/15 * * * *",
        health=health,  # type: ignore[arg-type]
        last_status="success",
        last_severity="green",
        last_summary="x",
        last_run_at=NOW,
        age_hours=0.0,
        next_run_at=None,
        due=False,
        stale=False,
        frozen=False,
        breaker_tripped=False,
        p50_ms=None,
        p95_ms=None,
        n_runs=1,
    )


def test_health_section() -> None:
    rows = [_status("a", "green"), _status("b", "yellow"), _status("c", "red")]
    section = fw.health_section(rows)
    assert section.severity == "red"
    assert "1 sain" in section.summary


def test_perf_section_regression() -> None:
    # 5 runs lents anciens, 5 runs très lents récents → P95 xN >= 2.
    runs = [
        _entry("s", status="success", sev="green", dur=100.0, at=NOW - timedelta(hours=h))
        for h in range(10, 5, -1)
    ]
    runs += [
        _entry("s", status="success", sev="green", dur=400.0, at=NOW - timedelta(hours=h))
        for h in range(5, 0, -1)
    ]
    section = fw.perf_section(runs)
    assert section.severity == "red"


def test_perf_section_insufficient_samples() -> None:
    runs = [_entry("s", status="success", sev="green", dur=100.0, at=NOW)]
    assert fw.perf_section(runs).severity == "green"


def test_errors_section_clusters() -> None:
    runs = [
        _entry("a", status="failed", sev="red", dur=1.0, at=NOW, err="ConnectionError: x")
        for _ in range(11)
    ]
    section = fw.errors_section(runs, now=NOW)
    assert section.severity == "red"  # cluster >= 10
    assert fw.error_signature("ConnectionError: refused") == "ConnectionError"
    assert fw.error_signature(None) == "<unknown>"


def test_errors_section_old_excluded() -> None:
    runs = [
        _entry("a", status="failed", sev="red", dur=1.0, at=NOW - timedelta(hours=48), err="X: y")
        for _ in range(5)
    ]
    assert fw.errors_section(runs, now=NOW).severity == "green"  # hors fenêtre 24h


def test_anomaly_section_spike() -> None:
    # 10 échecs dans la dernière heure, ~0 en baseline → pic critique.
    runs = [
        _entry("a", status="failed", sev="red", dur=1.0, at=NOW - timedelta(minutes=10))
        for _ in range(10)
    ]
    assert fw.anomaly_section(runs, now=NOW).severity == "red"


def test_anomaly_section_below_floor() -> None:
    runs = [_entry("a", status="failed", sev="red", dur=1.0, at=NOW - timedelta(minutes=5))]
    assert fw.anomaly_section(runs, now=NOW).severity == "green"  # < seuil absolu (5)


def test_aggregate_worst_wins() -> None:
    sections = [
        fw.Section("santé", "green", "ok"),
        fw.Section("perf", "yellow", "warn"),
        fw.Section("erreurs", "red", "boom"),
        fw.Section("anomalie", "green", "ok"),
    ]
    report = fw.aggregate(sections)
    assert report.severity == "red"
    assert "erreurs red" in report.summary
