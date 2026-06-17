"""Tests de l'optimiseur de campagnes (Pub, archi v2, S3) — CSV → recos chiffrées.

Brique pure : on construit des CSV / ``CampaignRow`` à la main et on vérifie le
parsing tolérant, le routage vers une action par campagne, le tri/cap, et les
agrégats (dépense, CPA par plateforme).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import optimizer
from argos_ops.poles.pub.optimizer import CampaignRow


def _row(
    platform: str, campaign: str, impr: int, clicks: int, cost: float, conv: int
) -> CampaignRow:
    return CampaignRow(
        platform=platform,
        campaign=campaign,
        impressions=impr,
        clicks=clicks,
        cost_eur=cost,
        conversions=conv,
    )


# --- Parsing -----------------------------------------------------------------
def test_parse_csv_canonical_headers() -> None:
    csv = "Campaign,Impressions,Clicks,Cost,Conversions\nArgos SaaS,1000,40,80.00,2\n"
    rows = optimizer.parse_campaign_csv(csv, platform="google_search")
    assert len(rows) == 1
    r = rows[0]
    assert r.campaign == "Argos SaaS"
    assert r.impressions == 1000
    assert r.clicks == 40
    assert r.cost_eur == 80.0
    assert r.conversions == 2
    assert round(r.ctr, 3) == 0.04
    assert r.cpa == 40.0


def test_parse_csv_header_aliases_and_locale() -> None:
    # En-têtes FR + montants « 1 234,56 € » (espace insécable + virgule décimale).
    csv = 'Campagne,Impr.,Clics,Coût,Conv.\nTest,"1\xa0200",30,"1\xa0234,56",0\n'
    rows = optimizer.parse_campaign_csv(csv, platform="linkedin_sponsored")
    assert rows[0].impressions == 1200
    assert rows[0].cost_eur == 1234.56


def test_to_float_locale_robust() -> None:
    f = optimizer._to_float
    assert f("350.00") == 350.0
    assert f("1,5") == 1.5
    assert f("€80") == 80.0
    assert f("1\xa0200") == 1200.0
    assert f("12,000") == 12000.0  # US thousands (bug historique : donnait 12.0)
    assert f("12.000") == 12000.0  # EU thousands
    assert f("1.234.567") == 1234567.0
    assert f("1,234.56") == 1234.56  # US mixte
    assert f("1.234,56") == 1234.56  # EU mixte
    assert f("") == 0.0
    assert f("n/a") == 0.0


def test_us_thousands_dont_corrupt_clicks() -> None:
    # Régression : "12,000" clics ne doit pas être lu comme 12 (CTR x1000).
    csv = 'Campaign,Impressions,Clicks,Cost,Conversions\nUS,"1,200,000","12,000","3,500.00",100\n'
    rows = optimizer.parse_campaign_csv(csv, platform="google_search")
    assert rows[0].impressions == 1200000
    assert rows[0].clicks == 12000
    assert rows[0].cost_eur == 3500.0


def test_parse_csv_skips_blank_rows_and_missing_campaign_col() -> None:
    assert optimizer.parse_campaign_csv("Foo,Bar\n1,2\n", platform="meta") == []
    csv = "Campaign,Cost\n,50\nReal,80\n"
    rows = optimizer.parse_campaign_csv(csv, platform="meta")
    assert [r.campaign for r in rows] == ["Real"]


# --- Recommandations ---------------------------------------------------------
def test_recommend_pause_on_high_cpa() -> None:
    # CPA = 500/2 = 250 > 2x80 ⇒ pause (critical), économie -cost.
    rows = {"google_search": [_row("google_search", "Gaspille", 5000, 250, 500.0, 2)]}
    recos = optimizer.recommend(rows, cpa_target_eur=80, window_days=7)
    assert recos[0].action == "pause"
    assert recos[0].severity == "critical"
    assert recos[0].eur_delta_week == -500.0


def test_recommend_drop_keyword_google_only() -> None:
    # 0 conversion, ≥100 € dépensés, plateforme à mots-clés ⇒ drop_keyword.
    rows = {"google_search": [_row("google_search", "ZeroConv", 20000, 300, 240.0, 0)]}
    recos = optimizer.recommend(rows, cpa_target_eur=80, window_days=7)
    assert recos[0].action == "drop_keyword"
    assert recos[0].eur_delta_week == -240.0
    # LinkedIn (audience, pas de mot-clé) avec 0 conv ⇒ pas de drop_keyword.
    rows_li = {"linkedin_sponsored": [_row("linkedin_sponsored", "ZeroConv", 20000, 300, 240.0, 0)]}
    assert all(r.action != "drop_keyword" for r in optimizer.recommend(rows_li))


def test_recommend_scale_on_healthy() -> None:
    # CPA 58 < 80, CTR 4% > bench 3% ⇒ scale (info), dépense additionnelle +30%.
    rows = {"google_search": [_row("google_search", "Saine", 12000, 480, 350.0, 6)]}
    recos = optimizer.recommend(rows, cpa_target_eur=80, window_days=7)
    assert recos[0].action == "scale"
    assert recos[0].severity == "info"
    assert round(recos[0].eur_delta_week, 1) == 105.0


def test_recommend_new_creative_low_ctr() -> None:
    # CTR 1.5% < bench 3% mais conv saine ⇒ new_creative.
    rows = {"google_search": [_row("google_search", "PeuCliquee", 8000, 120, 200.0, 3)]}
    recos = optimizer.recommend(rows, cpa_target_eur=80, window_days=7)
    assert recos[0].action == "new_creative"


def test_recommend_diagnose_lp() -> None:
    # CTR sain (4%) mais conv/clic < 1% ⇒ diagnostic landing page.
    rows = {"google_search": [_row("google_search", "MauvaiseLP", 10000, 400, 300.0, 1)]}
    recos = optimizer.recommend(rows, cpa_target_eur=500, window_days=7)
    assert recos[0].action == "diagnose_lp"
    assert recos[0].eur_delta_week == 0.0


def test_recommend_caps_at_five_and_sorts_by_severity() -> None:
    rows = {
        "google_search": [
            _row("google_search", "Pause", 5000, 250, 500.0, 2),  # pause critical
            _row("google_search", "Drop", 20000, 300, 240.0, 0),  # drop warning
            _row("google_search", "NewCrea", 8000, 120, 200.0, 3),  # warning
            _row("google_search", "Scale1", 12000, 480, 350.0, 6),  # info
        ],
        "linkedin_sponsored": [
            _row("linkedin_sponsored", "Scale2", 30000, 150, 400.0, 5),  # info
            _row("linkedin_sponsored", "Scale3", 40000, 200, 200.0, 4),  # info
        ],
    }
    recos = optimizer.recommend(rows, cpa_target_eur=80, window_days=7)
    assert len(recos) == 5  # cap
    assert recos[0].action == "pause"  # critical en tête
    assert recos[0].severity == "critical"


def test_recommend_id_is_stable() -> None:
    rows = {"google_search": [_row("google_search", "Argos - SaaS", 5000, 250, 500.0, 2)]}
    reco = optimizer.recommend(rows)[0]
    assert reco.id == "google_search-argos-saas-pause"


# --- Agrégats ----------------------------------------------------------------
def test_aggregates() -> None:
    rows = {
        "google_search": [_row("google_search", "A", 100, 10, 300.0, 3)],
        "linkedin_sponsored": [_row("linkedin_sponsored", "B", 100, 10, 200.0, 0)],
    }
    assert optimizer.total_spend(rows) == 500.0
    assert optimizer.spend_by_platform(rows) == {
        "google_search": 300.0,
        "linkedin_sponsored": 200.0,
    }
    cpa = optimizer.cpa_by_platform(rows)
    assert cpa["google_search"] == 100.0  # 300/3
    assert cpa["linkedin_sponsored"] == 0.0  # 0 conv ⇒ 0


# --- Chargement disque -------------------------------------------------------
def test_load_latest_campaigns_keeps_most_recent_per_platform(tmp_path: Path) -> None:
    d = tmp_path / "pub" / "campaigns"
    d.mkdir(parents=True)
    (d / "2026-06-01-google_search.csv").write_text(
        "Campaign,Cost,Conversions,Clicks,Impressions\nOld,10,1,1,1\n", encoding="utf-8"
    )
    (d / "2026-06-15-google_search.csv").write_text(
        "Campaign,Cost,Conversions,Clicks,Impressions\nNew,20,1,1,1\n", encoding="utf-8"
    )
    (d / "2026-06-10-unknownplatform.csv").write_text("Campaign,Cost\nX,5\n", encoding="utf-8")
    out = optimizer.load_latest_campaigns(poles_root=tmp_path)
    assert list(out) == ["google_search"]  # plateforme inconnue ignorée
    assert [r.campaign for r in out["google_search"]] == ["New"]  # plus récent
