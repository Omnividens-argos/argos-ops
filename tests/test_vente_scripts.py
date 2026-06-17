"""Tests d'intégration des scripts du pôle Vente (archi v2, S4) — run + mémoire."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.vente.scripts.bloctel_guard import BloctelGuardScript
from argos_ops.poles.vente.scripts.email_bot import EmailBotScript
from argos_ops.poles.vente.scripts.escalation_router import EscalationRouterScript
from argos_ops.poles.vente.scripts.health_score import HealthScoreScript
from argos_ops.poles.vente.scripts.lead_enricher import LeadEnricherScript
from argos_ops.poles.vente.scripts.prospect_miner import ProspectMinerScript


def _write(root: Path, rel: str, body: str) -> None:
    p = root / "vente" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


async def test_escalation_router_memory(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "support/tickets.yaml",
        "tickets:\n  - ticket_id: T1\n    customer_id: c\n    subject: prod down\n"
        "    body: incident urgent\n    opened_at: '2026-06-10'\n    plan: pro\n",
    )
    result = await run_script(EscalationRouterScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("vente", "escalation_router", poles_root=tmp_path)
    assert recs and recs[0].kind == "ticket" and recs[0].important is True
    assert "P0" in recs[0].tags


async def test_health_score_only_non_green(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "cs/customers.yaml",
        "customers:\n"
        "  - customer_id: red\n    name: R\n    contact_email: a@r.fr\n    contact_name: A\n"
        "    plan: starter\n    signup_date: '2026-02-01'\n    last_nps: 3\n    tickets_30d: 6\n"
        "    usage: {scans_this_month: 4, scans_quota: 50, last_login_days_ago: 40}\n"
        "  - customer_id: green\n    name: G\n    contact_email: b@g.fr\n    contact_name: B\n"
        "    plan: pro\n    signup_date: '2026-05-01'\n    last_nps: 9\n    tickets_30d: 0\n"
        "    usage: {scans_this_month: 142, scans_quota: 200, last_login_days_ago: 2}\n",
    )
    result = await run_script(HealthScoreScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("vente", "health_score", poles_root=tmp_path)
    # Seul le compte rouge est mémorisé (vert = bruit).
    assert len(recs) == 1 and "red" in recs[0].tags and recs[0].important is True


async def test_bloctel_guard_alert_on_match(tmp_path: Path) -> None:
    _write(tmp_path, "compliance/lead_phones.csv", "identifier,phone\nl,+33611223344\n")
    _write(tmp_path, "compliance/bloctel/bloctel_2026-06.txt", "+33611223344\n")
    result = await run_script(BloctelGuardScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("vente", "bloctel_guard", poles_root=tmp_path)
    assert recs[0].kind == "compliance_alert" and recs[0].important is True


async def test_lead_enricher_memory_and_files(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "outbound/inbox/leads.csv",
        "full_name,domain,title_hint,linkedin_url\nMarc Dupont,acme-securite.fr,CISO,\n",
    )
    result = await run_script(LeadEnricherScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("vente", "lead_enricher", poles_root=tmp_path)
    assert recs and recs[0].kind == "lead"
    assert (tmp_path / "vente" / "outbound" / "enriched").glob("*.md")


async def test_email_bot_classifies_and_skips_spam(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "inbox/messages.yaml",
        "messages:\n"
        "  - id: m1\n    from_email: a@b.fr\n    subject: Demande de devis\n    body: vos tarifs\n    received_at: '2026-06-17'\n"
        "  - id: m2\n    from_email: spam@x\n    subject: Gagnez du bitcoin\n    body: casino loterie\n    received_at: '2026-06-17'\n",
    )
    result = await run_script(EmailBotScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("vente", "email_bot", poles_root=tmp_path)
    # Le spam n'est pas mémorisé.
    assert len(recs) == 1 and "lead_chaud" in recs[0].tags


async def test_prospect_miner_appends(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "outbound/sources.yaml",
        "manual:\n  - full_name: Claire Moreau\n    domain: secure-corp.fr\n    title_hint: RSSI\n",
    )
    result = await run_script(ProspectMinerScript(poles_root=tmp_path))
    assert result.status == "success"
    csv = (tmp_path / "vente" / "outbound" / "inbox" / "leads.csv").read_text(encoding="utf-8")
    assert "Claire Moreau" in csv
