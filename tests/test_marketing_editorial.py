"""Tests de la synthèse éditoriale ``plan_editorial`` (Marketing, archi v2, S2).

Brique pure : on construit des ``MemoryRecord`` à la main (signaux Veille + faits
propres) et on vérifie le routage kind → canaux, la sévérité, le tri, et
l'exclusion des faits non éditorialisables.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argos_ops.poles.marketing.channels import CHANNEL_IDS
from argos_ops.poles.marketing.editorial import (
    ROUTABLE_KINDS,
    plan_editorial,
    record_severity,
    routing_for,
)
from argos_ops.poles.memory import MemoryRecord, compute_record_id


def _rec(
    kind: str,
    body: str,
    *,
    tags: tuple[str, ...] = (),
    important: bool = False,
    age_min: int = 0,
) -> MemoryRecord:
    return MemoryRecord(
        id=compute_record_id(body),  # id stable = hash du corps (comme la vraie mémoire)
        pole="veille",
        script="x",
        kind=kind,
        body=body,
        important=important,
        tags=tags,
        created_at=datetime.now(UTC) - timedelta(minutes=age_min),
    )


def test_routes_kinds_to_channels() -> None:
    recs = plan_editorial([_rec("trend", "Faille npm supply-chain")])
    assert len(recs) == 1
    assert recs[0].kind == "trend"
    assert "linkedin" in recs[0].channels


def test_breach_routed_pedagogical_channels() -> None:
    recs = plan_editorial([_rec("breach", "fuite massive", tags=("critical",))])
    assert recs[0].severity == "critical"
    # Angle défensif anti-FUD + canaux infosec.
    assert set(recs[0].channels) == {"linkedin", "x", "mastodon"}


def test_non_routable_kinds_excluded() -> None:
    records = [
        _rec("publication", "Publié sur LinkedIn : x"),  # mémoire propre marketing
        _rec("engagement", "Engagement linkedin"),
        _rec("intent_signal", "embauche CISO chez ACME"),  # signal vente, pas contenu
    ]
    assert plan_editorial(records) == []


def test_severity_sorted_desc() -> None:
    records = [
        _rec("competitor", "concurrent change pricing"),  # info
        _rec("cve", "CVE critique nginx", tags=("critical",)),  # critical
    ]
    recs = plan_editorial(records)
    assert recs[0].kind == "cve"
    assert recs[0].severity == "critical"
    assert recs[-1].kind == "competitor"


def test_record_severity_levels() -> None:
    assert record_severity(_rec("trend", "a", tags=("critical",))) == "critical"
    assert record_severity(_rec("trend", "b", important=True)) == "warning"
    assert record_severity(_rec("trend", "c")) == "info"


def test_routing_for_unknown_is_none() -> None:
    assert routing_for("intent_signal") is None
    assert routing_for("trend") is not None


def test_all_routable_kinds_route_to_known_channels() -> None:
    records = [_rec(kind, f"signal {kind}") for kind in sorted(ROUTABLE_KINDS)]
    recs = plan_editorial(records)
    assert len(recs) == len(ROUTABLE_KINDS)
    for rec in recs:
        assert rec.channels, f"{rec.kind} sans canal"
        assert all(c in CHANNEL_IDS for c in rec.channels), f"{rec.kind} → canal inconnu"


def test_aggregation_count_order_and_tiebreak() -> None:
    records = [
        _rec("trend", "trend info récent", age_min=1),
        _rec("trend", "trend warning", important=True, age_min=5),
        _rec("trend", "trend critique", tags=("critical",), age_min=10),
        # 1 seul competitor (info) → doit passer APRÈS trend (cardinalité 3 > 1)
        _rec("competitor", "competitor seul"),
    ]
    recs = plan_editorial(records)
    trend = next(r for r in recs if r.kind == "trend")
    assert trend.count == 3
    assert trend.severity == "critical"  # max du groupe
    # record_ids triés par sévérité décroissante puis récence : critique en tête.
    assert trend.record_ids[0] == _rec("trend", "trend critique", tags=("critical",)).id
    # Tri inter-recos : trend (critical) avant competitor (info).
    assert recs[0].kind == "trend"
