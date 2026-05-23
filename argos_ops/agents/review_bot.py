"""ReviewBot — Customer Advocacy (P22.G CS Sprint 7).

Sollicite les avis G2 / Capterra J+30 post-onboarding pour les comptes
**promoteurs** uniquement (NPS ≥ 9). Drafte un mail par client éligible
dans ``data/reviews/drafts/<id>.md``.

Filtres :
- ``onboarding_done_at`` < J-30 (au moins 1 mois d'expérience)
- ``last_review_at`` est null (pas déjà sollicité)
- ``last_nps >= 9`` (uniquement les promoteurs, évite les détracteurs)

Humain valide + envoie via ``zimbra-ops``. Idempotent (un draft existant
n'est pas recréé). Audit ``claude-judge`` recommandé pour vérifier
qu'on n'est pas insistant ou inadéquat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import Customer
from argos_ops.cs.scoring import NPS_PROMOTER_MIN
from argos_ops.cs.templates import render_review_email
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_DRAFTS_DIR: Path = REPO_ROOT / "data" / "reviews" / "drafts"

REVIEW_REQUEST_DELAY_DAYS = 30


@dataclass
class ReviewStats:
    customers_seen: int = 0
    drafts_created: int = 0
    drafts_skipped: int = 0
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"customers={self.customers_seen} drafted={self.drafts_created} "
            f"skipped={self.drafts_skipped}"
        )


def _first_name(contact_name: str, fallback_email: str) -> str:
    if contact_name and contact_name.strip():
        return contact_name.strip().split()[0]
    local = fallback_email.split("@", 1)[0]
    return local.split(".")[0].capitalize() if "." in local else local.capitalize()


def is_review_eligible(customer: Customer, *, today: date) -> bool:
    """Le compte est-il éligible à une demande d'avis ?

    Promoteur (NPS ≥ 9) + onboarding done depuis ≥ 30j + jamais sollicité.
    """
    if customer.last_review_at is not None:
        return False
    if customer.last_nps is None or customer.last_nps < NPS_PROMOTER_MIN:
        return False
    if customer.onboarding_done_at is None:
        return False
    return (today - customer.onboarding_done_at).days >= REVIEW_REQUEST_DELAY_DAYS


def _draft_review_request(customer: Customer, drafts_dir: Path) -> Path:
    drafts_dir.mkdir(parents=True, exist_ok=True)
    subject, body = render_review_email(
        contact_first_name=_first_name(customer.contact_name, customer.contact_email),
        company=customer.name,
    )
    front = {
        "customer_id": customer.customer_id,
        "to": customer.contact_email,
        "subject": subject,
        "nps_at_request": customer.last_nps,
        "status": "drafted",
    }
    draft_path = drafts_dir / f"{customer.customer_id}.md"
    draft_path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}\n",
        encoding="utf-8",
    )
    return draft_path


def build_review_embed(stats: ReviewStats) -> Embed:
    color = YELLOW if stats.drafts_created > 0 else GREEN
    fields = [
        EmbedField(name="Clients vus", value=str(stats.customers_seen), inline=True),
        EmbedField(name="Drafts créés", value=str(stats.drafts_created), inline=True),
        EmbedField(name="Skippés", value=str(stats.drafts_skipped), inline=True),
    ]
    if stats.drafts:
        preview = "\n".join(f"• {name}" for name in stats.drafts[:6])
        fields.append(EmbedField(name="Drafts", value=preview, inline=False))
    return Embed(
        title=f"ReviewBot — {stats.drafts_created} demande(s) d'avis draftée(s)",
        description=(
            "Cible promoteurs uniquement (NPS ≥ 9, onboarding ≥ J+30). "
            "Audit `claude-judge` puis envoi via `zimbra-ops`."
            if stats.drafts_created > 0
            else "Aucun promoteur éligible aujourd'hui."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ReviewBot",
    )


class ReviewBot(BaseAgent):
    """Sollicite avis G2/Capterra des promoteurs J+30 post-onboarding."""

    name = "ReviewBot"
    command = "/run-review-campaign"
    breaker_name = "ReviewBot"

    def __init__(
        self,
        *,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        drafts_dir: Path = DEFAULT_DRAFTS_DIR,
    ) -> None:
        self._customers_path = customers_path
        self._drafts_dir = drafts_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        customers = load_customers(self._customers_path)
        if not customers:
            logger.info(f"ReviewBot — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        today = date.today()
        stats = ReviewStats(customers_seen=len(customers))
        for customer in customers:
            if not is_review_eligible(customer, today=today):
                continue
            draft_path = self._drafts_dir / f"{customer.customer_id}.md"
            if draft_path.exists():
                stats.drafts_skipped += 1
                continue
            try:
                created = _draft_review_request(customer, self._drafts_dir)
                stats.drafts_created += 1
                stats.drafts.append(created.name)
            except Exception as exc:
                logger.exception(f"ReviewBot — draft {customer.customer_id} échec : {exc}")

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.drafts_created > 0:
            try:
                await send_embed(webhook, build_review_embed(stats))
            except Exception as exc:
                logger.warning(f"ReviewBot — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_DRAFTS_DIR",
    "REVIEW_REQUEST_DELAY_DAYS",
    "ReviewBot",
    "ReviewStats",
    "build_review_embed",
    "is_review_eligible",
]
