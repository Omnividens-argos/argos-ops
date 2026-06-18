"""Tests d'intégration des scripts du pôle Direction (archi v2, S6) — run + mémoire.

Hermétique : tout est seedé sous ``tmp_path`` (snapshots ``data/poles/direction/…``
+ ``pole.yaml`` de quelques pôles + mémoire cross-pôle), et la mémoire de chaque
script est relue via :func:`argos_ops.poles.memory.read_memory`. Strict miroir du
style de ``tests/test_finance_scripts.py``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.direction import okr
from argos_ops.poles.direction.scripts import (
    DIRECTION_SCRIPTS,
    BoardReporterScript,
    BugTriageScript,
    ChangelogBotScript,
    DecisionLoggerScript,
    DigestBuilderScript,
    FeedbackAggregatorScript,
    OKRTrackerScript,
    RoadmapPublisherScript,
    StrategyBotScript,
)


def _w(root: Path, rel: str, body: str) -> None:
    """Écrit un fichier snapshot du pôle Direction sous ``tmp_path/direction/<rel>``."""
    p = root / "direction" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _pole_yaml(root: Path, pole: str, name: str) -> None:
    """Scaffold un ``pole.yaml`` minimal (suffit à list_poles + load_pole_config)."""
    d = root / pole
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        f"id: {pole}\nname: {name}\nagent:\n  name: {name}Agent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: []\nfront_tools: []\n",
        encoding="utf-8",
    )


async def _seed_cross_pole(root: Path) -> None:
    """Au moins un AUTRE pôle (+ son pole.yaml) avec un fait — pour le snapshot flotte."""
    _pole_yaml(root, "veille", "Veille")
    _pole_yaml(root, "direction", "Direction")
    await memory.write_memory(
        "veille",
        "trend_spotter",
        "5 sujets cyber chauds détectés cette semaine",
        kind="signal",
        tags=("cyber",),
        poles_root=root,
    )


# =============================================================================
# Enregistrement
# =============================================================================
def test_nine_scripts_registered() -> None:
    assert len(DIRECTION_SCRIPTS) == 9
    assert {c.pole for c in DIRECTION_SCRIPTS} == {"direction"}


# =============================================================================
# strategy_bot / digest_builder — digests de la vue d'ensemble flotte
# =============================================================================
async def test_strategy_bot_writes_strategy_fact(tmp_path: Path) -> None:
    await _seed_cross_pole(tmp_path)
    result = await run_script(StrategyBotScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "strategy_bot", poles_root=tmp_path)
    assert recs and recs[0].kind == "strategy"
    assert "weekly" in recs[0].tags


async def test_digest_builder_writes_digest_fact(tmp_path: Path) -> None:
    await _seed_cross_pole(tmp_path)
    result = await run_script(DigestBuilderScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "digest_builder", poles_root=tmp_path)
    assert recs and recs[0].kind == "digest"
    assert "daily" in recs[0].tags


async def test_strategy_bot_success_without_other_poles(tmp_path: Path) -> None:
    # Aucun pôle scaffoldé : la vue d'ensemble est vide mais le script réussit.
    result = await run_script(StrategyBotScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "strategy_bot", poles_root=tmp_path)
    assert recs and recs[0].kind == "strategy"


# =============================================================================
# okr_tracker — un fait par KR en retard (off_track important / at_risk)
# =============================================================================
def _current_quarter_file(today: date | None = None) -> str:
    today = today or date.today()
    quarter = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{quarter}.yaml"


async def test_okr_tracker_off_track_and_at_risk(tmp_path: Path) -> None:
    today = date.today()
    quarter = (today.month - 1) // 3 + 1
    # Prorata temporis vivant du trimestre courant — pour ancrer un actual at_risk
    # (ratio 0.5..0.9) robuste quelle que soit la date d'exécution.
    expected = okr.prorata(today, year=today.year, quarter=quarter)
    # at_risk : progress ~ 0.7 x expected (ratio dans [0.5, 0.9)).
    at_risk_actual = round(100 * 0.7 * expected)
    _w(
        tmp_path,
        f"okr/{_current_quarter_file(today)}",
        "quarter: REF\n"
        f"year: {today.year}\n"
        f"quarter_num: {quarter}\n"
        "objectives:\n"
        "  - title: Croissance\n"
        "    key_results:\n"
        "      - name: MRR fin de trimestre\n"
        "        target: 10000\n"
        "        actual: 0\n"  # progress 0 → off_track quel que soit le prorata
        "        unit: EUR\n"
        "      - name: Couverture de tests\n"
        "        target: 100\n"
        f"        actual: {at_risk_actual}\n"
        "        unit: '%'\n",
    )
    result = await run_script(OKRTrackerScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "okr_tracker", poles_root=tmp_path)
    assert recs, "au moins un KR en retard attendu"
    assert {r.kind for r in recs} == {"okr"}
    off = next(r for r in recs if "off_track" in r.tags)
    assert off.important is True
    at_risk = next(r for r in recs if "at_risk" in r.tags)
    assert at_risk.important is False


async def test_okr_tracker_skips_without_file(tmp_path: Path) -> None:
    result = await run_script(OKRTrackerScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []


# =============================================================================
# board_reporter — board pack important + doc généré
# =============================================================================
async def test_board_reporter_important_and_generates_doc(tmp_path: Path) -> None:
    await _seed_cross_pole(tmp_path)
    _w(
        tmp_path,
        "board/metrics.yaml",
        "mrr_eur: 4500\nburn_eur: 1800\nrunway_months: 5.8\nnrr_pct: 104.0\nincidents_month: 1\n",
    )
    result = await run_script(BoardReporterScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "board_reporter", poles_root=tmp_path)
    assert recs and recs[0].kind == "board" and recs[0].important is True
    assert "board" in recs[0].tags
    # Le board pack markdown est généré sous docs/.
    assert list((tmp_path / "direction" / "docs").glob("board_*.md"))


async def test_board_reporter_success_without_metrics(tmp_path: Path) -> None:
    # Sans metrics.yaml, le board pack est généré à 0 € (toujours un livrable board).
    await _seed_cross_pole(tmp_path)
    result = await run_script(BoardReporterScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "board_reporter", poles_root=tmp_path)
    assert recs and recs[0].kind == "board"


# =============================================================================
# decision_logger — un fait important par décision
# =============================================================================
async def test_decision_logger_two_decisions(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "decisions/journal.md",
        "## D-001 — Architecture v2 pôle / agent / script\n"
        "**Date :** 2026-06-17\n"
        "**Partie :** S0\n"
        "**Décision :** Refondre Argos Ops en 8 pôles métier.\n\n"
        "---\n\n"
        "## D-002 — Direction = pôle transversal\n"
        "**Date :** 2026-06-18\n"
        "**Partie :** S6\n"
        "**Décision :** La Direction gèle la publication tant qu'un P0 est ouvert.\n",
    )
    result = await run_script(DecisionLoggerScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "decision_logger", poles_root=tmp_path)
    assert len(recs) >= 2
    assert {r.kind for r in recs} == {"decision"}
    assert all(r.important for r in recs)


async def test_decision_logger_skips_without_journal(tmp_path: Path) -> None:
    result = await run_script(DecisionLoggerScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []


# =============================================================================
# changelog_bot — fait changelog (artefact public)
# =============================================================================
async def test_changelog_bot_writes_changelog(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "changelog/commits.yaml",
        "from_ref: v0.5.0\nto_ref: HEAD\ncommits:\n"
        '  - sha: 836ef6e\n    subject: "feat(finance): pôle Finance complet"\n'
        '  - sha: aa11bb2\n    subject: "fix(vente): gel Bloctel non levé"\n',
    )
    result = await run_script(ChangelogBotScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "changelog_bot", poles_root=tmp_path)
    assert recs and recs[0].kind == "changelog"
    assert "publish" in recs[0].tags


async def test_changelog_bot_skips_without_commits(tmp_path: Path) -> None:
    result = await run_script(ChangelogBotScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []


# =============================================================================
# feedback_aggregator — récurrent important / single non-important
# =============================================================================
async def test_feedback_aggregator_recurring_vs_single(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "feedback/items.yaml",
        "items:\n"
        "  - source: email\n    customer_id: acme-sa\n    date: 2026-06-09\n"
        "    topic: Export PDF FR\n    verbatim: x\n"
        "  - source: support\n    customer_id: beta-co\n    date: 2026-06-11\n"
        "    topic: Export PDF FR\n    verbatim: y\n"
        "  - source: discord\n    customer_id: delta-io\n    date: 2026-06-12\n"
        "    topic: Intégration Slack\n    verbatim: z\n",
    )
    result = await run_script(FeedbackAggregatorScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "feedback_aggregator", poles_root=tmp_path)
    assert {r.kind for r in recs} == {"feedback"}
    recurring = next(r for r in recs if "recurring" in r.tags)
    assert recurring.important is True
    assert "Export PDF FR" in recurring.body
    single = next(r for r in recs if "recurring" not in r.tags)
    assert single.important is False
    assert "Intégration Slack" in single.body


async def test_feedback_aggregator_skips_without_items(tmp_path: Path) -> None:
    result = await run_script(FeedbackAggregatorScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []


# =============================================================================
# roadmap_publisher — fait roadmap (artefact public)
# =============================================================================
async def test_roadmap_publisher_writes_roadmap(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "roadmap/annexe_d.md",
        "# Annexe D — Avancement\n\n"
        "### 1. Direction & Pilotage\n\n"
        "- [x] ✅ **DirectionAgent** · Chief of Staff · Synthèse hebdo de la flotte. *S6 livré.*\n"
        "- [~] 🟡 **WeeklySynthesis** · Synthèse IA · Récit enrichi cerveau. *S6 partiel.*\n"
        "- [ ] ⬜ **SEOPlanner** · SEO · Planification éditoriale SERP.\n",
    )
    result = await run_script(RoadmapPublisherScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "roadmap_publisher", poles_root=tmp_path)
    assert recs and recs[0].kind == "roadmap"
    assert "publish" in recs[0].tags


async def test_roadmap_publisher_skips_without_annexe(tmp_path: Path) -> None:
    result = await run_script(RoadmapPublisherScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []


# =============================================================================
# bug_triage — P0 important + tag p0, P1 tag p1, P2 = aucun fait
# =============================================================================
async def test_bug_triage_p0_p1_no_p2(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "bugs/issues.yaml",
        "issues:\n"
        "  - number: 42\n"
        '    title: "Vulnérabilité XSS sur le rapport partagé"\n'
        '    body: "Rapport public rend du HTML non échappé. Risque XSS stocké."\n'
        "    labels: [bug, security]\n"
        "    opened_at: 2026-06-16\n"
        "  - number: 43\n"
        '    title: "Crash du scanner sur les gros domaines"\n'
        '    body: "Le scanner crash au-delà de 5000 sous-domaines."\n'
        "    labels: [bug]\n"
        "    opened_at: 2026-06-14\n"
        "  - number: 44\n"
        '    title: "Améliorer le wording de la page pricing"\n'
        '    body: "Confusion entre les plans Pro et Business."\n'
        "    labels: [enhancement]\n"
        "    opened_at: 2026-06-10\n",
    )
    result = await run_script(BugTriageScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("direction", "bug_triage", poles_root=tmp_path)
    assert {r.kind for r in recs} == {"bug"}
    # P0 (XSS) : important + tag p0.
    p0 = next(r for r in recs if "p0" in r.tags)
    assert p0.important is True and "#42" in p0.body
    # P1 (crash) : tag p1, non important.
    p1 = next(r for r in recs if "p1" in r.tags)
    assert p1.important is False and "#43" in p1.body
    # P2 (pricing) : aucun fait écrit (bruit).
    assert not any("#44" in r.body or "p2" in r.tags for r in recs)


async def test_bug_triage_skips_without_issues(tmp_path: Path) -> None:
    result = await run_script(BugTriageScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []
