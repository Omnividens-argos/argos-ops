"""Tests d'intégration des scripts du pôle Finance (archi v2, S5) — run + mémoire."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.finance.scripts import (
    FINANCE_SCRIPTS,
    AIActComplianceScript,
    BurnRateMonitorScript,
    ContractDeadlineScript,
    ExpenseAuditorScript,
    FinanceBotScript,
    IncidentLoggerScript,
    RGPDAuditorScript,
    TaxBotScript,
    VendorContractWatcherScript,
)


def _w(root: Path, rel: str, body: str) -> None:
    p = root / "finance" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_eleven_scripts_registered() -> None:
    assert len(FINANCE_SCRIPTS) == 11
    assert {c.pole for c in FINANCE_SCRIPTS} == {"finance"}


async def test_finance_bot_mrr_and_dunning(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "billing/subscriptions.yaml",
        "subscriptions:\n  - id: s1\n    customer_id: c1\n    status: active\n    mrr_eur: 350\n",
    )
    _w(
        tmp_path,
        "billing/invoices.yaml",
        "invoices:\n  - id: in1\n    customer_id: c1\n    customer_name: A\n    status: open\n"
        "    amount_due_eur: 350\n    due_date: 2020-01-01\n",  # très en retard → J+15
    )
    result = await run_script(FinanceBotScript(poles_root=tmp_path))
    assert result.status == "success"
    recs = await memory.read_memory("finance", "finance_bot", poles_root=tmp_path)
    kinds = {r.kind for r in recs}
    assert "mrr" in kinds and "dunning" in kinds
    dunning = next(r for r in recs if r.kind == "dunning")
    assert "J+15" in dunning.tags and dunning.important is True


async def test_burn_rate_monitor_important_on_alert(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "treasury/state.yaml",
        "cash_balance_eur: 10000\nmonthly_burn_eur: 9000\nmonthly_revenue_eur: 1000\n",
    )
    await run_script(BurnRateMonitorScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "burn_rate_monitor", poles_root=tmp_path)
    assert recs and recs[0].kind == "treasury" and recs[0].important is True


async def test_burn_rate_monitor_skips_without_state(tmp_path: Path) -> None:
    result = await run_script(BurnRateMonitorScript(poles_root=tmp_path))
    assert result.status == "success" and result.written == []


async def test_tax_bot_writes_important_fiscal(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "billing/subscriptions.yaml",
        "subscriptions:\n  - id: s1\n    customer_id: c1\n    status: active\n    mrr_eur: 500\n",
    )
    await run_script(TaxBotScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "tax_bot", poles_root=tmp_path)
    assert recs and recs[0].kind == "fiscal" and recs[0].important is True
    # Le doc CA3 est généré.
    assert list((tmp_path / "finance" / "docs").glob("ca3_*.md"))


async def test_rgpd_auditor_gap_tag_and_important(tmp_path: Path) -> None:
    # Registre absent → gap → important + tag gap.
    await run_script(RGPDAuditorScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "rgpd_auditor", poles_root=tmp_path)
    assert recs and recs[0].kind == "rgpd" and recs[0].important is True
    assert "gap" in recs[0].tags


async def test_ai_act_prohibited_tag(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "compliance/ai_act_registry.yaml",
        "systemes:\n  - nom: Bad\n    risk_class: prohibited\n",
    )
    await run_script(AIActComplianceScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "ai_act_compliance", poles_root=tmp_path)
    assert recs and recs[0].kind == "ai_act" and "prohibited" in recs[0].tags


async def test_vendor_contract_only_non_ok(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "contracts/vendors.yaml",
        "contracts:\n  - vendor: OVH\n    renewal_date: 2026-09-01\n    notice_period_days: 60\n"
        "    monthly_cost_eur: 12\n  - vendor: Far\n    renewal_date: 2030-01-01\n"
        "    notice_period_days: 30\n    monthly_cost_eur: 5\n",
    )
    await run_script(VendorContractWatcherScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "vendor_contract_watcher", poles_root=tmp_path)
    # Seul OVH (urgent) est mémorisé ; Far (ok) est du bruit.
    assert len(recs) == 1 and recs[0].source == "OVH" and recs[0].important is True


async def test_contract_deadline_client(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "contracts/clients.yaml",
        "contracts:\n  - client: Acme\n    start: 2025-07-01\n    term_months: 12\n",
    )
    await run_script(ContractDeadlineScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "contract_deadline", poles_root=tmp_path)
    assert recs and recs[0].kind == "client_contract"


async def test_incident_logger_open_only(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "incidents/2026-06-15-x.md",
        "---\ntitle: X\ndate: 2026-06-15\ncategory: data_leak\nseverity: P1\nstatus: open\n---\n\nbody\n",
    )
    _w(
        tmp_path,
        "incidents/2026-05-01-y.md",
        "---\ntitle: Y\ndate: 2026-05-01\ncategory: other\nseverity: P3\nstatus: resolved\n---\n\nbody\n",
    )
    await run_script(IncidentLoggerScript(poles_root=tmp_path))
    recs = await memory.read_memory("finance", "incident_logger", poles_root=tmp_path)
    assert len(recs) == 1 and recs[0].important is True and "P1" in recs[0].tags


async def test_expense_auditor_updates_history(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "expenses/2026-06.csv",
        "Settlement date,Counterparty name,Total amount (EUR),Reference\n"
        "2026-06-02,NewVendor,-50.00,x\n2026-06-03,Other,-40.00,y\n",
    )
    await run_script(ExpenseAuditorScript(poles_root=tmp_path))
    # Le journal vendors est mis à jour (update_history=True dans le script).
    journal = (tmp_path / "finance" / "expenses" / "vendors.md").read_text(encoding="utf-8")
    assert "NewVendor" in journal and "Other" in journal
