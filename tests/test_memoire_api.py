"""Tests de l'API cockpit du pôle Mémoire (archi v2, S7).

Hermétique : app minimale (router Mémoire seul) + ``POLES_DIR`` du module patché
vers ``tmp_path``. Faits périmés seedés avec un ``created_at`` lointain (toujours
> TTL quel que soit le jour de run) ; la protection ``important`` ne dépend pas de
l'âge. Strict miroir du style de ``tests/test_direction_api.py``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import memoire
from argos_ops.poles.memory import MemoryRecord, write_memory

# Très loin dans le passé ⇒ toujours périmé (âge ≫ TTL 180 j), indépendant du jour.
_OLD = datetime(2020, 1, 1, tzinfo=UTC)


def _pole(root: Path, pid: str, *, agent: str | None, reads: list[str], trigger: str = "") -> None:
    (root / pid).mkdir(parents=True, exist_ok=True)
    reads_yaml = "[" + ", ".join(f'"{r}"' for r in reads) + "]"
    if agent is None:
        agent_block = "agent: null\n"
    else:
        trig = f"  trigger: {trigger}\n" if trigger else ""
        agent_block = f"agent:\n  name: {agent}\n{trig}"
    (root / pid / "pole.yaml").write_text(
        f"id: {pid}\nname: {pid}\n{agent_block}scripts: []\n"
        f"reads_cross_pole: {reads_yaml}\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


def _seed(root: Path) -> None:
    _pole(root, "veille", agent="VeilleAgent", reads=[])
    _pole(root, "finance", agent="FinanceAgent", reads=[])
    _pole(root, "pub", agent="PubAgent", reads=[])
    _pole(root, "memoire", agent="MemoireAgent", reads=["*"], trigger="script")
    (root / "memoire" / "policy.yaml").write_text(
        "protect_important: true\nactive_for: [veille, finance]\n"
        "default_ttl_days: 180\nkeep_recent_per_kind: 5\nmin_stale_days: 30\n",
        encoding="utf-8",
    )

    async def _facts() -> None:
        # veille : 1 important (protégé), 1 périmé (candidat), 1 frais (gardé).
        await write_memory(
            "veille",
            "cve",
            "CVE critique à conserver",
            important=True,
            created_at=_OLD,
            tags=("critical",),
            poles_root=root,
        )
        await write_memory("veille", "cve", "vieux signal périmé", created_at=_OLD, poles_root=root)
        await write_memory("veille", "trend", "signal frais du jour", poles_root=root)

    asyncio.run(_facts())


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(memoire, "POLES_DIR", tmp_path)
    _seed(tmp_path)
    app = FastAPI()
    app.include_router(memoire.router)
    with TestClient(app) as c:
        yield c


def _important_id(client: TestClient) -> str:
    r = client.get("/api/poles/memoire/browse", params={"pole": "veille", "important": "true"})
    return r.json()["records"][0]["id"]


def _expired_id(client: TestClient) -> str:
    plan = client.get("/api/poles/memoire/plan", params={"pole": "veille"}).json()
    return next(c["record_id"] for c in plan["to_delete"] if c["reason"] == "expired")


# =============================================================================
# Lecture
# =============================================================================
def test_overview(client: TestClient) -> None:
    o = client.get("/api/poles/memoire/overview").json()
    assert o["pole"] == "memoire"
    # Policy.
    assert set(o["policy"]["active_for"]) == {"veille", "finance"}
    assert o["policy"]["protect_important"] is True
    # Stats par pôle : veille a 3 faits dont 1 important, 1 candidat.
    veille = next(p for p in o["poles"] if p["pole"] == "veille")
    assert veille["active"] is True
    assert veille["n_facts"] == 3
    assert veille["n_important"] == 1
    assert veille["n_candidates"] == 1
    # Compteurs globaux + audit câblage + historique vide.
    assert o["counts"]["facts_total"] >= 3
    assert o["counts"]["important_total"] >= 1
    assert "summary" in o["wiring"]
    assert o["history"] == []


def test_browse_filters(client: TestClient) -> None:
    # Filtre pôle.
    r = client.get("/api/poles/memoire/browse", params={"pole": "veille"})
    assert r.json()["total"] == 3
    # Filtre important.
    imp = client.get("/api/poles/memoire/browse", params={"pole": "veille", "important": "true"})
    assert imp.json()["total"] == 1
    assert imp.json()["records"][0]["important"] is True
    # Recherche texte.
    q = client.get("/api/poles/memoire/browse", params={"pole": "veille", "q": "frais"})
    assert q.json()["total"] == 1
    # Filtre script.
    sc = client.get("/api/poles/memoire/browse", params={"pole": "veille", "script": "trend"})
    assert sc.json()["total"] == 1


def test_plan_separates_delete_and_protected(client: TestClient) -> None:
    plan = client.get("/api/poles/memoire/plan", params={"pole": "veille"}).json()
    assert plan["active"] is True
    delete_ids = {c["record_id"] for c in plan["to_delete"]}
    protected = {p["record_id"]: p for p in plan["protected"]}
    imp = _important_id(client)
    # L'important est protégé, JAMAIS dans to_delete.
    assert imp in protected
    assert imp not in delete_ids
    assert protected[imp]["reason"] == "important"
    assert protected[imp]["would_delete"] is True


def test_plan_inactive_pole(client: TestClient) -> None:
    # pub n'est pas dans active_for.
    plan = client.get("/api/poles/memoire/plan", params={"pole": "pub"}).json()
    assert plan["active"] is False
    assert plan["to_delete"] == []


def test_fact_detail_returns_full_body(client: TestClient, tmp_path: Path) -> None:
    """GET /fact renvoie le corps INTÉGRAL (jamais tronqué) d'un fait précis."""
    # Corps long (> tout body_preview) pour prouver l'absence de troncature.
    long_body = "Détail complet du fait. " + "Ligne réutilisable. " * 40
    rec: MemoryRecord = asyncio.run(
        write_memory(
            "finance",
            "mrr",
            long_body,
            kind="metric",
            tags=("kpi", "mrr"),
            source="stripe",
            poles_root=tmp_path,
        )
    )
    r = client.get(
        "/api/poles/memoire/fact",
        params={"pole": "finance", "script": "mrr", "record_id": rec.id},
    )
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == rec.id
    assert detail["pole"] == "finance"
    assert detail["script"] == "mrr"
    assert detail["kind"] == "metric"
    assert detail["source"] == "stripe"
    assert detail["tags"] == ["kpi", "mrr"]
    assert detail["important"] is False
    # Corps complet : exactement le body normalisé, pas une preview tronquée.
    assert detail["body"] == long_body.strip()
    assert len(detail["body"]) > 200


