"""Tests des modules domaine du pôle Direction (archi v2, S6) — hermétiques (tmp_path).

Tout est sous ``tmp_path`` : la mémoire cross-pôle est semée via
``argos_ops.poles.memory.write_memory`` et les snapshots fichiers via le helper
``_w`` — on ne touche JAMAIS le vrai ``data/poles/``. Miroir du style
``tests/test_finance_domain.py``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.direction import (
    board,
    bugs,
    changelog,
    decisions,
    digest,
    feedback,
    fleet,
    okr,
    release,
    roadmap,
    synthesis,
)
from argos_ops.poles.direction.decisions import DecisionDraft


def _w(root: Path, pole: str, rel: str, body: str) -> None:
    """Écrit un fichier sous ``root/<pole>/<rel>`` (analogue du _w finance)."""
    p = root / pole / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _pole_yaml(root: Path, pole: str, name: str) -> None:
    """Crée un ``pole.yaml`` minimal pour que ``list_poles`` voie le pôle."""
    _w(root, pole, "pole.yaml", f"id: {pole}\nname: {name}\n")


# =============================================================================
# fleet — build_fleet_snapshot + fact_severity
# =============================================================================
async def _seed_fleet(root: Path) -> None:
    """Sème 3 pôles : un critique, un warning, un sain — + le pôle direction."""
    _pole_yaml(root, "vente", "Vente")
    _pole_yaml(root, "finance", "Finance")
    _pole_yaml(root, "veille", "Veille")
    _pole_yaml(root, "direction", "Direction")

    # Vente : un fait critique (tag critical) → pôle rouge.
    await memory.write_memory(
        "vente",
        "bloctel_guard",
        "Gel Bloctel : 2 numéros en liste d'opposition, envoi gelé.",
        kind="bloctel",
        tags=("bloctel", "critical", "frozen"),
        important=True,
        created_at=datetime(2026, 6, 18, 9, 0, tzinfo=UTC),
        poles_root=root,
    )
    # Finance : un fait warning (tag urgent) → pôle jaune.
    await memory.write_memory(
        "finance",
        "contract_deadline",
        "Contrat OVH à renouveler dans 15 jours (deadline 2026-07-03).",
        kind="contract",
        tags=("contract", "urgent"),
        created_at=datetime(2026, 6, 18, 8, 0, tzinfo=UTC),
        poles_root=root,
    )
    # Veille : un fait info pur → pôle vert (sain).
    await memory.write_memory(
        "veille",
        "trend_spotter",
        "Top sujet cyber de la semaine : ransomware-as-a-service en hausse.",
        kind="trend",
        tags=("trend",),
        created_at=datetime(2026, 6, 18, 7, 0, tzinfo=UTC),
        poles_root=root,
    )


async def test_fleet_snapshot_health_bands_and_worst(tmp_path: Path) -> None:
    await _seed_fleet(tmp_path)
    snap = await fleet.build_fleet_snapshot(
        poles_root=tmp_path, now=datetime(2026, 6, 18, 12, tzinfo=UTC)
    )
    # Direction exclue par défaut → 3 pôles supervisés.
    assert {p.pole for p in snap.poles} == {"vente", "finance", "veille"}
    assert snap.by_id("direction") is None

    vente = snap.by_id("vente")
    finance = snap.by_id("finance")
    veille = snap.by_id("veille")
    assert vente is not None and vente.health == "critical"
    assert finance is not None and finance.health == "warning"
    assert veille is not None and veille.health == "healthy"

    assert snap.worst_health == "critical"
    assert snap.poles_red == 1
    assert snap.poles_yellow == 1
    assert snap.poles_active == 3
    assert snap.total_critical == 1
    assert [p.name for p in snap.red_poles] == ["Vente"]
    # Tri : critique d'abord.
    assert snap.poles[0].pole == "vente"


async def test_fleet_snapshot_includes_direction_when_asked(tmp_path: Path) -> None:
    await _seed_fleet(tmp_path)
    snap = await fleet.build_fleet_snapshot(poles_root=tmp_path, include_direction=True)
    assert snap.by_id("direction") is not None  # idle (pas de mémoire propre)
    assert snap.by_id("direction").health == "idle"


def test_fact_severity_critical_warning_info() -> None:
    crit = memory.MemoryRecord(
        id="a",
        pole="vente",
        script="s",
        kind="bloctel",
        body="x",
        tags=("critical",),
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    warn = memory.MemoryRecord(
        id="b",
        pole="finance",
        script="s",
        kind="contract",
        body="x",
        tags=("urgent",),
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    info = memory.MemoryRecord(
        id="c",
        pole="veille",
        script="s",
        kind="trend",
        body="x",
        tags=("trend",),
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    important_no_marker = memory.MemoryRecord(
        id="d",
        pole="veille",
        script="s",
        kind="note",
        body="x",
        important=True,
        tags=(),
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    assert fleet.fact_severity(crit) == "critical"
    assert fleet.fact_severity(warn) == "warning"
    assert fleet.fact_severity(info) == "info"
    assert fleet.fact_severity(important_no_marker) == "warning"


# =============================================================================
# release — evaluate + gate (gel publication)
# =============================================================================
def test_release_evaluate_blocks_on_p0() -> None:
    empty = fleet.FleetSnapshot(
        generated_at=datetime(2026, 6, 18, tzinfo=UTC),
        poles=(),
        total_facts=0,
        total_important=0,
        total_critical=0,
        poles_red=0,
        poles_yellow=0,
        poles_active=0,
    )
    gate = release.evaluate(empty, open_p0=2)
    assert gate.blocking is True and gate.open_p0 == 2
    assert "P0" in gate.reason


def test_release_evaluate_blocks_on_red_pole() -> None:
    red = fleet.PoleHealth(
        pole="vente",
        name="Vente",
        n_facts=1,
        n_important=1,
        n_critical=1,
        n_warning=0,
        last_activity=datetime(2026, 6, 18, tzinfo=UTC),
        health="critical",
        headline="gel bloctel",
        scripts=("bloctel_guard",),
    )
    snap = fleet.FleetSnapshot(
        generated_at=datetime(2026, 6, 18, tzinfo=UTC),
        poles=(red,),
        total_facts=1,
        total_important=1,
        total_critical=1,
        poles_red=1,
        poles_yellow=0,
        poles_active=1,
    )
    gate = release.evaluate(snap, open_p0=0)
    assert gate.blocking is True and gate.red_poles == ("Vente",)
    assert "Vente" in gate.reason


def test_release_evaluate_open_when_clean() -> None:
    empty = fleet.FleetSnapshot(
        generated_at=datetime(2026, 6, 18, tzinfo=UTC),
        poles=(),
        total_facts=0,
        total_important=0,
        total_critical=0,
        poles_red=0,
        poles_yellow=0,
        poles_active=0,
    )
    gate = release.evaluate(empty, open_p0=0)
    assert gate.blocking is False and gate.reason == ""


async def test_release_gate_blocks_with_real_snapshot_and_p0(tmp_path: Path) -> None:
    await _seed_fleet(tmp_path)  # vente critique
    _w(
        tmp_path,
        "direction",
        "bugs/issues.yaml",
        'issues:\n  - number: 1\n    title: "Vulnérabilité XSS sur le rapport"\n'
        '    body: "XSS stocké sur le rapport partagé."\n    labels: ["security"]\n',
    )
    gate = await release.gate(poles_root=tmp_path)
    assert gate.blocking is True
    assert gate.open_p0 == 1  # XSS → P0
    assert "Vente" in gate.reason
    assert await release.release_blocking(poles_root=tmp_path) is True


# =============================================================================
# okr — load_current + set_actual (trimestre courant calculé via date.today)
# =============================================================================
_OKR_BODY = (
    "quarter: {q}\n"
    "year: {year}\n"
    "quarter_num: {n}\n"
    "objectives:\n"
    "  - title: Atteindre 10 000 EUR de MRR\n"
    "    key_results:\n"
    "      - name: MRR fin de trimestre\n"
    "        target: 10000\n"
    "        actual: 4500\n"
    "        unit: EUR\n"
    "      - name: Nouveaux clients\n"
    "        target: 8\n"
    "        actual: 3\n"
    "        unit: clients\n"
)


def _seed_current_okr(root: Path, *, today: date) -> Path:
    """Écrit l'OKR du trimestre courant au chemin que ``okr.current_okr_path`` calcule."""
    n = (today.month - 1) // 3 + 1
    path = okr.current_okr_path(poles_root=root, today=today)
    assert path.name == f"{today.year}-Q{n}.yaml"
    _w(
        root,
        "direction",
        f"okr/{path.name}",
        _OKR_BODY.format(q=f"{today.year}-Q{n}", year=today.year, n=n),
    )
    return path


