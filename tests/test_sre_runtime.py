"""Tests du socle runtime du pôle SRE (archi v2, S8).

Couvre les couches partagées par tous les scripts : journal de runs, registre de
breakers, kill-switch, cadence cron, tableau de statut, et le wrapper
``run_sre_script``. Hermétique : ``poles_root`` = ``tmp_path`` (aucune DB, aucun
réseau).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles.sre import breakers, killswitch, runlog, schedule, status
from argos_ops.poles.sre.base import BaseSreScript, run_sre_script
from argos_ops.poles.sre.report import SreReport, worst
from argos_ops.poles.sre.runlog import RunLogEntry

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _sre_pole(root: Path, scripts: list[tuple[str, str]]) -> None:
    """Écrit un data/poles/sre/pole.yaml minimal (id, schedule) par script."""
    lines = ["id: sre", "name: SRE", "agent: null", "scripts:"]
    for sid, sched in scripts:
        lines.append(f"  - id: {sid}")
        lines.append(f"    description: {sid} desc")
        if sched:
            lines.append(f'    schedule: "{sched}"')
    lines += ["reads_cross_pole: []", "front_tools: [alert_card]"]
    (root / "sre").mkdir(parents=True, exist_ok=True)
    (root / "sre" / "pole.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# =============================================================================
# report
# =============================================================================
def test_worst_severity() -> None:
    assert worst() == "green"
    assert worst("green", "yellow") == "yellow"
    assert worst("yellow", "red", "green") == "red"
    assert SreReport("red", "x").should_alert is True
    assert SreReport("green", "x").should_alert is False


# =============================================================================
# runlog
# =============================================================================
def test_runlog_append_load_order(tmp_path: Path) -> None:
    runlog.append_run(
        RunLogEntry(NOW - timedelta(hours=2), "a", "success", "green", 10.0, "old"),
        poles_root=tmp_path,
    )
    runlog.append_run(RunLogEntry(NOW, "a", "success", "yellow", 20.0, "new"), poles_root=tmp_path)
    runs = runlog.load_runs(poles_root=tmp_path)
    assert [r.summary for r in runs] == ["new", "old"]  # récent → vieux
    assert runlog.latest_per_script(poles_root=tmp_path)["a"].summary == "new"


def test_runlog_percentiles() -> None:
    p50, p95 = runlog.percentiles([float(x) for x in range(10, 101, 10)])
    assert (p50, p95) == (50.0, 100.0)
    assert runlog.percentiles([]) == (None, None)


def test_runlog_script_percentiles_excludes_skipped(tmp_path: Path) -> None:
    runlog.append_run(RunLogEntry(NOW, "s", "success", "green", 100.0, "ok"), poles_root=tmp_path)
    runlog.append_run(RunLogEntry(NOW, "s", "skipped", "green", 0.0, "frozen"), poles_root=tmp_path)
    p50, p95, n = runlog.script_percentiles("s", poles_root=tmp_path)
    assert n == 1 and p50 == 100.0 and p95 == 100.0


def test_runlog_runs_today(tmp_path: Path) -> None:
    runlog.append_run(RunLogEntry(NOW, "s", "success", "green", 1.0, "a"), poles_root=tmp_path)
    runlog.append_run(
        RunLogEntry(NOW - timedelta(days=2), "s", "success", "green", 1.0, "b"),
        poles_root=tmp_path,
    )
    runlog.append_run(RunLogEntry(NOW, "s", "skipped", "green", 0.0, "c"), poles_root=tmp_path)
    assert runlog.runs_today("s", now=NOW, poles_root=tmp_path) == 1  # skipped + J-2 exclus


def test_runlog_skips_corrupt_line(tmp_path: Path) -> None:
    path = runlog.runlog_path(poles_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{bad json}\n{"at": "2026-06-18T12:00:00+00:00", "script": "s", '
        '"status": "success", "severity": "green", "duration_ms": 1, "summary": "ok"}\n',
        encoding="utf-8",
    )
    runs = runlog.load_runs(poles_root=tmp_path)
    assert len(runs) == 1 and runs[0].summary == "ok"


# =============================================================================
# breakers
# =============================================================================
def test_breaker_trip_latches_and_reset(tmp_path: Path) -> None:
    t0 = NOW
    breakers.trip("x", "raison", now=t0, poles_root=tmp_path)
    # Re-trip plus tard : tripped_at conservé (latch).
    again = breakers.trip("x", "autre", now=t0 + timedelta(hours=3), poles_root=tmp_path)
    assert again.tripped_at == t0
    assert breakers.is_tripped("x", poles_root=tmp_path) is True
    breakers.reset("x", poles_root=tmp_path)
    assert breakers.is_tripped("x", poles_root=tmp_path) is False


def test_breaker_retrip_after_reset_is_fresh(tmp_path: Path) -> None:
    """Après reset, un nouvel armement doit prendre un tripped_at FRAIS (pas l'ancien)."""
    breakers.trip("x", "1", now=NOW, poles_root=tmp_path)
    breakers.reset("x", poles_root=tmp_path)
    again = breakers.trip("x", "2", now=NOW + timedelta(hours=10), poles_root=tmp_path)
    assert again.tripped_at == NOW + timedelta(hours=10)  # pas le NOW initial ressuscité


def test_breaker_list_tripped_order(tmp_path: Path) -> None:
    breakers.trip("b", "r", now=NOW, poles_root=tmp_path)
    breakers.trip("a", "r", now=NOW - timedelta(hours=1), poles_root=tmp_path)
    names = [b.name for b in breakers.list_tripped(poles_root=tmp_path)]
    assert names == ["a", "b"]  # plus ancien armement d'abord


def test_breaker_malformed_yaml_safe(tmp_path: Path) -> None:
    path = breakers.breakers_path(poles_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("breakers: not-a-dict\n", encoding="utf-8")
    assert breakers.load_breakers(poles_root=tmp_path) == {}


# =============================================================================
# killswitch
# =============================================================================
def test_killswitch_global_and_script(tmp_path: Path) -> None:
    assert killswitch.load_killswitch(poles_root=tmp_path).frozen is False
    killswitch.set_script("uptime_monitor", True, poles_root=tmp_path)
    ks = killswitch.load_killswitch(poles_root=tmp_path)
    assert ks.is_frozen("uptime_monitor") is True
    assert ks.is_frozen("other") is False
    # Gel global → tout est gelé.
    killswitch.set_global(True, reason="maintenance", poles_root=tmp_path)
    assert killswitch.load_killswitch(poles_root=tmp_path).is_frozen("other") is True


def test_killswitch_unset_script_idempotent(tmp_path: Path) -> None:
    killswitch.set_script("s", True, poles_root=tmp_path)
    killswitch.set_script("s", False, poles_root=tmp_path)
    killswitch.set_script("s", False, poles_root=tmp_path)  # idempotent
    assert killswitch.load_killswitch(poles_root=tmp_path).frozen_scripts == ()


# =============================================================================
# schedule (cron)
# =============================================================================
def test_schedule_is_due() -> None:
    expr = "0 4 * * *"  # quotidien 04:00 UTC
    assert schedule.is_due(expr, last_run=None, now=NOW) is True  # jamais lancé
    # Lancé ce matin 04:00 → prochain tick demain → pas dû.
    assert schedule.is_due(expr, last_run=NOW.replace(hour=4), now=NOW) is False
    # Lancé hier 04:00 → le tick d'aujourd'hui est passé → dû.
    assert schedule.is_due(expr, last_run=NOW - timedelta(days=1), now=NOW) is True
    assert schedule.is_due("pas-un-cron", last_run=None, now=NOW) is False


def test_schedule_missed_ticks_and_next() -> None:
    expr = "0 4 * * *"
    assert schedule.missed_ticks(expr, last_run=NOW - timedelta(days=3), now=NOW) == 3
    nxt = schedule.next_run(expr, after=NOW)
    assert nxt is not None and nxt.hour == 4 and nxt.day == 19


def test_schedule_missed_ticks_capped() -> None:
    """Garde-fou anti-boucle : un cron toutes les minutes avec un last_run ancien
    (~43 200 ticks sur 30 j) est borné à _MAX_TICKS_SCAN, jamais de boucle infinie."""
    capped = schedule.missed_ticks("* * * * *", last_run=NOW - timedelta(days=30), now=NOW)
    assert capped == schedule._MAX_TICKS_SCAN


def test_fleet_schedule_due_first(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("a", "0 4 * * *"), ("b", "*/15 * * * *")])
    entries = schedule.fleet_schedule(
        last_runs={"sre/a": NOW - timedelta(days=2)}, now=NOW, poles_root=tmp_path
    )
    assert {e.script for e in entries} == {"a", "b"}
    assert entries[0].due is True  # 'a' jamais... 'a' en retard, dû en tête


# =============================================================================
# status + base wrapper
# =============================================================================
class _StubScript(BaseSreScript):
    name = "uptime_monitor"

    def __init__(self, report: SreReport, *, poles_root: Path) -> None:
        super().__init__(poles_root=poles_root)
        self._report = report

    async def check(self) -> SreReport:
        return self._report


class _BoomScript(BaseSreScript):
    name = "uptime_monitor"

    async def check(self) -> SreReport:
        raise RuntimeError("boom")


async def test_run_sre_script_writes_memory_and_runlog(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("uptime_monitor", "*/15 * * * *")])
    script = _StubScript(SreReport("yellow", "1/2 endpoints degraded"), poles_root=tmp_path)
    result = await run_sre_script(script, now=NOW)
    assert result.status == "success"
    runs = runlog.load_runs(poles_root=tmp_path)
    assert runs[0].severity == "yellow" and runs[0].status == "success"
    mem = await script.read_memory()
    assert mem and mem[0].kind == "uptime_monitor" and mem[0].important is False


