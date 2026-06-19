"""Tests de l'API cockpit du pôle Direction (archi v2, S6).

Hermétique : app minimale (router Direction seul) + ``POLES_DIR`` du module patché
vers ``tmp_path``, avec OKR du trimestre courant + journal de décisions + feedback +
bugs (dont un P0 XSS) + changelog + roadmap + board scaffoldés, **plus** un autre
pôle (``veille``) doté d'un fait mémoire critique cross-pôle (la flotte montre un
pôle rouge). Le garde-fou de publication est donc armé (bug P0 + pôle critique).

Strict miroir du style de ``tests/test_finance_api.py``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import direction
from argos_ops.poles.memory import write_memory

# OKR : l'API résout le fichier du trimestre courant via date.today() (pas
# d'override), donc on ancre le snapshot OKR au trimestre d'aujourd'hui — sinon
# le fichier serait introuvable (rapport vide) et casserait les assertions.
_TODAY = date.today()
_QUARTER = (_TODAY.month - 1) // 3 + 1
_OKR_FILE = f"{_TODAY.year}-Q{_QUARTER}.yaml"
_OKR_QUARTER = f"{_TODAY.year}-Q{_QUARTER}"

# Un objectif + KR existants du snapshot OKR (réutilisés par le test PUT).
_OBJECTIVE = "Atteindre 10 000 € de MRR en fin de Q2"
_KR_NAME = "MRR fin de trimestre"


def _w(root: Path, rel: str, body: str) -> None:
    p = root / "direction" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _seed_pole_yaml(root: Path) -> None:
    (root / "direction").mkdir(parents=True, exist_ok=True)
    (root / "direction" / "pole.yaml").write_text(
        "id: direction\n"
        "name: Direction\n"
        "description: Pilotage transversal de la flotte.\n"
        "agent:\n"
        "  name: DirectionAgent\n"
        "  trigger: cron\n"
        "  skills:\n"
        "    - release-notes\n"
        "    - weekly-synthesis\n"
        "    - okr-review\n"
        "    - board-pack\n"
        "    - decision-log\n"
        "    - changelog\n"
        "    - roadmap-publish\n"
        "    - feedback-arbitrage\n"
        "    - bug-triage\n"
        "scripts: []\n"
        'reads_cross_pole: ["*"]\n'
        "front_tools: [memory_table, alert_card]\n",
        encoding="utf-8",
    )


def _seed_okr(root: Path) -> None:
    _w(
        root,
        f"okr/{_OKR_FILE}",
        f"quarter: {_OKR_QUARTER}\n"
        f"year: {_TODAY.year}\n"
        f"quarter_num: {_QUARTER}\n"
        "objectives:\n"
        f"  - title: {_OBJECTIVE}\n"
        "    key_results:\n"
        f"      - name: {_KR_NAME}\n"
        "        target: 10000\n"
        "        actual: 4500\n"
        "        unit: EUR\n"
        "      - name: Nouveaux clients signés\n"
        "        target: 8\n"
        "        actual: 3\n"
        "        unit: clients\n",
    )


def _seed_decisions(root: Path) -> None:
    _w(
        root,
        "decisions/journal.md",
        "## D-001 — Architecture v2 pôle / agent / script\n"
        "**Date :** 2026-06-17\n"
        "**Partie :** S0\n"
        "**Décision :** Refondre Argos Ops en 8 pôles métier.\n"
        "**Pourquoi :** Découpler décision et exécution.\n"
        "\n"
        "---\n"
        "\n"
        "## D-002 — Direction = pôle transversal avec gel de publication\n"
        "**Date :** 2026-06-18\n"
        "**Partie :** S6\n"
        "**Décision :** Geler la publication tant qu'un bug P0 est ouvert.\n"
        "**Pourquoi :** Garde-fou homogène avec les autres pôles.\n",
    )


def _seed_feedback(root: Path) -> None:
    _w(
        root,
        "feedback/items.yaml",
        "items:\n"
        "  - source: email\n"
        "    customer_id: acme-sa\n"
        "    date: 2026-06-09\n"
        "    topic: Export PDF du rapport en français\n"
        '    verbatim: "Export FR du rapport demandé."\n'
        "  - source: support\n"
        "    customer_id: client-beta\n"
        "    date: 2026-06-11\n"
        "    topic: Export PDF du rapport en français\n"
        '    verbatim: "Le rapport est en anglais."\n'
        "  - source: discord\n"
        "    customer_id: delta-io\n"
        "    date: 2026-06-12\n"
        "    topic: Intégration Slack des alertes\n"
        '    verbatim: "Webhook Slack natif demandé."\n',
    )


def _seed_bugs_with_p0(root: Path) -> None:
    _w(
        root,
        "bugs/issues.yaml",
        "issues:\n"
        "  - number: 42\n"
        '    title: "Vulnérabilité XSS sur le rapport de scan partagé"\n'
        '    body: "Un rapport partagé rend du HTML non échappé. Risque XSS stocké."\n'
        '    labels: ["bug", "security"]\n'
        "    opened_at: 2026-06-16\n"
        "  - number: 43\n"
        '    title: "Crash du scanner sur les très gros domaines"\n'
        '    body: "Le scanner crash (timeout + OOM). Régression depuis la v0.5."\n'
        '    labels: ["bug"]\n'
        "    opened_at: 2026-06-14\n"
        "  - number: 44\n"
        '    title: "Améliorer le wording de la page pricing"\n'
        '    body: "La grille tarifaire prête à confusion."\n'
        '    labels: ["enhancement"]\n'
        "    opened_at: 2026-06-10\n",
    )


def _seed_changelog(root: Path) -> None:
    _w(
        root,
        "changelog/commits.yaml",
        "from_ref: v0.5.0\n"
        "to_ref: HEAD\n"
        "commits:\n"
        "  - sha: 836ef6e\n"
        '    subject: "feat(finance): pôle Finance complet"\n'
        "  - sha: aa11bb2\n"
        '    subject: "fix(finance): rapprochement bancaire corrigé"\n'
        "  - sha: ee55ff6\n"
        '    subject: "perf(veille): cache des snapshots (-40%)"\n',
    )


def _seed_roadmap(root: Path) -> None:
    _w(
        root,
        "roadmap/annexe_d.md",
        "# Annexe D — Avancement de la flotte\n"
        "\n"
        "### 1. Direction & Pilotage\n"
        "\n"
        "- [x] ✅ **DirectionAgent** · Chief of Staff · Synthèse hebdo. *S6 livré.*\n"
        "- [~] 🟡 **WeeklySynthesis** · Synthèse IA · Récit hebdo. *S6 partiel.*\n"
        "\n"
        "### 2. Acquisition & Contenu\n"
        "\n"
        "- [x] ✅ **MarketingAgent** · Growth · Contenu organique. *S2 livré.*\n"
        "- [ ] ⬜ **SEOPlanner** · SEO · Planification éditoriale SERP.\n",
    )


def _seed_board(root: Path) -> None:
    _w(
        root,
        "board/metrics.yaml",
        "mrr_eur: 4500\nburn_eur: 1800\nrunway_months: 5.8\nnrr_pct: 104.0\nincidents_month: 1\n",
    )


def _seed_cross_pole_red(root: Path) -> None:
    """Pôle ``veille`` minimal + un fait mémoire critique (flotte rouge)."""
    veille = root / "veille"
    veille.mkdir(parents=True, exist_ok=True)
    (veille / "pole.yaml").write_text(
        "id: veille\n"
        "name: Veille\n"
        "description: Veille concurrentielle et sécurité.\n"
        "agent:\n"
        "  name: VeilleAgent\n"
        "scripts: []\n"
        "reads_cross_pole: []\n"
        "front_tools: [memory_table]\n",
        encoding="utf-8",
    )
    # Fait critique : tag « critical » → fact_severity == critical → pôle rouge.
    asyncio.run(
        write_memory(
            "veille",
            "cve_monitor",
            "CVE critique HIGH détectée sur une stack client déclarée — escalade requise.",
            kind="cve",
            tags=("critical",),
            important=True,
            poles_root=root,
        )
    )


def _seed(root: Path) -> None:
    _seed_pole_yaml(root)
    _seed_okr(root)
    _seed_decisions(root)
    _seed_feedback(root)
    _seed_bugs_with_p0(root)
    _seed_changelog(root)
    _seed_roadmap(root)
    _seed_board(root)
    _seed_cross_pole_red(root)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(direction, "POLES_DIR", tmp_path)
    _seed(tmp_path)
    app = FastAPI()
    app.include_router(direction.router)
    with TestClient(app) as c:
        yield c


# =============================================================================
# Lecture
# =============================================================================
def test_overview(client: TestClient) -> None:
    r = client.get("/api/poles/direction/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["pole"] == "direction"

    # Flotte : au moins le pôle veille, en santé critique (fait critique seedé).
    fleet = o["fleet"]
    assert fleet["poles"], "la flotte doit lister au moins un pôle supervisé"
    veille = next((p for p in fleet["poles"] if p["pole"] == "veille"), None)
    assert veille is not None and veille["health"] == "critical"
    assert fleet["worst_health"] == "critical"
    assert fleet["poles_red"] >= 1

    # OKR du trimestre courant.
    assert o["okr"]["quarter"] == _OKR_QUARTER

    # Board pack (KPIs snapshot fichier).
    assert o["board"]["mrr_eur"] == 4500.0

    # Décisions présentes (journal local).
    assert len(o["decisions"]) >= 1

    # Changelog : compteurs par section conventional commit.
    assert o["changelog"]["section_counts"]

    # Roadmap : compteurs d'avancement.
    rm = o["roadmap"]
    assert rm["entries_total"] >= 1 and rm["done"] >= 1

    # Feedback : un thème récurrent (≥ 2 mentions) doit ressortir.
    assert any(t["count"] >= 2 for t in o["feedback"]["themes"])

    # Bugs : au moins un P0 (la vulnérabilité XSS).
    assert o["bugs"]["p0"] >= 1

    # Plan d'oversight non vide.
    assert len(o["plan"]) >= 1

    # Gel de publication armé (P0 + pôle rouge) avec une raison non vide.
    assert o["release_blocking"] is True
    assert o["release_reason"].strip()
    assert o["counts"]["release_blocking"] is True
    assert o["counts"]["bugs_p0"] >= 1
    assert o["counts"]["poles_red"] >= 1


def test_doc_not_found(client: TestClient) -> None:
    assert client.get("/api/poles/direction/docs/nope.md").status_code == 404


def test_doc_pdf_not_found(client: TestClient) -> None:
    # Aucun PDF rendu (pandoc absent en CI) ⇒ 404.
    assert client.get("/api/poles/direction/docs/board_2026-06.md/pdf").status_code == 404
    assert client.get("/api/poles/direction/docs/nope.pdf/pdf").status_code == 404


def test_doc_pdf_served(client: TestClient, tmp_path: Path) -> None:
    # Dépose un PDF factice dans le dossier docs ⇒ 200 + content-type PDF.
    docs_dir = tmp_path / "direction" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "board_2026-06.pdf").write_bytes(b"%PDF-1.4 fake")

    r = client.get("/api/poles/direction/docs/board_2026-06.pdf/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-1.4 fake"


# =============================================================================
# Génération de docs (garde-fou release)
# =============================================================================
def test_generate_board_allowed(client: TestClient) -> None:
    # Le board pack est INTERNE : jamais gelé, même garde-fou armé.
    r = client.post("/api/poles/direction/docs/generate", json={"kind": "board"})
    assert r.status_code == 200
    name = r.json()["name"]
    assert r.json()["kind"] == "board" and name.startswith("board_")
    # Le doc généré est relisable en preview.
    prev = client.get(f"/api/poles/direction/docs/{name}")
    assert prev.status_code == 200 and prev.json()["content"].strip()


def test_generate_public_artifact_gated(client: TestClient) -> None:
    # Garde-fou armé (P0 + pôle rouge) ⇒ tout artefact public est gelé en 409.
    for kind in ("changelog", "roadmap", "release_notes"):
        r = client.post("/api/poles/direction/docs/generate", json={"kind": kind})
        assert r.status_code == 409, kind
        assert "gel" in r.json()["detail"].lower() or "P0" in r.json()["detail"]


def test_generate_public_artifact_allowed_when_gate_disarmed(
    client: TestClient, tmp_path: Path
) -> None:
    # Désarme le gel : aucun bug P0 et aucun pôle critique.
    _w(
        tmp_path,
        "bugs/issues.yaml",
        "issues:\n"
        "  - number: 44\n"
        '    title: "Améliorer le wording de la page pricing"\n'
        '    body: "La grille tarifaire prête à confusion."\n'
        '    labels: ["enhancement"]\n'
        "    opened_at: 2026-06-10\n",
    )
    # Vide la mémoire critique du pôle veille (plus de pôle rouge).
    for md in (tmp_path / "veille" / "scripts" / "cve_monitor" / "memory").glob("*.md"):
        md.unlink()

    o = client.get("/api/poles/direction/overview").json()
    assert o["release_blocking"] is False

    r = client.post("/api/poles/direction/docs/generate", json={"kind": "changelog"})
    assert r.status_code == 200 and r.json()["name"] == "changelog.md"


def test_generate_unknown_kind(client: TestClient) -> None:
    r = client.post("/api/poles/direction/docs/generate", json={"kind": "wat"})
    assert r.status_code == 422


# =============================================================================
# Board export
# =============================================================================
def test_board_export(client: TestClient) -> None:
    r = client.post("/api/poles/direction/board/export")
    assert r.status_code == 200
    body = r.json()
    assert body["path"].startswith("board_") and body["path"].endswith(".md")
    assert body["markdown"].strip()


# =============================================================================
# Décisions
# =============================================================================
def test_add_decision(client: TestClient) -> None:
    payload = {
        "title": "Adopter le forecast multi-scénarios",
        "partie": "direction",
        "decision": "Brancher ForecastPro en S+.",
        "pourquoi": "Visibilité trésorerie 90j.",
    }
    r = client.post("/api/poles/direction/decisions", json=payload)
    assert r.status_code == 201
    did = r.json()["decision_id"]
    assert did and r.json()["title"] == payload["title"]

    # Idempotent par titre : un second POST identique renvoie le même ID.
    r2 = client.post("/api/poles/direction/decisions", json=payload)
    assert r2.status_code == 201 and r2.json()["decision_id"] == did

    # Titre / décision vides → 422.
    assert (
        client.post(
            "/api/poles/direction/decisions",
            json={"title": "   ", "decision": "x", "pourquoi": "y"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/poles/direction/decisions",
            json={"title": "T", "decision": "  ", "pourquoi": "y"},
        ).status_code
        == 422
    )
    # Champ requis manquant (pas de title) → 422 (validation Pydantic).
    assert (
        client.post(
            "/api/poles/direction/decisions",
            json={"decision": "x", "pourquoi": "y"},
        ).status_code
        == 422
    )


# =============================================================================
# OKR
# =============================================================================
def test_update_okr(client: TestClient) -> None:
    r = client.put(
        "/api/poles/direction/okr",
        json={"objective": _OBJECTIVE, "name": _KR_NAME, "actual": 9000},
    )
    assert r.status_code == 200
    o = r.json()
    assert o["quarter"] == _OKR_QUARTER
    kr = next((k for k in o["key_results"] if k["name"] == _KR_NAME), None)
    assert kr is not None and kr["actual"] == 9000.0

    # KR inconnu → 404.
    bad = client.put(
        "/api/poles/direction/okr",
        json={"objective": _OBJECTIVE, "name": "Inexistant", "actual": 1},
    )
    assert bad.status_code == 404


# =============================================================================
# Cycle de vie des décisions (sidecar open/closed)
# =============================================================================
def test_list_decisions_default_open(client: TestClient) -> None:
    r = client.get("/api/poles/direction/decisions")
    assert r.status_code == 200
    decs = r.json()
    assert len(decs) >= 2  # D-001 + D-002 seedées
    # Aucun sidecar ⇒ toutes les décisions sont « open » par défaut.
    assert all(d["status"] == "open" for d in decs)
    # Les champs de DecisionOut sont bien repris.
    d001 = next((d for d in decs if d["decision_id"] == "D-001"), None)
    assert d001 is not None
    assert d001["title"] and d001["decision"] and d001["partie"]


def test_patch_decision_to_closed_then_reflected(client: TestClient) -> None:
    r = client.patch("/api/poles/direction/decisions/D-001", json={"status": "closed"})
    assert r.status_code == 200
    assert r.json()["decision_id"] == "D-001"
    assert r.json()["status"] == "closed"

    # GET reflète le statut persisté ; les autres décisions restent open.
    decs = client.get("/api/poles/direction/decisions").json()
    by_id = {d["decision_id"]: d for d in decs}
    assert by_id["D-001"]["status"] == "closed"
    assert by_id["D-002"]["status"] == "open"

    # Idempotent + réouverture possible.
    r2 = client.patch("/api/poles/direction/decisions/D-001", json={"status": "open"})
    assert r2.status_code == 200 and r2.json()["status"] == "open"
    decs2 = client.get("/api/poles/direction/decisions").json()
    assert {d["decision_id"]: d for d in decs2}["D-001"]["status"] == "open"


def test_patch_decision_unknown_id_404(client: TestClient) -> None:
    r = client.patch("/api/poles/direction/decisions/D-999", json={"status": "closed"})
    assert r.status_code == 404


def test_patch_decision_bad_status_422(client: TestClient) -> None:
    r = client.patch("/api/poles/direction/decisions/D-001", json={"status": "archived"})
    assert r.status_code == 422