def test_okr_load_current_statuses(tmp_path: Path) -> None:
    today = date.today()
    _seed_current_okr(tmp_path, today=today)
    report = okr.load_current(poles_root=tmp_path, today=today)
    assert len(report.key_results) == 2
    # Statuts dérivés du prorata — tous parmi l'ensemble connu.
    assert all(
        k.status in {"on_track", "at_risk", "off_track", "completed"} for k in report.key_results
    )


def test_okr_set_actual_updates_and_returns_report(tmp_path: Path) -> None:
    today = date.today()
    _seed_current_okr(tmp_path, today=today)
    updated = okr.set_actual(
        "Atteindre 10 000 EUR de MRR",
        "MRR fin de trimestre",
        9999.0,
        poles_root=tmp_path,
        today=today,
    )
    assert updated is not None
    kr = next(k for k in updated.key_results if k.name == "MRR fin de trimestre")
    assert kr.actual == 9999.0
    # La mutation est persistée : un rechargement reflète la nouvelle valeur.
    reloaded = okr.load_current(poles_root=tmp_path, today=today)
    kr2 = next(k for k in reloaded.key_results if k.name == "MRR fin de trimestre")
    assert kr2.actual == 9999.0


def test_okr_set_actual_none_when_kr_missing(tmp_path: Path) -> None:
    today = date.today()
    _seed_current_okr(tmp_path, today=today)
    assert (
        okr.set_actual(
            "Atteindre 10 000 EUR de MRR", "KR fantôme", 1.0, poles_root=tmp_path, today=today
        )
        is None
    )
    assert (
        okr.set_actual(
            "Objectif fantôme", "MRR fin de trimestre", 1.0, poles_root=tmp_path, today=today
        )
        is None
    )


