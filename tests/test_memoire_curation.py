"""Tests de la logique **pure** de curation (archi v2, S7).

Aucune I/O : on construit des :class:`MemoryRecord` à la main et on vérifie le
:class:`CurationPlan`. Le test central : un fait ``important`` (ou pattern
protégé) n'apparaît **jamais** dans ``to_delete``, même périmé/stale.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argos_ops.poles.memoire.curation import plan_curation
from argos_ops.poles.memoire.policy import MemoryPolicy
from argos_ops.poles.memory import MemoryRecord

NOW = datetime(2026, 6, 18, tzinfo=UTC)
POLE = "veille"


def rec(
    rid: str,
    *,
    kind: str = "note",
    important: bool = False,
    age_days: int = 0,
    tags: tuple[str, ...] = (),
    source: str | None = None,
    script: str = "s",
) -> MemoryRecord:
    return MemoryRecord(
        id=rid,
        pole=POLE,
        script=script,
        kind=kind,
        body=f"corps du fait {rid}",
        important=important,
        source=source,
        tags=tags,
        created_at=NOW - timedelta(days=age_days),
    )


def _ids(items: object) -> set[str]:
    return {i.record_id for i in items}  # type: ignore[attr-defined]


def test_inactive_pole_never_deletes() -> None:
    policy = MemoryPolicy(active_for=())  # POLE non listé
    plan = plan_curation({"s": [rec("a", age_days=999)]}, policy, POLE, now=NOW)
    assert plan.active is False
    assert plan.to_delete == ()
    assert plan.kept == plan.scanned == 1


def test_important_expired_is_protected_never_deleted() -> None:
    """INVARIANT central : important + périmé ⇒ protégé, jamais supprimable."""
    policy = MemoryPolicy(active_for=(POLE,), default_ttl_days=180, protect_important=True)
    imp = rec("imp", important=True, age_days=999)
    plan = plan_curation({"s": [imp]}, policy, POLE, now=NOW)

    assert "imp" not in _ids(plan.to_delete)
    prot = next(p for p in plan.protected if p.record_id == "imp")
    assert prot.reason == "important"
    assert prot.would_delete is True
    assert prot.would_delete_reason == "expired"
    assert plan.n_saved_from_delete == 1


def test_pattern_protected_kind_never_deleted() -> None:
    policy = MemoryPolicy(active_for=(POLE,), protected_kinds=("decision",))
    plan = plan_curation({"s": [rec("d", kind="decision", age_days=999)]}, policy, POLE, now=NOW)
    assert "d" not in _ids(plan.to_delete)
    prot = next(p for p in plan.protected if p.record_id == "d")
    assert prot.reason == "pattern"
    assert prot.would_delete is True


def test_pattern_protected_tag_and_source() -> None:
    policy = MemoryPolicy(
        active_for=(POLE,), protected_tags=("pinned",), protected_sources=("oracle",)
    )
    by_tag = rec("t", tags=("pinned",), age_days=999)
    by_src = rec("u", source="oracle", age_days=999)
    plan = plan_curation({"s": [by_tag, by_src]}, policy, POLE, now=NOW)
    assert _ids(plan.to_delete) == set()
    assert {p.record_id for p in plan.protected} == {"t", "u"}


def test_plain_expired_is_candidate() -> None:
    policy = MemoryPolicy(active_for=(POLE,), default_ttl_days=180)
    plan = plan_curation({"s": [rec("e", age_days=200)]}, policy, POLE, now=NOW)
    cand = next(c for c in plan.to_delete if c.record_id == "e")
    assert cand.reason == "expired"


def test_ttl_by_kind_override() -> None:
    policy = MemoryPolicy(active_for=(POLE,), default_ttl_days=180, ttl_by_kind={"signal": 30})
    plan = plan_curation(
        {"s": [rec("sig", kind="signal", age_days=40), rec("note", age_days=40)]},
        policy,
        POLE,
        now=NOW,
    )
    # signal périmé à 40 j (TTL 30) ; note pas périmée (TTL 180) et trop jeune pour stale.
    assert _ids(plan.to_delete) == {"sig"}


def test_fresh_is_kept() -> None:
    policy = MemoryPolicy(active_for=(POLE,), default_ttl_days=180, min_stale_days=30)
    plan = plan_curation({"s": [rec("fr", age_days=2)]}, policy, POLE, now=NOW)
    assert plan.to_delete == ()
    assert plan.protected == ()
    assert plan.kept == 1


def test_stale_superseded_versions() -> None:
    # keep_recent=2 : on garde les 2 plus récents d'un même kind ; les plus
    # vieux (au-delà) et ≥ min_stale_days deviennent stale.
    policy = MemoryPolicy(
        active_for=(POLE,), default_ttl_days=180, keep_recent_per_kind=2, min_stale_days=30
    )
    records = [
        rec("n0", age_days=32),  # rank 0 (le plus récent) → gardé
        rec("n1", age_days=34),  # rank 1 → gardé
        rec("n2", age_days=36),  # rank 2 → stale
        rec("n3", age_days=38),  # rank 3 → stale
        rec("n4", age_days=40),  # rank 4 → stale
    ]
    plan = plan_curation({"s": records}, policy, POLE, now=NOW)
    assert _ids(plan.to_delete) == {"n2", "n3", "n4"}
    assert all(c.reason == "stale" for c in plan.to_delete)
    assert plan.kept == 2


def test_stale_gated_by_min_stale_days() -> None:
    # keep_recent=0 mais faits trop jeunes (< min_stale) ⇒ jamais stale.
    policy = MemoryPolicy(
        active_for=(POLE,), default_ttl_days=180, keep_recent_per_kind=0, min_stale_days=30
    )
    plan = plan_curation(
        {"s": [rec("y0", age_days=10), rec("y1", age_days=12)]}, policy, POLE, now=NOW
    )
    assert plan.to_delete == ()
    assert plan.kept == 2


def test_expired_precedence_over_stale() -> None:
    # Un fait à la fois périmé ET stale est étiqueté « expired » (signal plus fort).
    policy = MemoryPolicy(
        active_for=(POLE,), default_ttl_days=30, keep_recent_per_kind=1, min_stale_days=10
    )
    records = [rec("fresh", age_days=5), rec("oldish", age_days=200)]
    plan = plan_curation({"s": records}, policy, POLE, now=NOW)
    cand = next(c for c in plan.to_delete if c.record_id == "oldish")
    assert cand.reason == "expired"


def test_stale_is_per_script_and_kind() -> None:
    # Le rang stale se calcule par (script, kind) : deux scripts n'interfèrent pas.
    policy = MemoryPolicy(
        active_for=(POLE,), default_ttl_days=180, keep_recent_per_kind=1, min_stale_days=10
    )
    by_script = {
        "a": [rec("a0", age_days=20, script="a"), rec("a1", age_days=40, script="a")],
        "b": [rec("b0", age_days=20, script="b")],
    }
    plan = plan_curation(by_script, policy, POLE, now=NOW)
    # a1 est stale (rank 1) ; a0 et b0 (rank 0 chacun) gardés.
    assert _ids(plan.to_delete) == {"a1"}


def test_stale_ranking_deterministic_across_input_order() -> None:
    # 3 faits au MÊME created_at (égalité) : le choix du « stale » ne doit PAS
    # dépendre de l'ordre d'entrée (sinon preview et cleaner divergent). Tiebreaker
    # = id décroissant ⇒ ccc(rank0), bbb(rank1), aaa(rank2 → stale).
    policy = MemoryPolicy(
        active_for=(POLE,), default_ttl_days=180, keep_recent_per_kind=2, min_stale_days=10
    )
    a, b, c = rec("aaa", age_days=50), rec("bbb", age_days=50), rec("ccc", age_days=50)
    p1 = plan_curation({"s": [a, b, c]}, policy, POLE, now=NOW)
    p2 = plan_curation({"s": [c, b, a]}, policy, POLE, now=NOW)
    assert _ids(p1.to_delete) == _ids(p2.to_delete) == {"aaa"}


def test_counts_consistency() -> None:
    policy = MemoryPolicy(active_for=(POLE,), default_ttl_days=180, protect_important=True)
    records = [
        rec("imp", important=True, age_days=999),  # protégé (would_delete)
        rec("exp", age_days=999),  # candidat
        rec("fresh", age_days=1),  # gardé
    ]
    plan = plan_curation({"s": records}, policy, POLE, now=NOW)
    assert plan.scanned == 3
    assert plan.n_delete == 1
    assert plan.n_protected == 1
    assert plan.n_important == 1
    assert plan.kept == 1
    # somme cohérente : delete + protected + kept == scanned
    assert plan.n_delete + plan.n_protected + plan.kept == plan.scanned