async def test_run_sre_script_red_flags_important(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("uptime_monitor", "*/15 * * * *")])
    script = _StubScript(SreReport("red", "site down"), poles_root=tmp_path)
    await run_sre_script(script, now=NOW)
    mem = await script.read_memory()
    assert mem[0].important is True  # un constat rouge est protégé


async def test_run_sre_script_frozen_skips(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("uptime_monitor", "*/15 * * * *")])
    killswitch.set_script("uptime_monitor", True, poles_root=tmp_path)
    script = _StubScript(SreReport("red", "site down"), poles_root=tmp_path)
    result = await run_sre_script(script, now=NOW)
    assert result.status == "skipped"
    assert await script.read_memory() == []  # rien écrit
    assert runlog.load_runs(poles_root=tmp_path)[0].status == "skipped"


async def test_run_sre_script_check_failure(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("uptime_monitor", "*/15 * * * *")])
    result = await run_sre_script(_BoomScript(poles_root=tmp_path), now=NOW)
    assert result.status == "failed"
    entry = runlog.load_runs(poles_root=tmp_path)[0]
    assert entry.status == "failed" and entry.severity == "red"


def test_compute_status_health(tmp_path: Path) -> None:
    _sre_pole(
        tmp_path,
        [("uptime_monitor", "*/15 * * * *"), ("backup_verifier", "0 4 * * *")],
    )
    # uptime : dernier run rouge → health red.
    runlog.append_run(
        RunLogEntry(NOW, "uptime_monitor", "success", "red", 12.0, "down"), poles_root=tmp_path
    )
    # backup : pas de run + breaker armé → health red.
    breakers.trip("backup_verifier", "manuel", now=NOW, poles_root=tmp_path)
    rows = {r.script: r for r in status.compute_status(now=NOW, poles_root=tmp_path)}
    assert rows["uptime_monitor"].health == "red"
    assert rows["uptime_monitor"].last_summary == "down"
    assert rows["backup_verifier"].breaker_tripped is True
    assert rows["backup_verifier"].health == "red"
    assert status.fleet_health(list(rows.values())) == "red"


def test_compute_status_stale(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("backup_verifier", "0 4 * * *")])
    runlog.append_run(
        RunLogEntry(NOW - timedelta(days=3), "backup_verifier", "success", "green", 5.0, "ok"),
        poles_root=tmp_path,
    )
    row = status.compute_status(now=NOW, poles_root=tmp_path)[0]
    assert row.stale is True and row.health == "yellow"