# =============================================================================
# decisions — load_decisions + log_decision (idempotent par titre)
# =============================================================================
def test_decisions_log_and_load_idempotent(tmp_path: Path) -> None:
    draft = DecisionDraft(
        title="Direction = pôle transversal",
        partie="S6",
        decision="La Direction lit toute la flotte et gèle la publication.",
        pourquoi="Garde-fou Python homogène avec les autres pôles.",
    )
    res1 = decisions.log_decision(draft, poles_root=tmp_path, today=date(2026, 6, 18))
    assert res1.appended is True and res1.decision_id == "D-001"

    entries = decisions.load_decisions(poles_root=tmp_path)
    assert len(entries) == 1
    assert entries[0].title == "Direction = pôle transversal"
    assert entries[0].decision_date == "2026-06-18"
    assert entries[0].partie == "S6"

    # Ré-append du même titre = no-op (idempotent), aucune entrée dupliquée.
    res2 = decisions.log_decision(draft, poles_root=tmp_path, today=date(2026, 6, 19))
    assert res2.appended is False
    assert len(decisions.load_decisions(poles_root=tmp_path)) == 1


# =============================================================================
# changelog — build_changelog
# =============================================================================
_COMMITS = (
    "from_ref: v0.5.0\n"
    "to_ref: HEAD\n"
    "commits:\n"
    '  - sha: 836ef6e\n    subject: "feat(finance): pôle Finance complet"\n'
    '  - sha: aa11bb2\n    subject: "fix(vente): gel Bloctel mal levé"\n'
    '  - sha: ee55ff6\n    subject: "perf(veille): cache snapshots concurrents"\n'
    '  - sha: 11aa22b\n    subject: "docs: plan de session S0-S9"\n'
)


