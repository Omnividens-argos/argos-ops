"""Tests de l'API cockpit du pôle Pub (archi v2, S3).

Hermétique : app minimale (router Pub seul) + ``POLES_DIR`` du module patché vers
``tmp_path``, avec campagnes / créas / budget scaffoldés.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import pub
from argos_ops.poles.pub import budget, creatives


def _scaffold(root: Path) -> None:
    d = root / "pub"
    (d / "campaigns").mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: pub\nname: Pub\nagent:\n  name: PubAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [veille]\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )
    (d / "campaigns" / "2026-06-15-google_search.csv").write_text(
        "Campaign,Impressions,Clicks,Cost,Conversions\n"
        "Gaspille,5000,250,500.00,2\n"  # pause critical
        "Saine,12000,480,350.00,6\n",  # scale (augmentatrice)
        encoding="utf-8",
    )
    budget.set_daily_budget(300.0, poles_root=root)
    creatives.create_creative(
        platform="google_search",
        title="Pentest SaaS",
        variants=(
            creatives.Variant(
                label="A", angle="tech", headline="Pentest continu", primary_text="x"
            ),
        ),
        poles_root=root,
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(pub, "POLES_DIR", tmp_path)
    _scaffold(tmp_path)
    app = FastAPI()
    app.include_router(pub.router)
    with TestClient(app) as c:
        yield c


def test_overview(client: TestClient) -> None:
    r = client.get("/api/poles/pub/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["pole"] == "pub"
    assert len(o["platforms"]) == 3
    assert o["budget"]["daily_budget_eur"] == 300.0
    assert o["counts"]["recommendations"] >= 1
    assert any(rec["action"] == "pause" for rec in o["recommendations"])
    assert len(o["creatives"]) == 1
    assert len(o["campaigns"]) == 2


def test_create_creative(client: TestClient) -> None:
    r = client.post(
        "/api/poles/pub/creatives",
        json={
            "platform": "meta",
            "title": "PME tranquille",
            "variants": [{"label": "A", "headline": "Sans jargon", "primary_text": "corps"}],
            "persona": "thomas",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "meta-pme-tranquille"
    assert body["status"] == "draft"
    assert body["variants"][0]["headline_ok"] is True


def test_create_creative_unknown_platform(client: TestClient) -> None:
    r = client.post(
        "/api/poles/pub/creatives", json={"platform": "tiktok", "title": "X", "variants": []}
    )
    assert r.status_code == 400


def test_creative_lifecycle_validate_golive(client: TestClient) -> None:
    cid = "google_search-pentest-saas"
    assert client.post(f"/api/poles/pub/creatives/{cid}/validate").json()["status"] == "validated"
    r = client.post(f"/api/poles/pub/creatives/{cid}/golive")
    assert r.status_code == 200
    assert r.json()["status"] == "live"


def test_golive_requires_validated(client: TestClient) -> None:
    # Draft non validée ⇒ go-live refusé (409).
    r = client.post("/api/poles/pub/creatives/google_search-pentest-saas/golive")
    assert r.status_code == 409


def test_golive_blocked_when_breaker_tripped(client: TestClient, tmp_path: Path) -> None:
    cid = "google_search-pentest-saas"
    client.post(f"/api/poles/pub/creatives/{cid}/validate")
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)  # arme
    r = client.post(f"/api/poles/pub/creatives/{cid}/golive")
    assert r.status_code == 409
    assert "breaker" in r.json()["detail"].lower()


def test_set_budget(client: TestClient) -> None:
    r = client.put("/api/poles/pub/budget", json={"daily_budget_eur": 500.0})
    assert r.status_code == 200
    assert r.json()["daily_budget_eur"] == 500.0


def test_reset_breaker(client: TestClient, tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)
    r = client.post("/api/poles/pub/breaker/reset")
    assert r.status_code == 200
    assert r.json()["breaker_tripped"] is False


def test_apply_reco_shadow(client: TestClient) -> None:
    r = client.post(
        "/api/poles/pub/recommendations/apply",
        json={
            "platform": "google_search",
            "campaign": "Gaspille",
            "action": "pause",
            "eur_delta_week": -500.0,
            "rationale": "CPA trop haut",
        },
    )
    assert r.status_code == 201
    assert r.json()["mode"] == "shadow"
    # La reco apparaît désormais comme appliquée dans l'overview.
    o = client.get("/api/poles/pub/overview").json()
    assert o["counts"]["applied"] == 1


def test_apply_spend_increasing_blocked_when_tripped(client: TestClient, tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)  # arme
    r = client.post(
        "/api/poles/pub/recommendations/apply",
        json={
            "platform": "google_search",
            "campaign": "Saine",
            "action": "scale",
            "eur_delta_week": 105.0,
            "rationale": "x",
        },
    )
    assert r.status_code == 409


def test_simulate(client: TestClient) -> None:
    r = client.post(
        "/api/poles/pub/simulate",
        json={"per_platform_daily": {"google_search": 100.0, "linkedin_sponsored": 50.0}},
    )
    assert r.status_code == 200
    sim = r.json()
    assert sim["total_daily_eur"] == 150.0
    assert len(sim["allocations"]) == 2
