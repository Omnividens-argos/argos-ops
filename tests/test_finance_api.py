"""Tests de l'API cockpit du pôle Finance (archi v2, S5).

Hermétique : app minimale (router Finance seul) + ``POLES_DIR`` du module patché
vers ``tmp_path``, avec billing / treasury / registres / contexte devis scaffoldés.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import finance

# review_date dynamique : l'API évalue la conformité avec date.today() (pas
# d'override), donc une date figée deviendrait « périmée » (> 365j) et flipperait
# le gel — cf. revue adversariale S5. On ancre la revue à aujourd'hui.
_TODAY = date.today().isoformat()


def _w(root: Path, rel: str, body: str) -> None:
    p = root / "finance" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _seed(root: Path) -> None:
    (root / "finance").mkdir(parents=True, exist_ok=True)
    (root / "finance" / "pole.yaml").write_text(
        "id: finance\nname: Finance\nagent:\n  name: FinanceAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [vente]\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )
    _w(
        root,
        "billing/subscriptions.yaml",
        "subscriptions:\n  - id: s1\n    customer_id: c1\n    customer_name: A\n    status: active\n"
        "    mrr_eur: 350\n    current_period_end: 2026-07-05\n",
    )
    _w(
        root,
        "billing/invoices.yaml",
        "invoices:\n  - id: in1\n    customer_id: c1\n    customer_name: A\n    status: open\n"
        "    amount_due_eur: 350\n    due_date: 2020-01-01\n",  # J+15
    )
    _w(
        root,
        "treasury/state.yaml",
        "cash_balance_eur: 48000\nmonthly_burn_eur: 9500\nmonthly_revenue_eur: 1200\nburn_cap_eur: 12000\n",
    )
    _w(
        root,
        "compliance/rgpd_registry.yaml",
        "traitements:\n  - nom: Facturation\n    base_legale: contrat\n    finalite: facturation\n"
        f"    donnees: [email]\n    duree_conservation: 10 ans\n    review_date: {_TODAY}\n",
    )
    _w(
        root,
        "compliance/ai_act_registry.yaml",
        "systemes:\n  - nom: FinanceAgent\n    risk_class: minimal\n",
    )
    _w(
        root,
        "docs/contexts/acme.yaml",
        "deal_id: acme\ncompany: Acme\ncontact_name: Marc\ncontact_email: m@acme.fr\n"
        "plan: Argos Pro\nmonthly_price_eur: 350\nissue_date: 2026-06-18\n",
    )
    _w(
        root,
        "ledger/flows.yaml",
        "flows:\n  - date: 2026-06-01\n    label: Vente\n    category: revenue\n    direction: in\n"
        "    amount_eur: 700\n",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(finance, "POLES_DIR", tmp_path)
    _seed(tmp_path)
    app = FastAPI()
    app.include_router(finance.router)
    with TestClient(app) as c:
        yield c


def test_overview(client: TestClient) -> None:
    r = client.get("/api/poles/finance/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["pole"] == "finance"
    assert o["billing"]["mrr_eur"] == 350.0
    assert o["billing"]["dunning"][0]["level"] == "J+15"
    assert o["treasury"]["severity"] == "alert"
    assert o["compliance_blocking"] is False
    assert o["counts"]["incidents_open"] == 0
    assert o["contracts"]["vendors"] == [] and o["contracts"]["clients"] == []
    assert len(o["fiscal"]) >= 1  # échéancier fiscal toujours peuplé
    assert len(o["ledger"]["flows"]) == 1
    assert o["forecast"]["expected_30d_eur"] == 350.0


def test_add_and_delete_flow(client: TestClient) -> None:
    r = client.post(
        "/api/poles/finance/ledger/flows",
        json={
            "flow_date": "2026-06-10",
            "label": "Pub",
            "category": "marketing",
            "direction": "out",
            "amount_eur": 200,
        },
    )
    assert r.status_code == 201
    fid = r.json()["id"]
    assert r.json()["direction"] == "out"
    d = client.request("DELETE", f"/api/poles/finance/ledger/flows/{fid}")
    assert d.status_code == 200 and d.json()["deleted"] is True
    assert client.request("DELETE", "/api/poles/finance/ledger/flows/ghost").status_code == 404


def test_edit_flow(client: TestClient) -> None:
    # Ajoute une ligne puis l'édite en place (tableur éditable).
    add = client.post(
        "/api/poles/finance/ledger/flows",
        json={
            "flow_date": "2026-06-10",
            "label": "Pub",
            "category": "marketing",
            "direction": "out",
            "amount_eur": 200,
        },
    )
    assert add.status_code == 201
    fid = add.json()["id"]
    edit = client.put(
        f"/api/poles/finance/ledger/flows/{fid}",
        json={
            "flow_date": "2026-06-10",
            "label": "Pub LinkedIn",
            "category": "marketing",
            "direction": "out",
            "amount_eur": 250,
        },
    )
    assert edit.status_code == 200
    assert edit.json()["id"] == fid  # id stable après édition
    assert edit.json()["label"] == "Pub LinkedIn"
    assert edit.json()["amount_eur"] == 250.0
    # La modif est visible dans overview (recalcul à chaud).
    flows = client.get("/api/poles/finance/overview").json()["ledger"]["flows"]
    edited = next(f for f in flows if f["id"] == fid)
    assert edited["label"] == "Pub LinkedIn" and edited["amount_eur"] == 250.0


def test_edit_flow_unknown_404(client: TestClient) -> None:
    r = client.put(
        "/api/poles/finance/ledger/flows/ghost",
        json={
            "flow_date": "2026-06-10",
            "label": "x",
            "direction": "in",
            "amount_eur": 10,
        },
    )
    assert r.status_code == 404


def test_edit_flow_rejects_bad_amount(client: TestClient) -> None:
    # Crée une ligne valide puis tente de l'éditer avec un montant non positif.
    add = client.post(
        "/api/poles/finance/ledger/flows",
        json={"flow_date": "2026-06-10", "label": "Pub", "direction": "out", "amount_eur": 200},
    )
    fid = add.json()["id"]
    r = client.put(
        f"/api/poles/finance/ledger/flows/{fid}",
        json={"flow_date": "2026-06-10", "label": "Pub", "direction": "out", "amount_eur": -5},
    )
    assert r.status_code == 422


def test_doc_pdf_404_when_absent(client: TestClient) -> None:
    # Génère une CA3 (markdown) ; sans pandoc le PDF n'existe pas → 404.
    client.post("/api/poles/finance/docs/generate", json={"kind": "ca3"})
    docs = client.get("/api/poles/finance/overview").json()["docs"]
    name = next(d["name"] for d in docs if d["kind"] == "ca3")
    if any(d["has_pdf"] for d in docs if d["name"] == name):
        pytest.skip("pandoc présent : PDF rendu, le cas 404 ne s'applique pas")
    r = client.get(f"/api/poles/finance/docs/{name.replace('.md', '.pdf')}")
    assert r.status_code == 404
    # Doc totalement inconnu → 404 aussi.
    assert client.get("/api/poles/finance/docs/ghost.pdf").status_code == 404


def test_upload_doc_file_multipart_and_versioning(client: TestClient) -> None:
    pdf = b"%PDF-1.4 fake binary content"
    r = client.post(
        "/api/poles/finance/docs/upload/file",
        files={"file": ("brief.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "brief.pdf"
    assert body["kind"] == "upload"
    assert body["has_pdf"] is True
    uploads = client.get("/api/poles/finance/overview").json()["uploads"]
    assert "brief.pdf" in uploads
    # Re-upload du même nom → versionné -v2 (pas d'écrasement).
    r2 = client.post(
        "/api/poles/finance/docs/upload/file",
        files={"file": ("brief.pdf", pdf, "application/pdf")},
    )
    assert r2.status_code == 201
    assert r2.json()["name"] == "brief-v2.pdf"


def test_add_flow_rejects_negative(client: TestClient) -> None:
    r = client.post(
        "/api/poles/finance/ledger/flows",
        json={"flow_date": "2026-06-10", "label": "x", "direction": "in", "amount_eur": -5},
    )
    assert r.status_code == 422


def test_add_flow_rejects_non_finite(client: TestClient) -> None:
    # inf / NaN doivent être rejetés en 422 à la validation (pas un 500 plus loin).
    for bad in ("Infinity", "NaN"):
        r = client.post(
            "/api/poles/finance/ledger/flows",
            content=(
                '{"flow_date": "2026-06-10", "label": "x", "direction": "in", "amount_eur": '
                + bad
                + "}"
            ),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422, bad


def test_generate_ca3(client: TestClient) -> None:
    r = client.post("/api/poles/finance/docs/generate", json={"kind": "ca3"})
    assert r.status_code == 200
    assert r.json()["kind"] == "ca3" and r.json()["name"].startswith("ca3_")


def test_generate_proposal_ok_when_compliant(client: TestClient) -> None:
    r = client.post(
        "/api/poles/finance/docs/generate", json={"kind": "proposal", "deal_id": "acme"}
    )
    assert r.status_code == 200 and r.json()["name"] == "devis_acme.md"


def test_generate_proposal_blocked_by_compliance(client: TestClient, tmp_path: Path) -> None:
    # Casse la conformité : registre RGPD avec un gap → onboarding gelé.
    _w(
        tmp_path,
        "compliance/rgpd_registry.yaml",
        "traitements:\n  - nom: Sans base\n    finalite: x\n    donnees: [email]\n"
        "    duree_conservation: 1 an\n    review_date: 2026-06-01\n",
    )
    assert client.get("/api/poles/finance/overview").json()["compliance_blocking"] is True
    r = client.post(
        "/api/poles/finance/docs/generate", json={"kind": "proposal", "deal_id": "acme"}
    )
    assert r.status_code == 409
    assert "gel" in r.json()["detail"].lower() or "conformit" in r.json()["detail"].lower()


def test_generate_proposal_unknown_context_404(client: TestClient) -> None:
    r = client.post(
        "/api/poles/finance/docs/generate", json={"kind": "proposal", "deal_id": "ghost"}
    )
    assert r.status_code == 404


def test_draft_dunning(client: TestClient) -> None:
    r = client.post("/api/poles/finance/invoices/in1/dunning")
    assert r.status_code == 200 and r.json()["status"] == "drafted"
    assert client.post("/api/poles/finance/invoices/ghost/dunning").status_code == 404


def test_export_accounting(client: TestClient) -> None:
    r = client.post("/api/poles/finance/export/accounting")
    assert r.status_code == 200
    assert "solde_eur" in r.json()["csv"] and "Vente" in r.json()["csv"]


def test_upload_listed_in_overview(client: TestClient) -> None:
    up = client.post(
        "/api/poles/finance/docs/upload", json={"filename": "note.md", "content": "à remplir"}
    )
    assert up.status_code == 201
    # L'uploadé est surfacé dans overview.uploads (pas une impasse UX).
    assert "note.md" in client.get("/api/poles/finance/overview").json()["uploads"]
    # …mais read_doc reste restreint au top-level docs/ (pas de lecture de uploads/).
    assert client.get("/api/poles/finance/docs/note.md").status_code == 404


def test_doc_preview_top_level_only(client: TestClient) -> None:
    # Génère une CA3 puis la prévisualise (doc top-level).
    client.post("/api/poles/finance/docs/generate", json={"kind": "ca3"})
    docs = client.get("/api/poles/finance/overview").json()["docs"]
    name = next(d["name"] for d in docs if d["kind"] == "ca3")
    prev = client.get(f"/api/poles/finance/docs/{name}")
    assert prev.status_code == 200 and "CA3" in prev.json()["content"]
    assert client.get("/api/poles/finance/docs/ghost.md").status_code == 404