def test_changelog_build(tmp_path: Path) -> None:
    _w(tmp_path, "direction", "changelog/commits.yaml", _COMMITS)
    view = changelog.build_changelog(poles_root=tmp_path)
    assert view.n_commits == 4
    # 4 types distincts (feat / fix / perf / docs) → 4 sections.
    assert view.n_sections == 4
    assert view.period_label == "v0.5.0 → HEAD"
    assert "# Changelog" in view.markdown
    assert "pôle Finance complet" in view.markdown
    section_keys = {k for k, _ in view.section_counts}
    assert {"feat", "fix", "perf", "docs"} == section_keys


def test_changelog_empty_when_absent(tmp_path: Path) -> None:
    _pole_yaml(tmp_path, "direction", "Direction")
    view = changelog.build_changelog(poles_root=tmp_path)
    assert view.n_commits == 0 and view.n_sections == 0


# =============================================================================
# feedback — build_report + recurring_themes
# =============================================================================
_FEEDBACK = (
    "items:\n"
    "  - source: email\n    customer_id: acme\n    topic: Export PDF en français\n"
    '    verbatim: "Export FR svp."\n'
    "  - source: support\n    customer_id: beta\n    topic: Export PDF en français\n"
    '    verbatim: "Rapport en anglais bloquant."\n'
    "  - source: discord\n    customer_id: delta\n    topic: Intégration Slack\n"
    '    verbatim: "Webhook Slack natif."\n'
)


def test_feedback_report_and_recurring(tmp_path: Path) -> None:
    _w(tmp_path, "direction", "feedback/items.yaml", _FEEDBACK)
    report = feedback.build_report(poles_root=tmp_path)
    assert report.items_total == 3
    assert len(report.themes) == 2
    recurring = feedback.recurring_themes(poles_root=tmp_path)
    # Seul « Export PDF » a ≥ 2 mentions.
    assert len(recurring) == 1
    assert recurring[0].topic == "Export PDF en français"
    assert recurring[0].count == 2


# =============================================================================
# roadmap — build_roadmap
# =============================================================================
_ANNEXE = (
    "# Annexe D — Avancement de la flotte\n"
    "\n"
    "### 1. Direction & Pilotage\n"
    "\n"
    "- [x] ✅ **DirectionAgent** · Chief of Staff · Synthèse hebdo. *S6 livré.*\n"
    "- [x] ✅ **OKRTracker** · OKR · Suivi trimestriel. *S6 livré.*\n"
    "- [~] 🟡 **WeeklySynthesis** · Synthèse IA · Récit enrichi cerveau. *S6 partiel.*\n"
    "- [ ] ⬜ **SEOPlanner** · SEO · Planification SERP.\n"
    "\n"
    "### 2. Vente & Finance\n"
    "\n"
    "- [x] ✅ **VenteAgent** · Conversion · Pipeline et CRM. *S4 livré.*\n"
    "- [ ] ⬜ **ForecastPro** · Finance · Forecast multi-scénarios.\n"
)


def test_roadmap_build_counts(tmp_path: Path) -> None:
    _w(tmp_path, "direction", "roadmap/annexe_d.md", _ANNEXE)
    view = roadmap.build_roadmap(poles_root=tmp_path)
    assert view.entries_total == 6
    assert view.done == 3  # DirectionAgent, OKRTracker, VenteAgent
    assert view.partial == 1  # WeeklySynthesis
    assert view.roadmap == 2  # SEOPlanner, ForecastPro
    assert view.services == 2
    assert "Roadmap publique" in view.markdown


