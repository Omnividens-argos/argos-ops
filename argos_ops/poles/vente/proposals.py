"""Devis & contrats du pôle Vente (archi v2, S4).

Charge ``data/poles/vente/proposals/<deal_id>/context.yaml``
(:class:`~argos_ops.sales.models.ProposalContext`, saisi par le fondateur) et
rend le Markdown via :func:`argos_ops.sales.templates.render_proposal` /
:func:`render_contract`.

Cycle de vie (suivi dans ``status.yaml`` du dossier) :

1. ``proposal_bot`` rend ``proposal.md`` (statut → ``drafted``) ;
2. le fondateur marque ``proposal_status: sent`` à la main ;
3. ``contract_generator`` ne rend ``contract.md`` que si le devis est ``sent``.

Idempotent : un livrable déjà présent n'est pas réécrit. PDF tenté via pandoc
(:func:`try_render_pdf`) si dispo — sinon Markdown seul (D-009).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente.store import parse_date
from argos_ops.sales.models import ProposalContext
from argos_ops.sales.templates import render_contract, render_proposal

VENTE_POLE = "vente"

PROPOSAL_FILE = "proposal.md"
CONTRACT_FILE = "contract.md"
CONTEXT_FILE = "context.yaml"
STATUS_FILE = "status.yaml"


@dataclass(frozen=True)
class ProposalEntry:
    """Vue cockpit d'un deal devis/contrat."""

    deal_id: str
    company: str
    plan: str
    monthly_price_eur: int
    proposal_status: str  # none | drafted | sent
    has_proposal: bool
    has_contract: bool


def proposals_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "proposals"


def _deal_dir(deal_id: str, *, poles_root: Path = POLES_DIR) -> Path:
    return proposals_dir(poles_root=poles_root) / deal_id


def load_context(deal_id: str, *, poles_root: Path = POLES_DIR) -> ProposalContext | None:
    """Charge le ``context.yaml`` d'un deal. ``None`` si absent."""
    path = _deal_dir(deal_id, poles_root=poles_root) / CONTEXT_FILE
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return None
    issue_raw = raw.get("issue_date")
    extras_raw = raw.get("extras") or {}
    return ProposalContext(
        deal_id=str(raw.get("deal_id", deal_id)),
        company=str(raw["company"]),
        contact_name=str(raw["contact_name"]),
        contact_email=str(raw["contact_email"]),
        siret=(str(raw["siret"]) if raw.get("siret") else None),
        plan=str(raw.get("plan", "Argos Pro")),
        monthly_price_eur=int(raw.get("monthly_price_eur", 350)),
        setup_fee_eur=int(raw.get("setup_fee_eur", 0)),
        discount_percent=int(raw.get("discount_percent", 0)),
        contract_duration_months=int(raw.get("contract_duration_months", 12)),
        issue_date=parse_date(issue_raw) if issue_raw else date.today(),
        validity_days=int(raw.get("validity_days", 30)),
        extras={str(k): str(v) for k, v in extras_raw.items()}
        if isinstance(extras_raw, dict)
        else {},
    )


def proposal_status(deal_id: str, *, poles_root: Path = POLES_DIR) -> str:
    """Statut du devis : ``none`` (pas de status.yaml) / ``drafted`` / ``sent``."""
    path = _deal_dir(deal_id, poles_root=poles_root) / STATUS_FILE
    if not path.exists():
        return "none"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return str(raw.get("proposal_status", "none")) if isinstance(raw, dict) else "none"


def _set_status(deal_id: str, status: str, *, poles_root: Path = POLES_DIR) -> None:
    path = _deal_dir(deal_id, poles_root=poles_root) / STATUS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"proposal_status": status}, sort_keys=False), encoding="utf-8")


def list_deal_ids(*, poles_root: Path = POLES_DIR) -> list[str]:
    """Slugs des deals ayant un dossier devis (présence d'un ``context.yaml``)."""
    d = proposals_dir(poles_root=poles_root)
    if not d.exists():
        return []
    return sorted(c.name for c in d.iterdir() if c.is_dir() and (c / CONTEXT_FILE).exists())


def load_entries(*, poles_root: Path = POLES_DIR) -> list[ProposalEntry]:
    """Vue cockpit de tous les deals devis/contrat."""
    out: list[ProposalEntry] = []
    for deal_id in list_deal_ids(poles_root=poles_root):
        ctx = load_context(deal_id, poles_root=poles_root)
        if ctx is None:
            continue
        deal_dir = _deal_dir(deal_id, poles_root=poles_root)
        out.append(
            ProposalEntry(
                deal_id=deal_id,
                company=ctx.company,
                plan=ctx.plan,
                monthly_price_eur=ctx.monthly_price_eur,
                proposal_status=proposal_status(deal_id, poles_root=poles_root),
                has_proposal=(deal_dir / PROPOSAL_FILE).exists(),
                has_contract=(deal_dir / CONTRACT_FILE).exists(),
            )
        )
    return out


def render_proposal_file(deal_id: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Rend ``proposal.md`` pour un deal (idempotent). ``None`` si pas de contexte.

    Pose le statut ``drafted`` si non encore positionné.
    """
    ctx = load_context(deal_id, poles_root=poles_root)
    if ctx is None:
        return None
    out = _deal_dir(deal_id, poles_root=poles_root) / PROPOSAL_FILE
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_proposal(ctx), encoding="utf-8")
    if proposal_status(deal_id, poles_root=poles_root) == "none":
        _set_status(deal_id, "drafted", poles_root=poles_root)
    return out


def render_contract_file(deal_id: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Rend ``contract.md`` — uniquement si le devis est marqué ``sent``.

    Renvoie ``None`` si pas de contexte ou si le devis n'est pas ``sent`` (le
    contrat ne se génère jamais avant l'acceptation du devis).
    """
    ctx = load_context(deal_id, poles_root=poles_root)
    if ctx is None or proposal_status(deal_id, poles_root=poles_root) != "sent":
        return None
    out = _deal_dir(deal_id, poles_root=poles_root) / CONTRACT_FILE
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_contract(ctx), encoding="utf-8")
    return out


__all__ = [
    "CONTRACT_FILE",
    "PROPOSAL_FILE",
    "ProposalEntry",
    "list_deal_ids",
    "load_context",
    "load_entries",
    "proposal_status",
    "proposals_dir",
    "render_contract_file",
    "render_proposal_file",
]
