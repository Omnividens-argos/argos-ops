"""Tests de l'orchestrateur SRE (archi v2, S8).

Hermétique : ``poles_root`` = ``tmp_path`` avec un ``pole.yaml`` SRE minimal.
Couvre les 6 verdicts (launch + 5 skips) et l'exécution dry-run vs live.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.sre import breakers, killswitch, orchestrator
from argos_ops.poles.sre.runlog import RunLogEntry, append_run

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _sre_pole(root: Path, scripts: list[tuple[str, str | None]]) -> None:
    lines = ["id: sre", "name: SRE", "agent: null", "scripts:"]
    for sid, sched in scripts:
        lines.append(f"  - id: {sid}")
        if sched:
            lines.append(f'    schedule: "{sched}"')
    lines += ["reads_cross_pole: []", "front_tools: [alert_card]"]
    (root / "sre").mkdir(parents=True, exist_ok=True)
    (root / "sre" / "pole.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def test_plan_verdicts(tmp_path: Path) -> None:
    _sre_pole(
        tmp_path,
        [
            ("fleet_watchdog", "0 */6 * * *"),  # jamais lancé → launch
            ("uptime_monitor", "*/15 * * * *"),  # gelé → skipped_frozen
            ("backup_verifier", "0 4 * * *"),  # breaker armé → skipped_breaker
            ("doc_linter", None),  # pas de schedule → skipped_no_schedule
        ],
    )
    killswitch.set_script("uptime_monitor", True, poles_root=tmp_path)
    breakers.trip("backup_verifier", "manuel", now=NOW, poles_root=tmp_path)

    plan = await orchestrator.plan_execution(poles_root=tmp_path, now=NOW)
    verdicts = {d.script: d.verdict for d in plan.decisions}
    assert verdicts["fleet_watchdog"] == "launch"
    assert verdicts["uptime_monitor"] == "skipped_frozen"
    assert verdicts["backup_verifier"] == "skipped_breaker"
    assert verdicts["doc_linter"] == "skipped_no_schedule"
    assert plan.to_launch[0].script == "fleet_watchdog"


async def test_plan_not_due(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("backup_verifier", "0 4 * * *")])
    # Lancé ce matin 04:00 → prochain tick demain → pas dû.
    append_run(
        RunLogEntry(NOW.replace(hour=4), "backup_verifier", "success", "green", 5.0, "ok"),
        poles_root=tmp_path,
    )
    plan = await orchestrator.plan_execution(poles_root=tmp_path, now=NOW)
    assert plan.decisions[0].verdict == "skipped_not_due"


async def test_plan_daily_limit(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("uptime_monitor", "*/15 * * * *")])
    (tmp_path / "sre" / "orchestrator.yaml").write_text(
        "max_concurrent: 2\ndaily_limits:\n  uptime_monitor: 1\n", encoding="utf-8"
    )
    append_run(
        RunLogEntry(NOW - timedelta(hours=1), "uptime_monitor", "success", "green", 5.0, "ok"),
        poles_root=tmp_path,
    )
    plan = await orchestrator.plan_execution(poles_root=tmp_path, now=NOW)
    assert plan.decisions[0].verdict == "skipped_daily_limit"


async def test_execute_dry_run_launches_nothing(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("fleet_watchdog", "0 */6 * * *")])
    plan = await orchestrator.plan_execution(poles_root=tmp_path, now=NOW, dry_run=True)
    outcomes = await orchestrator.execute_plan(plan, poles_root=tmp_path)
    assert outcomes == []


async def test_execute_live_runs_via_runner(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("fleet_watchdog", "0 */6 * * *")])
    plan = await orchestrator.plan_execution(poles_root=tmp_path, now=NOW, dry_run=False)
    ran: list[str] = []

    async def fake_runner(script: BaseScript) -> ScriptResult:
        ran.append(script.name)
        return ScriptResult(status="success", summary="done")

    outcomes = await orchestrator.execute_plan(plan, poles_root=tmp_path, runner=fake_runner)
    assert ran == ["fleet_watchdog"]
    assert outcomes[0].status == "success"


async def test_config_max_concurrent_clamped(tmp_path: Path) -> None:
    _sre_pole(tmp_path, [("uptime_monitor", "*/15 * * * *")])
    (tmp_path / "sre" / "orchestrator.yaml").write_text("max_concurrent: 0\n", encoding="utf-8")
    cfg = orchestrator.load_orchestrator_config(poles_root=tmp_path)
    assert cfg.max_concurrent == 1  # clampé à >= 1