# =============================================================================
# bugs — triage + open_p0
# =============================================================================
_ISSUES = (
    "issues:\n"
    '  - number: 42\n    title: "Vulnérabilité XSS sur le rapport partagé"\n'
    '    body: "HTML non échappé issu du nom de domaine scanné."\n    labels: ["bug", "security"]\n'
    '  - number: 43\n    title: "Crash du scanner sur gros domaines"\n'
    '    body: "Timeout + OOM, régression depuis la v0.5."\n    labels: ["bug"]\n'
    '  - number: 44\n    title: "Améliorer le wording pricing"\n'
    '    body: "Confusion entre plans Pro et Business."\n    labels: ["enhancement"]\n'
)


def test_bugs_triage_and_open_p0(tmp_path: Path) -> None:
    _w(tmp_path, "direction", "bugs/issues.yaml", _ISSUES)
    stats = bugs.triage(poles_root=tmp_path)
    assert stats.issues_total == 3
    assert stats.p0 == 1  # XSS / vulnérabilité → P0
    assert stats.p1 == 1  # crash / régression → P1
    assert stats.p2 == 1  # wording → P2
    assert bugs.open_p0(poles_root=tmp_path) == 1


def test_bugs_no_issues(tmp_path: Path) -> None:
    _pole_yaml(tmp_path, "direction", "Direction")
    assert bugs.open_p0(poles_root=tmp_path) == 0


# =============================================================================
# board — build_metrics (a besoin d'un FleetSnapshot)
# =============================================================================
async def test_board_build_metrics_from_snapshot(tmp_path: Path) -> None:
    await _seed_fleet(tmp_path)
    snap = await fleet.build_fleet_snapshot(poles_root=tmp_path)
    _w(
        tmp_path,
        "direction",
        "board/metrics.yaml",
        "mrr_eur: 4500\nburn_eur: 1800\nrunway_months: 5.8\nnrr_pct: 104.0\nincidents_month: 1\n",
    )
    metrics = board.build_metrics(snap, poles_root=tmp_path, today=date(2026, 6, 18))
    assert metrics.mrr_eur == Decimal("4500")
    assert metrics.arr_eur == Decimal("54000")  # 12x MRR
    assert metrics.burn_eur == Decimal("1800")
    assert metrics.runway_months == 5.8
    assert metrics.nrr_pct == 104.0
    assert metrics.incidents_month == 1
    # Ops dérivés du snapshot.
    assert metrics.runs_month == snap.total_facts
    assert metrics.breakers_tripped == snap.poles_red  # 1 pôle rouge
    assert metrics.period == "2026-06"


# =============================================================================
# digest + synthesis (assemblage snapshot + okr + gate)
# =============================================================================
async def test_digest_and_synthesis_assembly(tmp_path: Path) -> None:
    await _seed_fleet(tmp_path)
    snap = await fleet.build_fleet_snapshot(
        poles_root=tmp_path, now=datetime(2026, 6, 18, 12, tzinfo=UTC)
    )

    # Digest weekly.
    dg = digest.build_digest(snap, scope="weekly", today=date(2026, 6, 18))
    assert dg.scope == "weekly"
    assert "Digest hebdomadaire" in dg.markdown
    assert "alerte critique" in dg.headline
    assert "Vente" in dg.markdown  # pôle rouge listé

    # OKR + gate pour la synthèse.
    today = date.today()
    _seed_current_okr(tmp_path, today=today)
    okr_report = okr.load_current(poles_root=tmp_path, today=today)
    gate = release.evaluate(snap, open_p0=1)  # gel forcé

    syn = synthesis.build_synthesis(snap, okr_report, gate)
    assert "alerte critique" in syn.headline  # 1 pôle rouge
    # Le récit mentionne l'état flotte + l'OKR du trimestre.
    assert "État flotte" in syn.narrative
    assert okr_report.quarter in syn.narrative
    # Le gel de publication remonte dans les risques.
    assert any("GELÉE" in r for r in syn.risks)
    # Vente (pôle rouge) apparaît dans les risques.
    assert any("Vente" in r for r in syn.risks)
