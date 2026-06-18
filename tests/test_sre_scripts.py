"""Tests des 13 scripts du pôle SRE (archi v2, S8).

Hermétique : ``poles_root`` = ``tmp_path``, fetchers réseau (HTTP / SSL / DNS /
OSV / gh) injectés par des stubs — aucun réseau, aucune DB. On teste surtout la
logique pure (parse / classify / diff / build_report) + un ``check()`` par script.
"""

from __future__ import annotations

import os
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles.sre.base import run_sre_script
from argos_ops.poles.sre.scripts import (
    backup_verifier,
    bot_config_manager,
    ci_flake_tracker,
    dependency_auditor,
    diagram_generator,
    dns_guard,
    doc_linter,
    secret_rotator,
    ssl_expirer,
    uptime_monitor,
)
from argos_ops.poles.sre.scripts.adr_writer import AdrWriterScript
from argos_ops.poles.sre.scripts.adr_writer import generate_all as adr_generate
from argos_ops.poles.sre.scripts.kill_switch_operator import StaleBreaker, build_report, find_stale
from argos_ops.poles.sre.scripts.uptime_monitor import EndpointConfig, UptimeCheckResult

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _pole(root: Path, pid: str, *, agent: str | None, scripts: list[tuple[str, str]]) -> None:
    lines = [f"id: {pid}", f"name: {pid}"]
    lines.append("agent: null" if agent is None else f"agent:\n  name: {agent}")
    lines.append("scripts:")
    for sid, sched in scripts:
        lines.append(f"  - id: {sid}")
        if sched:
            lines.append(f'    schedule: "{sched}"')
    if not scripts:
        lines[-1] = "scripts: []"
    lines += ["reads_cross_pole: []", "front_tools: [alert_card]"]
    (root / pid).mkdir(parents=True, exist_ok=True)
    (root / pid / "pole.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# =============================================================================
# backup_verifier
# =============================================================================
def _backup(bdir: Path, age_hours: float) -> None:
    bdir.mkdir(exist_ok=True)
    f = bdir / "db.sql.gz"
    f.write_text("x")
    ts = (NOW - timedelta(hours=age_hours)).timestamp()
    os.utime(f, (ts, ts))


def test_backup_verifier_classifies(tmp_path: Path) -> None:
    bdir = tmp_path / "backups"
    _backup(bdir, 2)  # frais → ok/vert
    assert backup_verifier.scan_backups(bdir, now=NOW).status == "ok"
    assert (
        backup_verifier.build_report(backup_verifier.scan_backups(bdir, now=NOW)).severity
        == "green"
    )
    # Fenêtre intermédiaire 24h < age <= 72h → stale/jaune (branche jusque-là non couverte).
    _backup(bdir, 48)
    stale = backup_verifier.scan_backups(bdir, now=NOW)
    assert stale.status == "stale"
    assert backup_verifier.build_report(stale).severity == "yellow"
    # Au-delà de 72h → missing/rouge.
    _backup(bdir, 100)
    assert backup_verifier.scan_backups(bdir, now=NOW).status == "missing"


def test_backup_verifier_missing(tmp_path: Path) -> None:
    snap = backup_verifier.scan_backups(tmp_path / "nope", now=NOW)
    assert snap.status == "missing"
    assert backup_verifier.build_report(snap).severity == "red"


def test_backup_report_summary_stable_across_age() -> None:
    """INVARIANT idempotence : à état observé constant, le résumé (corps mémoire)
    ne doit PAS varier avec l'âge live — sinon chaque run empile un nouveau fait."""
    s1 = backup_verifier.BackupSnapshot("db.sql", 2.0, 1, "ok")
    s2 = backup_verifier.BackupSnapshot("db.sql", 20.0, 1, "ok")
    assert backup_verifier.build_report(s1).summary == backup_verifier.build_report(s2).summary


async def test_backup_run_is_idempotent(tmp_path: Path) -> None:
    """Deux runs à état backup constant ⇒ un seul fait mémoire (pas d'empilement)."""
    bdir = tmp_path / "backups"
    _backup(bdir, 2)
    script = backup_verifier.BackupVerifierScript(poles_root=tmp_path, backup_dir=bdir)
    await run_sre_script(script, now=NOW)
    await run_sre_script(script, now=NOW + timedelta(hours=6))
    assert len(await script.read_memory()) == 1


# =============================================================================
# secret_rotator
# =============================================================================
def test_secret_rotator_ages() -> None:
    today = NOW.date()
    entries = [
        {"name": "ovh", "last_rotated": (today - timedelta(days=10)).isoformat()},
        {"name": "stripe", "last_rotated": (today - timedelta(days=120)).isoformat()},
        {"name": "discord", "last_rotated": (today - timedelta(days=200)).isoformat()},
        {"name": "bad", "last_rotated": None},
    ]
    statuses = {s.name: s.status for s in secret_rotator.evaluate_secrets(entries, today=today)}
    assert statuses == {"ovh": "ok", "stripe": "due", "discord": "overdue", "bad": "invalid"}
    report = secret_rotator.build_report(secret_rotator.evaluate_secrets(entries, today=today))
    assert report.severity == "red"  # overdue + invalid


async def test_secret_rotator_check_empty(tmp_path: Path) -> None:
    report = await secret_rotator.SecretRotatorScript(poles_root=tmp_path).check()
    assert report.severity == "green"


# =============================================================================
# doc_linter
# =============================================================================
def test_doc_linter_detects_dead_links(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ok.md").write_text(
        "# Titre\n\nvoir [autre](other.md)\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "other.md").write_text("# Autre\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[mort](docs/ghost.md) et [ancre morte](docs/other.md#inexistant) et [ext](https://x.fr)\n",
        encoding="utf-8",
    )
    n_files, n_links, issues = doc_linter.scan_docs(tmp_path)
    kinds = sorted(i.kind for i in issues)
    assert kinds == ["missing_anchor", "missing_file"]
    assert doc_linter.build_report(n_files, n_links, issues).severity == "red"


def test_doc_linter_slugify() -> None:
    assert doc_linter.slugify_heading("D-019 : Abandon du Chatbot") == "d-019--abandon-du-chatbot"


# =============================================================================
# bot_config_manager
# =============================================================================
def test_config_drift_detects(tmp_path: Path) -> None:
    _pole(tmp_path, "veille", agent="VeilleAgent", scripts=[("trend", "0 4 * * *")])
    _pole(tmp_path, "sre", agent=None, scripts=[("uptime_monitor", "*/15 * * * *")])
    (tmp_path / "sre" / "config").mkdir(parents=True)
    (tmp_path / "sre" / "config" / "baseline.yaml").write_text(
        "poles:\n"
        "  veille:\n    agent: OldAgent\n    scripts: {trend: '0 4 * * *', gone: '0 5 * * *'}\n"
        "  sre:\n    agent: null\n    scripts: {uptime_monitor: '*/15 * * * *'}\n",
        encoding="utf-8",
    )
    baseline = bot_config_manager._baseline_snapshot(poles_root=tmp_path)
    live = bot_config_manager._live_snapshot(poles_root=tmp_path)
    assert baseline is not None
    drifts = bot_config_manager.diff_config(baseline, live)
    kinds = {d.kind for d in drifts}
    assert "agent_changed" in kinds and "script_removed" in kinds
    assert bot_config_manager.build_report(baseline, drifts).severity == "red"


async def test_config_drift_no_baseline(tmp_path: Path) -> None:
    _pole(tmp_path, "sre", agent=None, scripts=[("uptime_monitor", "*/15 * * * *")])
    report = await bot_config_manager.BotConfigManagerScript(poles_root=tmp_path).check()
    assert report.severity == "green"


# =============================================================================
# diagram_generator
# =============================================================================
async def test_diagram_generator(tmp_path: Path) -> None:
    specs = tmp_path / "sre" / "diagrams"
    specs.mkdir(parents=True)
    (specs / "flow.yaml").write_text(
        "title: Flux\ndirection: LR\nnodes:\n  - {id: a, label: A}\n  - {id: b, label: B}\n"
        "edges:\n  - {from: a, to: b}\n",
        encoding="utf-8",
    )
    (specs / "bad.yaml").write_text("title: Bad\nnodes: []\n", encoding="utf-8")
    out = tmp_path / "docs" / "diagrams"
    results = diagram_generator.generate_all(poles_root=tmp_path, output_dir=out)
    assert {r.slug: r.ok for r in results} == {"bad": False, "flow": True}
    assert (out / "flow.md").read_text(encoding="utf-8").startswith("# Flux")
    assert "flowchart LR" in (out / "flow.md").read_text(encoding="utf-8")
    assert diagram_generator.build_report(results).severity == "yellow"  # une spec invalide


# =============================================================================
# adr_writer
# =============================================================================
async def test_adr_writer_idempotent_numbering(tmp_path: Path) -> None:
    queue = tmp_path / "sre" / "adr" / "queue"
    queue.mkdir(parents=True)
    (queue / "local-first.yaml").write_text(
        "title: Local first\nstatus: accepted\ncontext: c\ndecision: d\n"
        "consequences: e\ndecided_on: 2026-06-18\n",
        encoding="utf-8",
    )
    adr_dir = tmp_path / "docs" / "adr"
    first = adr_generate(poles_root=tmp_path, adr_dir=adr_dir)
    assert first[0].number == 1 and first[0].created is True
    # Re-run : même slug → même numéro, pas un nouveau.
    second = adr_generate(poles_root=tmp_path, adr_dir=adr_dir)
    assert second[0].number == 1 and second[0].created is False
    assert list(adr_dir.glob("ADR-*.md")) == [adr_dir / "ADR-0001-local-first.md"]


async def test_adr_writer_empty(tmp_path: Path) -> None:
    report = await AdrWriterScript(poles_root=tmp_path, adr_dir=tmp_path / "adr").check()
    assert report.severity == "green"


# =============================================================================
# uptime_monitor
# =============================================================================
def test_uptime_build_report() -> None:
    results = [
        UptimeCheckResult("a", "https://a", "up", 200, 10.0, None),
        UptimeCheckResult("b", "https://b", "degraded", 404, 5.0, None),
        UptimeCheckResult("c", "https://c", "down", None, None, "timeout"),
    ]
    assert uptime_monitor.build_report(results).severity == "red"
    assert uptime_monitor.build_report(results[:2]).severity == "yellow"
    assert uptime_monitor.build_report([]).severity == "green"


async def test_uptime_check_with_stub(tmp_path: Path) -> None:
    (tmp_path / "sre" / "uptime").mkdir(parents=True)
    (tmp_path / "sre" / "uptime" / "endpoints.yaml").write_text(
        "endpoints:\n  - {name: site, url: 'https://omnividens.fr/'}\n", encoding="utf-8"
    )

    async def stub(ep: EndpointConfig) -> UptimeCheckResult:
        return UptimeCheckResult(ep.name, ep.url, "down", 500, 1.0, None)

    report = await uptime_monitor.UptimeMonitorScript(poles_root=tmp_path, probe=stub).check()
    assert report.severity == "red"


# =============================================================================
# ssl_expirer
# =============================================================================
async def test_ssl_expirer_classifies(tmp_path: Path) -> None:
    ep_ok = EndpointConfig("ok", "https://a.fr")
    ep_http = EndpointConfig("http", "http://b.fr")  # ignoré (pas HTTPS)

    async def fetch_soon(host: str, port: int) -> datetime:
        return NOW + timedelta(days=3)

    res = await ssl_expirer.check_endpoint(ep_ok, fetch_soon, now=NOW)
    assert res is not None and res.status == "critical"
    assert await ssl_expirer.check_endpoint(ep_http, fetch_soon, now=NOW) is None
    # Bornes exactes (CRITICAL_DAYS=7, WARN_DAYS=30).
    assert ssl_expirer.classify_days(40) == "ok"
    assert ssl_expirer.classify_days(30) == "ok"
    assert ssl_expirer.classify_days(15) == "expiring_soon"
    assert ssl_expirer.classify_days(7) == "expiring_soon"
    assert ssl_expirer.classify_days(6.9) == "critical"


async def test_ssl_expirer_error_path(tmp_path: Path) -> None:
    """Handshake en échec ou cert illisible → status 'error' → rouge (jamais masqué)."""
    ep = EndpointConfig("a", "https://a.fr")

    async def raise_ssl(host: str, port: int) -> datetime:
        raise ssl.SSLError("handshake")

    async def none_fetch(host: str, port: int) -> None:
        return None

    err = await ssl_expirer.check_endpoint(ep, raise_ssl, now=NOW)
    assert err is not None and err.status == "error"
    none_res = await ssl_expirer.check_endpoint(ep, none_fetch, now=NOW)
    assert (
        none_res is not None and none_res.status == "error" and none_res.error == "cert illisible"
    )
    assert ssl_expirer.build_report([err]).severity == "red"  # _STATUS_SEVERITY['error']='red'
    # Bout en bout : endpoint HTTPS + fetcher qui échoue → rouge.
    (tmp_path / "sre" / "uptime").mkdir(parents=True)
    (tmp_path / "sre" / "uptime" / "endpoints.yaml").write_text(
        "endpoints:\n  - {name: site, url: 'https://omnividens.fr/'}\n", encoding="utf-8"
    )
    report = await ssl_expirer.SslExpirerScript(poles_root=tmp_path, fetcher=raise_ssl).check()
    assert report.severity == "red"


# =============================================================================
# dns_guard
# =============================================================================
def test_dns_diff_critical() -> None:
    prev = {"omnividens.fr:A": ["1.1.1.1"], "omnividens.fr:MX": ["mx1"]}
    cur = {"omnividens.fr:A": ["2.2.2.2"], "omnividens.fr:MX": ["mx1"]}
    critical = frozenset({"omnividens.fr:A", "omnividens.fr:MX"})
    changes = dns_guard.diff_records(prev, cur, critical)
    assert len(changes) == 1 and changes[0].critical is True
    assert dns_guard.build_report(changes, n_keys=2, partial=False).severity == "red"


async def test_dns_guard_first_run_no_alert(tmp_path: Path) -> None:
    async def resolver(name: str, rtype: str) -> list[str]:
        return ["1.1.1.1"] if rtype == "A" else []

    report = await dns_guard.DnsGuardScript(poles_root=tmp_path, resolver=resolver).check()
    # Premier run : pas de snapshot précédent → aucun diff → vert.
    assert report.severity == "green"
    # Snapshot écrit → 2e run identique reste vert.
    report2 = await dns_guard.DnsGuardScript(poles_root=tmp_path, resolver=resolver).check()
    assert report2.severity == "green"


# =============================================================================
# dependency_auditor
# =============================================================================
def test_dependency_parse_and_report() -> None:
    deps = dependency_auditor.parse_requirements(
        "# comment\nhttpx==0.28.1\npydantic[email]==2.7.0 ; python_version>='3.12'\n-e .\n"
    )
    assert {d.name for d in deps} == {"httpx", "pydantic"}
    assert dependency_auditor.normalize_severity("MODERATE") == "MEDIUM"
    vulns = [dependency_auditor.Vulnerability("httpx", "0.28.1", "CVE-X", "HIGH", "boom")]
    assert dependency_auditor.build_report(2, vulns).severity == "red"
    assert dependency_auditor.build_report(2, []).severity == "green"


async def test_dependency_check_degrades_on_failure(tmp_path: Path) -> None:
    async def boom() -> list[dependency_auditor.Dependency]:
        raise RuntimeError("uv absent")

    script = dependency_auditor.DependencyAuditorScript(poles_root=tmp_path, deps_provider=boom)
    report = await script.check()
    assert report.severity == "yellow"  # dégrade, ne plante pas en rouge


# =============================================================================
# ci_flake_tracker
# =============================================================================
def test_ci_flake_detection_dual_threshold() -> None:
    """Sémantique ET (≥ 3 échecs ET ≥ 20%) + bornes + tri par taux décroissant."""
    jr = ci_flake_tracker.JobRun
    jobs = (
        [jr("below_occ", "failure")] * 2
        + [jr("below_occ", "success")] * 8  # 2/10 : <3 → pas flaky
        + [jr("below_rate", "failure")] * 3
        + [jr("below_rate", "success")] * 27  # 3/30=10% → non
        + [jr("boundary", "failure")] * 3
        + [jr("boundary", "success")] * 12  # 3/15=20% pile → flaky
        + [jr("always", "failure")] * 10  # 10/10=100% → flaky
    )
    flakes = ci_flake_tracker.detect_flakes(jobs)
    # ET strict : ni below_occ ni below_rate ; tri taux décroissant (always avant boundary).
    assert [f.job_name for f in flakes] == ["always", "boundary"]
    assert ci_flake_tracker.build_report(40, flakes).severity == "yellow"
    assert ci_flake_tracker.build_report(40, []).severity == "green"


async def test_ci_flake_degrades(tmp_path: Path) -> None:
    async def boom(repo: str, lookback: int) -> tuple[int, list[ci_flake_tracker.JobRun]]:
        raise RuntimeError("gh absent")

    report = await ci_flake_tracker.CiFlakeTrackerScript(poles_root=tmp_path, fetcher=boom).check()
    assert report.severity == "yellow"


# =============================================================================
# kill_switch_operator
# =============================================================================
def test_kill_switch_operator_stale() -> None:
    from argos_ops.poles.sre.breakers import Breaker

    tripped = [
        Breaker("recent", True, "r", NOW - timedelta(hours=1)),
        Breaker("stale", True, "r", NOW - timedelta(hours=6)),
        Breaker("old", True, "r", NOW - timedelta(hours=30)),
    ]
    stale = find_stale(tripped, now=NOW)
    assert {s.name for s in stale} == {"stale", "old"}  # > 4h
    assert build_report(stale).severity == "red"  # 'old' >= 24h
    assert build_report([StaleBreaker("x", "r", 5.0)]).severity == "yellow"
    assert build_report([]).severity == "green"


def test_kill_switch_detail_stable_within_band() -> None:
    """INVARIANT idempotence : à bande d'âge constante (≥ 4h), le détail (corps
    mémoire) ne varie pas avec l'âge live — sinon un fait par run toutes les 4h."""
    a = build_report([StaleBreaker("x", "r", 5.0)]).detail
    b = build_report([StaleBreaker("x", "r", 20.0)]).detail
    assert a == b
