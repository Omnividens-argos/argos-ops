"""Tests du plan d'oversight du pôle Direction (archi v2, S6) — pur, déterministe."""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.poles.direction.plan import DirectionPlan, plan_actions, severity_rank
from argos_ops.poles.memory import MemoryRecord


def _rec(
    kind: str,
    *,
    pole: str = "direction",
    tags: tuple[str, ...] = (),
    important: bool = False,
    body: str = "x",
    minute: int = 0,
) -> MemoryRecord:
    return MemoryRecord(
        id=f"{pole}-{kind}-{'-'.join(tags)}-{minute}",
        pole=pole,
        script=kind,
        kind=kind,
        body=body,
        important=important,
        source=None,
        tags=tags,
        created_at=datetime(2026, 6, 18, 9, minute, tzinfo=UTC),
    )


# =============================================================================
# Routing par kind (faits du pôle Direction)
# =============================================================================
def test_route_bug_severity_by_label() -> None:
    p0 = plan_actions([_rec("bug", tags=("p0",))], release_blocking=False)
    assert p0 and p0[0].kind == "bug" and p0[0].severity == "critical"
    p1 = plan_actions([_rec("bug", tags=("p1",))], release_blocking=False)
    assert p1 and p1[0].severity == "warning"
    p2 = plan_actions([_rec("bug", tags=())], release_blocking=False)
    assert p2 and p2[0].severity == "info"


def test_route_okr_off_track_vs_at_risk() -> None:
    off = plan_actions([_rec("okr", tags=("off_track",))], release_blocking=False)
    assert off and off[0].kind == "okr" and off[0].severity == "critical"
    risk = plan_actions([_rec("okr", tags=("at_risk",))], release_blocking=False)
    assert risk and risk[0].severity == "warning"
    # OKR on-track / sans tag → non actionnable.
    assert plan_actions([_rec("okr", tags=())], release_blocking=False) == []


def test_route_feedback_important_is_warning() -> None:
    imp = plan_actions([_rec("feedback", important=True)], release_blocking=False)
    assert imp and imp[0].kind == "feedback" and imp[0].severity == "warning"
    plain = plan_actions([_rec("feedback")], release_blocking=False)
    assert plain and plain[0].severity == "info"


def test_route_decision_and_board_are_info() -> None:
    dec = plan_actions([_rec("decision")], release_blocking=False)
    assert dec and dec[0].kind == "decision" and dec[0].severity == "info"
    bd = plan_actions([_rec("board")], release_blocking=False)
    assert bd and bd[0].kind == "board" and bd[0].severity == "info"


def test_route_strategy_digest_not_actionable() -> None:
    assert plan_actions([_rec("strategy"), _rec("digest")], release_blocking=False) == []


# =============================================================================
# Publication + gel release
# =============================================================================
def test_publish_suppressed_when_release_blocking() -> None:
    for kind in ("changelog", "roadmap", "release_notes"):
        blocked = plan_actions([_rec(kind)], release_blocking=True)
        assert blocked and blocked[0].kind == "publish"
        assert blocked[0].suppressed_by_release is True
        open_ = plan_actions([_rec(kind)], release_blocking=False)
        assert open_ and open_[0].kind == "publish"
        assert open_[0].suppressed_by_release is False


# =============================================================================
# Cross-pôle → oversight
# =============================================================================
def test_cross_pole_oversight_one_action_per_pole_at_worst() -> None:
    recs = [
        # Vente : 2 faits, dont un critique → oversight critique.
        _rec("bloctel", pole="vente", tags=("warning",), minute=1),
        _rec("bloctel", pole="vente", tags=("critical",), body="gel bloctel", minute=2),
        # Finance : que du warning → oversight warning.
        _rec("contract", pole="finance", tags=("urgent",), minute=3),
        # Veille : que de l'info → pas d'oversight.
        _rec("trend", pole="veille", tags=(), minute=4),
    ]
    plans = plan_actions(recs, release_blocking=False)
    oversight = [p for p in plans if p.kind == "oversight"]
    by_pole = {p.pole: p for p in oversight}
    assert set(by_pole) == {"vente", "finance"}  # veille (info) ignoré
    assert by_pole["vente"].severity == "critical"
    assert by_pole["finance"].severity == "warning"
    # Une seule action d'oversight par pôle.
    assert len(oversight) == 2


# =============================================================================
# Tri : sévérité décroissante (critical d'abord), exécutable avant gelé
# =============================================================================
def test_sort_critical_first_executable_before_suppressed() -> None:
    recs = [
        _rec("changelog", minute=1),  # publish, info, suppressed (release_blocking)
        _rec("bug", tags=("p0",), minute=2),  # critical
        _rec("decision", minute=3),  # info, non suppressed
        _rec(
            "bloctel", pole="vente", tags=("critical",), body="gel", minute=4
        ),  # oversight critical
    ]
    plans = plan_actions(recs, release_blocking=True)
    assert plans[0].severity == "critical"  # critique en tête
    # Parmi les info, l'exécutable (decision) passe avant la publication gelée.
    infos = [p for p in plans if p.severity == "info"]
    assert infos[0].suppressed_by_release is False
    assert infos[-1].suppressed_by_release is True


def test_severity_rank_monotonic() -> None:
    assert severity_rank("critical") > severity_rank("warning") > severity_rank("info")


def test_unknown_kind_ignored() -> None:
    assert plan_actions([_rec("mystere")], release_blocking=False) == []


def test_plan_is_frozen_dataclass() -> None:
    p = DirectionPlan("info", "decision", "a", "b", "direction")
    assert p.record_ids == () and p.suppressed_by_release is False
