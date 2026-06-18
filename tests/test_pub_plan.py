"""Tests de la synthèse du plan d'actions (Pub, archi v2, S3).

Brique pure : on construit des ``MemoryRecord`` (signaux Veille + recos
``ad_reco`` écrites par l'optimiseur) et on vérifie le routage des idées de créa,
la lecture de l'action dans les tags, et le **gel par le breaker**.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argos_ops.poles.memory import MemoryRecord, compute_record_id
from argos_ops.poles.pub.plan import plan_actions, record_severity


def _rec(
    kind: str,
    body: str,
    *,
    tags: tuple[str, ...] = (),
    important: bool = False,
    age_min: int = 0,
) -> MemoryRecord:
    return MemoryRecord(
        id=compute_record_id(body),
        pole="veille",
        script="x",
        kind=kind,
        body=body,
        important=important,
        tags=tags,
        created_at=datetime.now(UTC) - timedelta(minutes=age_min),
    )


def test_creative_idea_from_veille_trend() -> None:
    plans = plan_actions([_rec("trend", "Faille npm supply-chain")])
    assert len(plans) == 1
    p = plans[0]
    assert p.kind == "creative_idea"
    assert p.action == "new_campaign"
    assert "google_search" in p.platforms


def test_breach_routed_defensive_anti_fud() -> None:
    plans = plan_actions([_rec("breach", "fuite massive", tags=("critical",))])
    assert plans[0].severity == "critical"
    # Angle défensif, plateforme pro (pas de canal anxiogène grand public).
    assert plans[0].platforms == ("linkedin_sponsored",)
    assert "FUD" in plans[0].angle


def test_non_routable_veille_kinds_excluded() -> None:
    records = [
        _rec("intent_signal", "embauche CISO"),  # signal Vente
        _rec("seo_movement", "perte position"),  # organique
        _rec("press", "mention presse"),  # RP
    ]
    assert plan_actions(records) == []


def test_budget_action_from_ad_reco_tags() -> None:
    rec = _rec(
        "ad_reco", "[google_search] Saine — scaler +30%", tags=("scale", "google_search", "info")
    )
    plans = plan_actions([rec])
    assert len(plans) == 1
    assert plans[0].kind == "budget_action"
    assert plans[0].action == "scale"
    assert plans[0].platforms == ("google_search",)
    assert plans[0].suppressed_by_breaker is False


def test_breaker_freezes_spend_increasing_actions() -> None:
    scale = _rec("ad_reco", "scale gs", tags=("scale", "google_search", "info"))
    pause = _rec("ad_reco", "pause gs", tags=("pause", "google_search", "critical"))
    plans = plan_actions([scale, pause], breaker_tripped=True)
    by_action = {p.action: p for p in plans}
    # scale augmente la dépense ⇒ gelé ; pause la réduit ⇒ jamais gelé.
    assert by_action["scale"].suppressed_by_breaker is True
    assert by_action["pause"].suppressed_by_breaker is False


def test_ordering_critical_budget_before_info_idea() -> None:
    pause = _rec("ad_reco", "pause gs", tags=("pause", "google_search", "critical"))
    idea = _rec("competitor", "concurrent a bougé")  # info
    plans = plan_actions([idea, pause])
    assert plans[0].action == "pause"
    assert plans[0].severity == "critical"


def test_ad_reco_without_known_action_tag_skipped() -> None:
    rec = _rec("ad_reco", "bruit sans action", tags=("google_search",))
    assert plan_actions([rec]) == []


def test_record_severity_levels() -> None:
    assert record_severity(_rec("trend", "a", tags=("critical",))) == "critical"
    assert record_severity(_rec("trend", "b", important=True)) == "warning"
    assert record_severity(_rec("trend", "c")) == "info"
