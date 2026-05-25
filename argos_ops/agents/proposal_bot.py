"""ProposalBot — Sales Engineer (P22.H Sales Sprint 3).

Génère un devis Markdown + PDF (pandoc si dispo) à partir d'un
``ProposalContext`` rangé dans
``data/proposals/<deal_id>/context.yaml``. Le fondateur saisit le
context à la main (variables compte + plan + prix) ; ProposalBot rend
le devis et le marque ``status: drafted``.

Output :

- ``data/proposals/<deal_id>/proposal.md`` — toujours présent
- ``data/proposals/<deal_id>/proposal.pdf`` — si ``pandoc`` est sur le
  PATH (sinon le fondateur convertit à la main)

Le bot ne touche pas le ``context.yaml`` — il enregistre un fichier
``status.yaml`` séparé pour tracer l'idempotence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.sales.models import ProposalContext
from argos_ops.sales.templates import render_proposal, try_render_pdf

DEFAULT_PROPOSALS_ROOT: Path = REPO_ROOT / "data" / "proposals"


@dataclass
class ProposalStats:
    deals_seen: int = 0
    drafted: int = 0
    already_drafted: int = 0
    pdf_generated: int = 0
    pdf_skipped_no_pandoc: int = 0
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"deals={self.deals_seen} drafted={self.drafted} "
            f"already={self.already_drafted} pdf_ok={self.pdf_generated} "
            f"pdf_skipped={self.pdf_skipped_no_pandoc}"
        )


def _load_context(context_path: Path) -> ProposalContext:
    raw = yaml.safe_load(context_path.read_text(encoding="utf-8")) or {}
    issue = raw.get("issue_date")
    if isinstance(issue, str):
        issue_date = date.fromisoformat(issue)
    elif isinstance(issue, date):
        issue_date = issue
    else:
        issue_date = date.today()
    return ProposalContext(
        deal_id=raw["deal_id"],
        company=raw["company"],
        contact_name=raw["contact_name"],
        contact_email=raw["contact_email"],
        siret=raw.get("siret"),
        plan=raw.get("plan", "Argos Pro"),
        monthly_price_eur=int(raw.get("monthly_price_eur", 350)),
        setup_fee_eur=int(raw.get("setup_fee_eur", 0)),
        discount_percent=int(raw.get("discount_percent", 0)),
        contract_duration_months=int(raw.get("contract_duration_months", 12)),
        issue_date=issue_date,
        validity_days=int(raw.get("validity_days", 30)),
        extras=dict(raw.get("extras", {}) or {}),
    )


def _is_drafted(deal_dir: Path) -> bool:
    status_path = deal_dir / "status.yaml"
    if not status_path.exists():
        return False
    raw = yaml.safe_load(status_path.read_text(encoding="utf-8")) or {}
    return raw.get("proposal_status") in {"drafted", "sent"}


def _write_status(deal_dir: Path, *, pdf_ok: bool) -> None:
    payload = {
        "proposal_status": "drafted",
        "drafted_at": datetime.now(UTC).isoformat(),
        "pdf_generated": pdf_ok,
    }
    (deal_dir / "status.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def build_proposal_embed(stats: ProposalStats) -> Embed:
    color = YELLOW if stats.drafted > 0 else GREEN
    fields = [
        EmbedField(name="Deals scannés", value=str(stats.deals_seen), inline=True),
        EmbedField(name="Devis draftés", value=str(stats.drafted), inline=True),
        EmbedField(name="Déjà draftés", value=str(stats.already_drafted), inline=True),
        EmbedField(name="PDF générés", value=str(stats.pdf_generated), inline=True),
        EmbedField(
            name="PDF skip (pandoc absent)",
            value=str(stats.pdf_skipped_no_pandoc),
            inline=True,
        ),
    ]
    if stats.drafts:
        preview = "\n".join(f"• {d}" for d in stats.drafts[:5])
        fields.append(EmbedField(name="Drafts", value=preview, inline=False))
    return Embed(
        title=f"ProposalBot — {stats.drafted} devis draftés",
        description=(
            "Inspecte `data/proposals/<deal_id>/proposal.md` (ou .pdf)."
            if stats.drafted > 0
            else "Aucun nouveau devis à drafter."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ProposalBot",
    )


class ProposalBot(BaseAgent):
    """Génère un devis Markdown + PDF par deal."""

    name = "ProposalBot"
    command = "/draft-proposal"
    breaker_name = "ProposalBot"
    ai_act_risk_class = "limited"

    def __init__(self, *, proposals_root: Path = DEFAULT_PROPOSALS_ROOT) -> None:
        self._proposals_root = proposals_root

    async def run(self) -> RunResult:
        settings = get_settings()
        if not self._proposals_root.exists():
            logger.info(f"ProposalBot — pas de dossier {self._proposals_root}")
            return RunResult(status="success", output_summary="silence (no proposals dir)")

        stats = ProposalStats()
        for deal_dir in sorted(self._proposals_root.iterdir()):
            if not deal_dir.is_dir():
                continue
            context_path = deal_dir / "context.yaml"
            if not context_path.exists():
                continue
            stats.deals_seen += 1
            if _is_drafted(deal_dir):
                stats.already_drafted += 1
                continue
            try:
                context = _load_context(context_path)
            except Exception as exc:
                logger.error(f"ProposalBot — context.yaml invalide {deal_dir.name} : {exc}")
                continue
            markdown = render_proposal(context)
            md_path = deal_dir / "proposal.md"
            md_path.write_text(markdown, encoding="utf-8")
            pdf_path = deal_dir / "proposal.pdf"
            pdf_ok = try_render_pdf(md_path, pdf_path=pdf_path)
            if pdf_ok:
                stats.pdf_generated += 1
            else:
                stats.pdf_skipped_no_pandoc += 1
            _write_status(deal_dir, pdf_ok=pdf_ok)
            stats.drafted += 1
            stats.drafts.append(context.deal_id)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.deals_seen > 0:
            try:
                await send_embed(webhook, build_proposal_embed(stats))
            except Exception as exc:
                logger.warning(f"ProposalBot — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_PROPOSALS_ROOT",
    "ProposalBot",
    "ProposalStats",
    "build_proposal_embed",
]
