"""ContractGenerator — Sales Legal (P22.H Sales Sprint 3).

Génère le contrat de prestation (CGV / MSA) Markdown + PDF à partir
du même ``context.yaml`` qu'un devis. Convention : on génère le
contrat **après** que le devis a été drafté + envoyé, donc on lit
``status.yaml`` pour détecter ``proposal_status: sent`` (positionné à
la main par le fondateur quand le devis a été validé par le client).

Sortie ::

    data/contracts/<deal_id>/contract.md
    data/contracts/<deal_id>/contract.pdf (si pandoc dispo)

On ne lit jamais le context.yaml dans ``data/contracts/`` (single
source of truth dans ``data/proposals/<deal_id>/context.yaml``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.agents.proposal_bot import DEFAULT_PROPOSALS_ROOT, _load_context
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.sales.templates import render_contract, try_render_pdf

DEFAULT_CONTRACTS_ROOT: Path = REPO_ROOT / "data" / "contracts"


@dataclass
class ContractStats:
    deals_seen: int = 0
    drafted: int = 0
    already_drafted: int = 0
    pdf_generated: int = 0
    waiting_on_proposal: int = 0
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"deals={self.deals_seen} drafted={self.drafted} "
            f"already={self.already_drafted} pdf_ok={self.pdf_generated} "
            f"waiting={self.waiting_on_proposal}"
        )


def _proposal_is_sent(proposal_dir: Path) -> bool:
    status_path = proposal_dir / "status.yaml"
    if not status_path.exists():
        return False
    raw = yaml.safe_load(status_path.read_text(encoding="utf-8")) or {}
    return raw.get("proposal_status") == "sent"


def _contract_already_drafted(contract_dir: Path) -> bool:
    return (contract_dir / "contract.md").exists()


def build_contract_embed(stats: ContractStats) -> Embed:
    color = YELLOW if stats.drafted > 0 else GREEN
    fields = [
        EmbedField(name="Deals scannés", value=str(stats.deals_seen), inline=True),
        EmbedField(name="Contrats draftés", value=str(stats.drafted), inline=True),
        EmbedField(name="Déjà draftés", value=str(stats.already_drafted), inline=True),
        EmbedField(name="PDF générés", value=str(stats.pdf_generated), inline=True),
        EmbedField(
            name="En attente (devis non envoyé)",
            value=str(stats.waiting_on_proposal),
            inline=True,
        ),
    ]
    if stats.drafts:
        preview = "\n".join(f"• {d}" for d in stats.drafts[:5])
        fields.append(EmbedField(name="Drafts", value=preview, inline=False))
    return Embed(
        title=f"ContractGenerator — {stats.drafted} contrats draftés",
        description=(
            "Inspecte `data/contracts/<deal_id>/contract.md` (ou .pdf)."
            if stats.drafted > 0
            else "Aucun nouveau contrat à drafter."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ContractGenerator",
    )


class ContractGenerator(BaseAgent):
    """Génère un contrat de prestation par deal (post-devis envoyé)."""

    name = "ContractGenerator"
    command = "/draft-contract"
    breaker_name = "ContractGenerator"
    ai_act_risk_class = "limited"

    def __init__(
        self,
        *,
        proposals_root: Path = DEFAULT_PROPOSALS_ROOT,
        contracts_root: Path = DEFAULT_CONTRACTS_ROOT,
    ) -> None:
        self._proposals_root = proposals_root
        self._contracts_root = contracts_root

    async def run(self) -> RunResult:
        settings = get_settings()
        if not self._proposals_root.exists():
            logger.info(f"ContractGenerator — pas de proposals dir ({self._proposals_root})")
            return RunResult(status="success", output_summary="silence (no proposals)")

        stats = ContractStats()
        for deal_dir in sorted(self._proposals_root.iterdir()):
            if not deal_dir.is_dir():
                continue
            context_path = deal_dir / "context.yaml"
            if not context_path.exists():
                continue
            stats.deals_seen += 1
            if not _proposal_is_sent(deal_dir):
                stats.waiting_on_proposal += 1
                continue

            try:
                context = _load_context(context_path)
            except Exception as exc:
                logger.error(f"ContractGenerator — context invalide {deal_dir.name} : {exc}")
                continue

            contract_dir = self._contracts_root / context.deal_id
            contract_dir.mkdir(parents=True, exist_ok=True)
            if _contract_already_drafted(contract_dir):
                stats.already_drafted += 1
                continue

            markdown = render_contract(context)
            md_path = contract_dir / "contract.md"
            md_path.write_text(markdown, encoding="utf-8")
            pdf_path = contract_dir / "contract.pdf"
            if try_render_pdf(md_path, pdf_path=pdf_path):
                stats.pdf_generated += 1
            (contract_dir / "status.yaml").write_text(
                yaml.safe_dump(
                    {
                        "contract_status": "drafted",
                        "drafted_at": datetime.now(UTC).isoformat(),
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            stats.drafted += 1
            stats.drafts.append(context.deal_id)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.deals_seen > 0:
            try:
                await send_embed(webhook, build_contract_embed(stats))
            except Exception as exc:
                logger.warning(f"ContractGenerator — notif Discord échouée : {exc}")

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return str(p)

        inputs = [
            IOItem(
                label="Deals (context.yaml devis envoyé)",
                kind="file",
                detail=f"{stats.waiting_on_proposal} en attente (devis non envoyé)",
                ref=_rel(self._proposals_root),
                count=stats.deals_seen,
            )
        ]
        outputs = [
            IOItem(
                label="Contrats CGV/MSA générés",
                kind="file",
                detail=(
                    f"{stats.pdf_generated} PDF · "
                    f"{stats.already_drafted} déjà drafté(s)"
                ),
                ref=_rel(self._contracts_root),
                count=stats.drafted,
            )
        ]
        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_CONTRACTS_ROOT",
    "ContractGenerator",
    "ContractStats",
    "build_contract_embed",
]