def test_fact_detail_unknown_record_404(client: TestClient) -> None:
    r = client.get(
        "/api/poles/memoire/fact",
        params={"pole": "veille", "script": "cve", "record_id": "deadbeef0000"},
    )
    assert r.status_code == 404


def test_fact_detail_unknown_pole_404(client: TestClient) -> None:
    r = client.get(
        "/api/poles/memoire/fact",
        params={"pole": "nope", "script": "cve", "record_id": "deadbeef0000"},
    )
    assert r.status_code == 404


# =============================================================================
# Mutations
# =============================================================================
def test_clean_deletes_validated_expired(client: TestClient) -> None:
    exp = _expired_id(client)
    r = client.post(
        "/api/poles/memoire/clean",
        json={"pole": "veille", "targets": [{"script": "cve", "record_id": exp}]},
    )
    assert r.status_code == 200
    assert r.json()["n_deleted"] == 1
    # Re-plan : le candidat a disparu.
    plan = client.get("/api/poles/memoire/plan", params={"pole": "veille"}).json()
    assert exp not in {c["record_id"] for c in plan["to_delete"]}


def test_clean_refuses_important_invariant(client: TestClient) -> None:
    """INVARIANT API : demander la suppression d'un fait important ⇒ refusé, fait intact."""
    imp = _important_id(client)
    r = client.post(
        "/api/poles/memoire/clean",
        json={"pole": "veille", "targets": [{"script": "cve", "record_id": imp}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["n_deleted"] == 0
    assert any("important" in x["reason"] for x in body["refused"])
    # Toujours présent.
    still = client.get("/api/poles/memoire/browse", params={"pole": "veille", "important": "true"})
    assert imp in {rec["id"] for rec in still.json()["records"]}


def test_flag_toggle_protects_then_unprotects(client: TestClient) -> None:
    # Le fait frais (kept) → on le protège manuellement.
    fresh = client.get("/api/poles/memoire/browse", params={"pole": "veille", "q": "frais"}).json()[
        "records"
    ][0]
    on = client.post(
        "/api/poles/memoire/flag",
        json={
            "pole": "veille",
            "script": fresh["script"],
            "record_id": fresh["id"],
            "important": True,
        },
    )
    assert on.status_code == 200 and on.json()["important"] is True
    # Maintenant 2 importants.
    imp = client.get("/api/poles/memoire/browse", params={"pole": "veille", "important": "true"})
    assert imp.json()["total"] == 2
    # On le dé-protège.
    off = client.post(
        "/api/poles/memoire/flag",
        json={
            "pole": "veille",
            "script": fresh["script"],
            "record_id": fresh["id"],
            "important": False,
        },
    )
    assert off.json()["important"] is False


def test_flag_missing_fact_404(client: TestClient) -> None:
    r = client.post(
        "/api/poles/memoire/flag",
        json={"pole": "veille", "script": "cve", "record_id": "deadbeef0000", "important": True},
    )
    assert r.status_code == 404


def test_policy_update_activation(client: TestClient) -> None:
    r = client.put("/api/poles/memoire/policy", json={"pole": "pub", "active": True})
    assert r.status_code == 200
    assert "pub" in r.json()["active_for"]
    # Persisté : pub devient actif dans l'overview.
    o = client.get("/api/poles/memoire/overview").json()
    pub = next(p for p in o["poles"] if p["pole"] == "pub")
    assert pub["active"] is True


def test_history_after_clean(client: TestClient) -> None:
    exp = _expired_id(client)
    client.post(
        "/api/poles/memoire/clean",
        json={"pole": "veille", "targets": [{"script": "cve", "record_id": exp}]},
    )
    h = client.get("/api/poles/memoire/history").json()
    assert len(h) == 1
    assert h[0]["pole"] == "veille"
    assert h[0]["n_deleted"] == 1


def test_wiring_endpoint(client: TestClient) -> None:
    w = client.get("/api/poles/memoire/wiring").json()
    assert "edges" in w and "anomalies" in w
    # memoire lit veille en wildcard.
    assert any(e["source"] == "memoire" and e["target"] == "veille" for e in w["edges"])


# =============================================================================
# 404
# =============================================================================
def test_unknown_pole_404(client: TestClient) -> None:
    assert client.get("/api/poles/memoire/plan", params={"pole": "nope"}).status_code == 404
    assert (
        client.put("/api/poles/memoire/policy", json={"pole": "nope", "active": True}).status_code
        == 404
    )
    assert (
        client.post("/api/poles/memoire/clean", json={"pole": "nope", "targets": []}).status_code
        == 404
    )
