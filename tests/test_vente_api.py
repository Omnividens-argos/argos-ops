"""Tests de l'API cockpit du pôle Vente (archi v2, S4).

Hermétique : app minimale (router Vente seul) + ``POLES_DIR`` du module patché
vers ``tmp_path``, avec pipe / customers / tickets / inbox / leads scaffoldés.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import vente


def _write(root: Path, rel: str, body: str) -> None:
    p = root / "vente" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _scaffold(root: Path) -> None:
    (root / "vente").mkdir(parents=True, exist_ok=True)
    (root / "vente" / "pole.yaml").write_text(
        "id: vente\nname: Vente\nagent:\n  name: VenteAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [veille, marketing]\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )
    _write(
        root,
        "deals/pipe.yaml",
        "deals:\n  - deal_id: D1\n    company: Acme\n    stage: proposal_sent\n"
        "    amount_eur: 6000\n    last_activity_at: '2026-05-01'\n",
    )
    _write(
        root,
        "cs/customers.yaml",
        "customers:\n  - customer_id: red\n    name: R\n    contact_email: a@r.fr\n    contact_name: A\n"
        "    plan: starter\n    signup_date: '2026-02-01'\n    last_nps: 3\n    tickets_30d: 6\n"
        "    usage: {scans_this_month: 4, scans_quota: 50, last_login_days_ago: 40}\n",
    )
    _write(
        root,
        "support/tickets.yaml",
        "tickets:\n  - ticket_id: T1\n    customer_id: red\n    subject: prod down\n"
        "    body: incident urgent\n    opened_at: '2026-06-10'\n    plan: pro\n",
    )
    _write(
        root,
        "inbox/messages.yaml",
        "messages:\n"
        "  - id: lead1\n    from_email: a@b.fr\n    from_name: Lead\n    subject: Devis\n    body: vos tarifs\n    received_at: '2026-06-17'\n"
        "  - id: human1\n    from_email: dpo@x.fr\n    subject: Q\n    body: parler a un humain svp pas de bot\n    received_at: '2026-06-17'\n",
    )
    _write(
        root,
        "outbound/inbox/leads.csv",
        "full_name,domain,title_hint,linkedin_url\n"
        "Marc Dupont,acme-securite.fr,CISO,\n"
        "Jean Bricoleur,gmail.com,Gérant,\n",
    )
    _write(
        root,
        "proposals/D1/context.yaml",
        "deal_id: D1\ncompany: Acme\ncontact_name: Marc\ncontact_email: marc@acme.fr\n"
        "plan: Argos Pro\nmonthly_price_eur: 350\nissue_date: '2026-06-01'\n",
    )
    _write(
        root,
        "meetings/requests.yaml",
        "requests:\n  - request_id: rdv-1\n    attendee_email: marc@acme.fr\n    attendee_name: Marc\n"
        "    company: Acme\n    starts_at: '2026-06-20T14:00:00+00:00'\n    duration_minutes: 30\n    status: pending\n",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(vente, "POLES_DIR", tmp_path)
    _scaffold(tmp_path)
    app = FastAPI()
    app.include_router(vente.router)
    with TestClient(app) as c:
        yield c


def test_overview(client: TestClient) -> None:
    r = client.get("/api/poles/vente/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["pole"] == "vente"
    assert len(o["pipeline"]) == 1
    assert len(o["inbox"]) == 2
    assert o["counts"]["p0"] == 1
    assert o["counts"]["health_red"] == 1
    assert o["counts"]["outbound_frozen"] is False
    # Marc éligible, Jean (gmail) inéligible.
    by_slug = {lead["slug"]: lead for lead in o["leads"]}
    assert any(lead["eligible"] for lead in by_slug.values())
    assert any(not lead["eligible"] for lead in by_slug.values())


def test_inbox_human_blocked(client: TestClient) -> None:
    r = client.post("/api/poles/vente/inbox/human1/draft")
    assert r.status_code == 409
    assert "humaine" in r.json()["detail"].lower()


def test_inbox_lead_drafts(client: TestClient) -> None:
    r = client.post("/api/poles/vente/inbox/lead1/draft")
    assert r.status_code == 200
    assert r.json()["status"] == "drafted"


def test_leads_upload(client: TestClient) -> None:
    r = client.post(
        "/api/poles/vente/leads/upload",
        json={"rows": [{"full_name": "Claire Moreau", "domain": "secure-corp.fr"}]},
    )
    assert r.status_code == 201
    assert r.json()["added"] == 1


def test_sequence_blocked_for_ineligible(client: TestClient) -> None:
    o = client.get("/api/poles/vente/overview").json()
    ineligible = next(lead["slug"] for lead in o["leads"] if not lead["eligible"])
    r = client.post("/api/poles/vente/sequences", json={"slug": ineligible})
    assert r.status_code == 409
    assert "inéligible" in r.json()["detail"].lower()


def test_sequence_scaffolds_eligible(client: TestClient) -> None:
    o = client.get("/api/poles/vente/overview").json()
    eligible = next(lead["slug"] for lead in o["leads"] if lead["eligible"])
    r = client.post("/api/poles/vente/sequences", json={"slug": eligible})
    assert r.status_code == 201
    assert r.json()["status"] == "scaffolded"


def test_sequence_frozen_by_bloctel(client: TestClient, tmp_path: Path) -> None:
    # Arme le gel Bloctel : un téléphone opposé.
    _write(tmp_path, "compliance/lead_phones.csv", "identifier,phone\nl,+33611223344\n")
    _write(tmp_path, "compliance/bloctel/bloctel_2026-06.txt", "+33611223344\n")
    o = client.get("/api/poles/vente/overview").json()
    assert o["counts"]["outbound_frozen"] is True
    eligible = next(lead["slug"] for lead in o["leads"] if lead["eligible"])
    r = client.post("/api/poles/vente/sequences", json={"slug": eligible})
    assert r.status_code == 409
    assert "bloctel" in r.json()["detail"].lower()


def test_book_meeting(client: TestClient) -> None:
    r = client.post("/api/poles/vente/meetings/rdv-1/book")
    assert r.status_code == 200
    assert r.json()["status"] == "drafted"


def test_move_deal_stage(client: TestClient) -> None:
    r = client.patch("/api/poles/vente/deals/D1/stage", json={"stage": "contract_sent"})
    assert r.status_code == 200
    assert r.json()["deal_id"] == "D1"
    assert r.json()["stage"] == "contract_sent"
    # Persisté : l'overview relit pipe.yaml et voit le nouveau stade.
    o = client.get("/api/poles/vente/overview").json()
    d1 = next(d for d in o["pipeline"] if d["deal_id"] == "D1")
    assert d1["stage"] == "contract_sent"


def test_move_deal_stage_invalid(client: TestClient) -> None:
    r = client.patch("/api/poles/vente/deals/D1/stage", json={"stage": "negotiation"})
    assert r.status_code == 422


def test_move_deal_stage_unknown_deal(client: TestClient) -> None:
    r = client.patch("/api/poles/vente/deals/ghost/stage", json={"stage": "won"})
    assert r.status_code == 404


def test_meeting_ics(client: TestClient) -> None:
    assert client.post("/api/poles/vente/meetings/rdv-1/book").status_code == 200
    r = client.get("/api/poles/vente/meetings/rdv-1/ics")
    assert r.status_code == 200
    body = r.json()
    assert body["request_id"] == "rdv-1"
    assert body["filename"] == "rdv-1.ics"
    assert "BEGIN:VCALENDAR" in body["ics"]


def test_meeting_ics_regenerated_without_book(client: TestClient) -> None:
    # Pas de book préalable → régénération à la volée.
    r = client.get("/api/poles/vente/meetings/rdv-1/ics")
    assert r.status_code == 200
    assert "BEGIN:VCALENDAR" in r.json()["ics"]


def test_meeting_ics_unknown_404(client: TestClient) -> None:
    assert client.get("/api/poles/vente/meetings/ghost/ics").status_code == 404


def test_draft_proposal(client: TestClient) -> None:
    r = client.post("/api/poles/vente/proposals/D1/draft")
    assert r.status_code == 200
    assert r.json()["proposal_status"] == "drafted"


def test_unknown_404(client: TestClient) -> None:
    assert client.post("/api/poles/vente/proposals/ghost/draft").status_code == 404
    assert client.post("/api/poles/vente/meetings/ghost/book").status_code == 404


def test_lead_detail_known_slug(client: TestClient) -> None:
    o = client.get("/api/poles/vente/overview").json()
    # Marc Dupont (CISO, acme-securite.fr) — éligible, persona marc.
    slug = next(lead["slug"] for lead in o["leads"] if lead["eligible"])
    r = client.get(f"/api/poles/vente/leads/{slug}")
    assert r.status_code == 200
    d = r.json()
    # Champs résumé (mêmes que LeadOut).
    assert d["slug"] == slug
    assert d["domain"] == "acme-securite.fr"
    assert d["eligible"] is True
    assert d["persona"] == "marc"
    # Champs structurés.
    assert d["persona_score"] > 0
    assert "ciso" in d["persona_signals"]
    assert d["bant"]["total"] == d["bant_total"]
    assert all(k in d["bant"] for k in ("budget", "authority", "need", "timing", "total"))
    # Guesses email triées par confidence décroissante, best_email = la 1re.
    assert d["email_guesses"]
    assert d["email_guesses"][0]["email"] == d["best_email"]
    # Pas de fiche enriched/<slug>.md écrite → corps vide.
    assert d["markdown_body"] == ""


def test_lead_detail_unknown_404(client: TestClient) -> None:
    assert client.get("/api/poles/vente/leads/ghost-slug-x").status_code == 404


def test_draft_body_roundtrip(client: TestClient) -> None:
    # Avant tout draft : exists=false, body vide.
    r = client.get("/api/poles/vente/inbox/lead1/draft")
    assert r.status_code == 200
    assert r.json() == {"id": "lead1", "body": "", "exists": False}

    # POST draft (squelette) puis GET → exists=true, body non vide.
    assert client.post("/api/poles/vente/inbox/lead1/draft").status_code == 200
    got = client.get("/api/poles/vente/inbox/lead1/draft").json()
    assert got["exists"] is True
    assert got["body"]

    # PUT un corps édité → renvoyé tel quel + relu identique.
    edited = "Bonjour Lead,\n\nVoici notre tarif Argos Pro.\n\nArgos — on scanne, vous corrigez.\n"
    put = client.put("/api/poles/vente/inbox/lead1/draft", json={"body": edited})
    assert put.status_code == 200
    assert put.json()["exists"] is True
    assert put.json()["body"] == edited.strip()
    back = client.get("/api/poles/vente/inbox/lead1/draft").json()
    assert back["body"] == edited.strip()


def test_draft_body_put_creates_without_post(client: TestClient) -> None:
    # PUT sans POST préalable doit créer le draft.
    edited = "Réponse rédigée à la main."
    put = client.put("/api/poles/vente/inbox/lead1/draft", json={"body": edited})
    assert put.status_code == 200
    assert put.json()["body"] == edited
    assert client.get("/api/poles/vente/inbox/lead1/draft").json()["body"] == edited


def test_draft_body_unknown_message_404(client: TestClient) -> None:
    assert client.get("/api/poles/vente/inbox/ghost/draft").status_code == 404
    r = client.put("/api/poles/vente/inbox/ghost/draft", json={"body": "x"})
    assert r.status_code == 404
