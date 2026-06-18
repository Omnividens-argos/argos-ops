"""Tests de l'API cockpit du pôle SRE (archi v2, S8).

Hermétique : app minimale (router SRE seul) + ``POLES_DIR`` du module patché vers
``tmp_path``. On seede un ``pole.yaml`` SRE + quelques runs/breakers, puis on
vérifie overview / runs / plan / run-now / breakers / kill-switch. Strict miroir
du style de ``tests/test_memoire_api.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import sre
from argos_ops.poles.sre import breakers, runlog
from argos_ops.poles.sre.runlog import RunLogEntry

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)

# Sous-ensemble de scripts réels pour un pole.yaml de test léger.
_SCRIPTS = [
    ("fleet_watchdog", "0 */6 * * *"),
    ("uptime_monitor", "*/15 * * * *"),
    ("backup_verifier", "0 4 * * *"),
    ("kill_switch_operator", "0 */4 * * *"),
]


def _seed(root: Path) -> None:
    lines = ["id: sre", "name: SRE & Meta-Ops", "agent: null", "scripts:"]
    for sid, sched in _SCRIPTS:
        lines += [f"  - id: {sid}", f"    description: {sid}", f'    schedule: "{sched}"']
    lines += ["reads_cross_pole: []", "front_tools: [alert_card]"]
    (root / "sre").mkdir(parents=True, exist_ok=True)
    (root / "sre" / "pole.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # uptime : dernier run rouge (récent).
    runlog.append_run(
        RunLogEntry(
            NOW - timedelta(minutes=5), "uptime_monitor", "success", "red", 12.0, "site down"
        ),
        poles_root=root,
    )
    # backup : run vert ancien.
    runlog.append_run(
        RunLogEntry(NOW - timedelta(hours=10), "backup_verifier", "success", "green", 5.0, "ok"),
        poles_root=root,
    )
    breakers.trip("ad_spend_runaway", "test", now=NOW - timedelta(hours=30), poles_root=root)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(sre, "POLES_DIR", tmp_path)
    _seed(tmp_path)
    app = FastAPI()
    app.include_router(sre.router)
    with TestClient(app) as c:
        yield c


def test_overview(client: TestClient) -> None:
    o = client.get("/api/poles/sre/overview").json()
    assert o["pole"] == "sre"
    assert o["health"] == "red"  # uptime rouge
    assert o["counts"]["scripts_total"] == 4
    assert o["counts"]["red"] >= 1
    assert o["counts"]["breakers_tripped"] == 1
    uptime = next(s for s in o["scripts"] if s["script"] == "uptime_monitor")
    assert uptime["health"] == "red" and uptime["last_summary"] == "site down"
    assert uptime["runnable"] is True
    # Planning cron + plan orchestrateur présents.
    assert any(e["script"] == "fleet_watchdog" for e in o["schedule"])
    assert o["plan"]["to_launch"] >= 1
    # Breaker armé visible.
    assert o["breakers"][0]["name"] == "ad_spend_runaway"


def test_runs_filter(client: TestClient) -> None:
    all_runs = client.get("/api/poles/sre/runs").json()
    assert len(all_runs) == 2
    only = client.get("/api/poles/sre/runs", params={"script": "uptime_monitor"}).json()
    assert len(only) == 1 and only[0]["severity"] == "red"


def test_plan_endpoint(client: TestClient) -> None:
    plan = client.get("/api/poles/sre/plan").json()
    assert plan["dry_run"] is True
    verdicts = {d["script"]: d["verdict"] for d in plan["decisions"]}
    # fleet_watchdog jamais lancé → launch.
    assert verdicts["fleet_watchdog"] == "launch"


def test_breaker_reset(client: TestClient) -> None:
    r = client.post("/api/poles/sre/breakers/ad_spend_runaway/reset")
    assert r.status_code == 200 and r.json()["tripped"] is False
    o = client.get("/api/poles/sre/overview").json()
    assert o["counts"]["breakers_tripped"] == 0


def test_breaker_trip(client: TestClient) -> None:
    r = client.post("/api/poles/sre/breakers/manual_test/trip", json={"reason": "essai"})
    assert r.status_code == 200 and r.json()["tripped"] is True
    assert r.json()["reason"] == "essai"


def test_killswitch_global_and_script(client: TestClient) -> None:
    g = client.post("/api/poles/sre/killswitch", json={"frozen": True, "reason": "maintenance"})
    assert g.status_code == 200 and g.json()["frozen"] is True
    s = client.post(
        "/api/poles/sre/killswitch/script", json={"script": "uptime_monitor", "frozen": True}
    )
    assert "uptime_monitor" in s.json()["frozen_scripts"]
    # Script inconnu → 404.
    assert (
        client.post(
            "/api/poles/sre/killswitch/script", json={"script": "nope", "frozen": True}
        ).status_code
        == 404
    )


def test_run_now(client: TestClient) -> None:
    # kill_switch_operator est hermétique (lit le registre breakers de tmp_path).
    r = client.post("/api/poles/sre/run/kill_switch_operator")
    assert r.status_code == 200 and r.json()["status"] == "success"
    # Un nouveau run apparaît dans le journal.
    runs = client.get("/api/poles/sre/runs", params={"script": "kill_switch_operator"}).json()
    assert len(runs) == 1
    # Script inconnu → 404.
    assert client.post("/api/poles/sre/run/nope").status_code == 404


def test_run_now_respects_killswitch(client: TestClient) -> None:
    client.post(
        "/api/poles/sre/killswitch/script", json={"script": "kill_switch_operator", "frozen": True}
    )
    r = client.post("/api/poles/sre/run/kill_switch_operator")
    assert r.json()["status"] == "skipped"  # gelé → run sauté
