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


def test_draft_proposal(client: TestClient) -> None:
    r = client.post("/api/poles/vente/proposals/D1/draft")
    assert r.status_code == 200
    assert r.json()["proposal_status"] == "drafted"


def test_unknown_404(client: TestClient) -> None:
    assert client.post("/api/poles/vente/proposals/ghost/draft").status_code == 404
    assert client.post("/api/poles/vente/meetings/ghost/book").status_code == 404
