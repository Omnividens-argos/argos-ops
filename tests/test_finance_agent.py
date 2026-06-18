"""Tests du FinanceAgent (archi v2, S5) — plan borné par la conformité."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.finance.agent import FinanceAgent

# L'agent évalue la conformité avec date.today() (pas d'override) → revue ancrée
# à aujourd'hui pour que le test reste vert au fil du temps (cf. revue S5).
_TODAY = date.today().isoformat()


def _pole_yaml(root: Path) -> None:
    d = root / "finance"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: finance\nname: Finance\nagent:\n  name: FinanceAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [vente]\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


def _registries_ok(root: Path) -> None:
    c = root / "finance" / "compliance"
    c.mkdir(parents=True, exist_ok=True)
    (c / "rgpd_registry.yaml").write_text(
        "traitements:\n  - nom: Facturation\n    base_legale: contrat\n    finalite: x\n"
        f"    donnees: [email]\n    duree_conservation: 10 ans\n    review_date: {_TODAY}\n",
        encoding="utf-8",
    )
    (c / "ai_act_registry.yaml").write_text(
        "systemes:\n  - nom: FinanceAgent\n    risk_class: minimal\n", encoding="utf-8"
    )


async def test_agent_skipped_when_no_memory(tmp_path: Path) -> None:
    _pole_yaml(tmp_path)
    _registries_ok(tmp_path)
    result = await FinanceAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"


async def test_agent_plans_and_reads_cross_pole(tmp_path: Path) -> None:
    _pole_yaml(tmp_path)
    _registries_ok(tmp_path)
    # Fait propre (dunning) + fait cross-pôle Vente (devis envoyé).
    await memory.write_memory(
        "finance",
        "finance_bot",
        "Relance J+15 facture in1",
        kind="dunning",
        tags=("dunning", "J+15"),
        important=True,
        poles_root=tmp_path,
    )
    await memory.write_memory(
        "vente",
        "proposal_bot",
        "Devis DEAL-1 (Acme) sent",
        kind="proposal",
        tags=("DEAL-1", "sent"),
        poles_root=tmp_path,
    )
    result = await FinanceAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert "vente" in result.summary  # cross-pôle lu
    joined = " ".join(result.actions)
    assert "dunning" in joined and "billing_new" in joined
    assert "GELÉ" not in joined  # conformité OK


async def test_agent_freezes_billing_new_when_compliance_blocking(tmp_path: Path) -> None:
    _pole_yaml(tmp_path)
    # Pas de registres → conformité bloquante.
    await memory.write_memory(
        "vente",
        "proposal_bot",
        "Devis DEAL-1 sent",
        kind="proposal",
        tags=("DEAL-1", "sent"),
        poles_root=tmp_path,
    )
    result = await FinanceAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    billing_action = next(a for a in result.actions if "billing_new" in a)
    assert "GELÉ" in billing_action
    assert "GELÉ" in result.summary
