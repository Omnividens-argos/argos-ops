"""Tests unitaires de l'orchestrateur de flotte + journal de flotte (archi v2, S9).

Complète ``test_fleet_e2e.py`` (cycle complet) par les cas de décision fins et le
round-trip du journal. asyncio_mode = "auto" → pas de décorateur sur les async.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from argos_ops.poles import fleet_runlog
from argos_ops.poles.fleet import (
    DEFAULT_MAX_CONCURRENT,
    load_fleet_config,
    plan_fleet,
)
from argos_ops.poles.fleet_runlog import (
    FleetRun,
    append_fleet_run,
    latest_per_pole_script,
    load_fleet_runs,
    runs_today_for,
)

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)  # un jeudi


def _seed_pole(root: Path, pid: str, scripts: list[tuple[str, str | None]]) -> None:
    """Écrit un ``pole.yaml`` minimal pour un pôle ad hoc (script id, schedule)."""
    d = root / pid
    d.mkdir(parents=True, exist_ok=True)
    body: dict[str, object] = {
        "id": pid,
        "name": pid,
        "agent": None,
        "scripts": [
            ({"id": sid, "schedule": sched} if sched else {"id": sid}) for sid, sched in scripts
        ],
        "reads_cross_pole": [],
        "front_tools": [],
    }
    (d / "pole.yaml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


# =============================================================================
# Journal de flotte
# =============================================================================
async def test_fleet_runlog_round_trip(tmp_path: Path) -> None:
    append_fleet_run(
        FleetRun(at=NOW, pole="veille", script="trend_spotter", status="success", duration_ms=12.5),
        poles_root=tmp_path,
    )
    append_fleet_run(
        FleetRun(
            at=NOW - timedelta(hours=1),
            pole="vente",
            script="email_bot",
            status="failed",
            duration_ms=3.0,
            error="boom",
        ),
        poles_root=tmp_path,
    )
    runs = load_fleet_runs(poles_root=tmp_path)
    assert len(runs) == 2
    assert runs[0].pole == "veille"  # tri récent → ancien
    # filtres
    assert len(load_fleet_runs(pole="vente", poles_root=tmp_path)) == 1
    assert load_fleet_runs(script="email_bot", poles_root=tmp_path)[0].error == "boom"
    # vue (pole, script)
    latest = latest_per_pole_script(poles_root=tmp_path)
    assert set(latest) == {("veille", "trend_spotter"), ("vente", "email_bot")}


async def test_fleet_runlog_runs_today_excludes_skipped(tmp_path: Path) -> None:
    append_fleet_run(
        FleetRun(at=NOW, pole="pub", script="ad_bot", status="success", duration_ms=1.0),
        poles_root=tmp_path,
    )
    append_fleet_run(
        FleetRun(at=NOW, pole="pub", script="ad_bot", status="skipped", duration_ms=0.0),
        poles_root=tmp_path,
    )
    # hier ne compte pas pour « aujourd'hui »
    append_fleet_run(
        FleetRun(
            at=NOW - timedelta(days=1),
            pole="pub",
            script="ad_bot",
            status="success",
            duration_ms=1.0,
        ),
        poles_root=tmp_path,
    )
    assert runs_today_for("pub", "ad_bot", now=NOW, poles_root=tmp_path) == 1


def test_fleet_runlog_skips_unreadable_lines(tmp_path: Path) -> None:
    path = fleet_runlog.fleet_runlog_path(poles_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{ not json\n{"at": "2026-06-18T12:00:00+00:00", "pole": "sre", '
        '"script": "uptime_monitor", "status": "success", "duration_ms": 1}\n',
        encoding="utf-8",
    )
    runs = load_fleet_runs(poles_root=tmp_path)
    assert len(runs) == 1  # la ligne corrompue est sautée, pas fatale
    assert runs[0].script == "uptime_monitor"


# =============================================================================
# Config de flotte
# =============================================================================
def test_load_fleet_config_defaults_when_absent(tmp_path: Path) -> None:
    cfg = load_fleet_config(poles_root=tmp_path)
    assert cfg.max_concurrent == DEFAULT_MAX_CONCURRENT
    assert cfg.daily_limit("vente", "email_bot") is None


def test_load_fleet_config_parses_limits(tmp_path: Path) -> None:
    (tmp_path / "fleet.yaml").write_text(
        yaml.safe_dump({"max_concurrent": 5, "daily_limits": {"vente/email_bot": 96}}),
        encoding="utf-8",
    )
    cfg = load_fleet_config(poles_root=tmp_path)
    assert cfg.max_concurrent == 5
    assert cfg.daily_limit("vente", "email_bot") == 96
    assert cfg.daily_limit("vente", "absent") is None


def test_load_fleet_config_clamps_max_concurrent_to_one(tmp_path: Path) -> None:
    # 0 est une valeur explicite à clamper à 1 (jamais 0 worker).
    (tmp_path / "fleet.yaml").write_text(yaml.safe_dump({"max_concurrent": 0}), encoding="utf-8")
    assert load_fleet_config(poles_root=tmp_path).max_concurrent == 1
    # Une valeur illisible retombe sur le défaut.
    (tmp_path / "fleet.yaml").write_text(
        yaml.safe_dump({"max_concurrent": "oops"}), encoding="utf-8"
    )
    assert load_fleet_config(poles_root=tmp_path).max_concurrent == DEFAULT_MAX_CONCURRENT


# =============================================================================
# Décisions fines de l'orchestrateur
# =============================================================================
async def test_plan_marks_not_due_after_recent_run(tmp_path: Path) -> None:
    # competitor_watcher est hebdo (lundi) ; un run jeudi → pas dû avant lundi prochain.
    _seed_pole(tmp_path, "veille", [("competitor_watcher", "0 7 * * 1")])
    append_fleet_run(
        FleetRun(
            at=NOW - timedelta(hours=2),
            pole="veille",
            script="competitor_watcher",
            status="success",
            duration_ms=1.0,
        ),
        poles_root=tmp_path,
    )
    plan = await plan_fleet(poles_root=tmp_path, now=NOW, dry_run=True)
    verdicts = {(d.pole, d.script): d.verdict for d in plan.decisions}
    assert verdicts[("veille", "competitor_watcher")] == "skipped_not_due"


async def test_plan_marks_not_runnable_for_unregistered_script(tmp_path: Path) -> None:
    # Un script déclaré dans pole.yaml mais absent du registre → skipped_not_runnable.
    _seed_pole(tmp_path, "veille", [("ghost_script", "0 6 * * *")])
    plan = await plan_fleet(poles_root=tmp_path, now=NOW, dry_run=True)
    ghost = next(d for d in plan.decisions if d.script == "ghost_script")
    assert ghost.verdict == "skipped_not_runnable"
    assert ghost.runnable is False


# =============================================================================
# Vérification du câblage (registre)
# =============================================================================
def test_validate_registry_detects_duplicate_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deux classes au même ``name`` dans un pôle (que ``script_registry`` écraserait)."""
    from argos_ops.poles import registry as reg
    from argos_ops.poles.base import BaseScript, ScriptResult

    class _A(BaseScript):
        pole = "veille"
        name = "dup"

        async def run(self) -> ScriptResult:
            return ScriptResult(status="success")

    class _B(BaseScript):
        pole = "veille"
        name = "dup"

        async def run(self) -> ScriptResult:
            return ScriptResult(status="success")

    _seed_pole(tmp_path, "veille", [("dup", "0 6 * * *")])
    monkeypatch.setattr(reg, "POLE_SCRIPTS", {"veille": (_A, _B)})
    problems = reg.validate_registry(poles_root=tmp_path)
    assert any("dupliqué" in p for p in problems)
