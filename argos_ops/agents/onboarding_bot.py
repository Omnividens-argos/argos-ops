"""OnboardingBot — CSM Onboarding (P22.G CS Sprint 7).

Pilote la checklist onboarding J+0 / J+7 / J+30 de chaque client. Lit
``data/cs/customers.yaml`` (rempli à la main par le fondateur après chaque
nouveau signup Stripe), drafte un email d'onboarding pour chaque étape
dont la date est échue et qui n'a pas encore été draftée.

Humain-in-the-loop strict : le bot ne fait QUE drafter. Le fondateur lit
``data/onboarding/drafts/<customer>-J<step>.md``, peaufine, et envoie via
``zimbra-ops``. Idempotent : un draft déjà créé n'est pas recréé.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import Customer
from argos_ops.cs.templates import (
    ONBOARDING_DAY_0,
    ONBOARDING_DAY_7,
    ONBOARDING_DAY_30,
    render_onboarding_email,
)
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_DRAFTS_DIR: Path = REPO_ROOT / "data" / "onboarding" / "drafts"

ONBOARDING_STEPS: tuple[int, ...] = (ONBOARDING_DAY_0, ONBOARDING_DAY_7, ONBOARDING_DAY_30)


@dataclass
class OnboardingStats:
    """Récap d'un run."""

    customers_seen: int = 0
    drafts_created: int = 0
    drafts_skipped: int = 0  # déjà draftés ou pas encore dus
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"customers={self.customers_seen} drafted={self.drafts_created} "
            f"skipped={self.drafts_skipped}"
        )


def _due_steps(customer: Customer, *, today: date) -> list[int]:
    """Renvoie les étapes onboarding échues depuis ``signup_date``."""
    delta_days = (today - customer.signup_date).days
    return [step for step in ONBOARDING_STEPS if delta_days >= step]


def _first_name(contact_name: str, fallback_email: str) -> str:
    """Devine le prénom depuis ``contact_name`` ou la partie locale email."""
    if contact_name and contact_name.strip():
        return contact_name.strip().split()[0]
    local = fallback_email.split("@", 1)[0]
    return local.split(".")[0].capitalize() if "." in local else local.capitalize()


def _draft_onboarding(customer: Customer, step: int, drafts_dir: Path) -> Path:
    """Crée un draft Markdown avec frontmatter + corps templaté."""
    drafts_dir.mkdir(parents=True, exist_ok=True)
    subject, body = render_onboarding_email(
        contact_first_name=_first_name(customer.contact_name, customer.contact_email),
        company=customer.name,
        plan=customer.plan.value,
        step=step,
        signup_date=customer.signup_date,
    )
    front = {
        "customer_id": customer.customer_id,
        "to": customer.contact_email,
        "subject": subject,
        "step": f"J+{step}",
        "status": "drafted",
    }
    draft_path = drafts_dir / f"{customer.customer_id}-J{step}.md"
    draft_path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}\n",
        encoding="utf-8",
    )
    return draft_path


def build_onboarding_embed(stats: OnboardingStats) -> Embed:
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
        title=f"OnboardingBot — {stats.drafts_created} email(s) d'onboarding draftés",
        description=(
            "Lis `data/onboarding/drafts/<id>-J<step>.md` et envoie via `zimbra-ops`."
            if stats.drafts_created > 0
            else "Aucun onboarding à drafter aujourd'hui."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • OnboardingBot",
    )


class OnboardingBot(BaseAgent):
    """Drafte les emails onboarding J+0 / J+7 / J+30 (humain envoie)."""

    name = "OnboardingBot"
    command = "/run-onboarding"
    breaker_name = "OnboardingBot"

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
            logger.info(f"OnboardingBot — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        today = date.today()
        stats = OnboardingStats(customers_seen=len(customers))
        for customer in customers:
            for step in _due_steps(customer, today=today):
                draft_path = self._drafts_dir / f"{customer.customer_id}-J{step}.md"
                if draft_path.exists():
                    stats.drafts_skipped += 1
                    continue
                try:
                    created = _draft_onboarding(customer, step, self._drafts_dir)
                    stats.drafts_created += 1
                    stats.drafts.append(created.name)
                except Exception as exc:
                    logger.exception(
                        f"OnboardingBot — draft {customer.customer_id} J+{step} échec : {exc}"
                    )

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.drafts_created > 0:
            try:
                await send_embed(webhook, build_onboarding_embed(stats))
            except Exception as exc:
                logger.warning(f"OnboardingBot — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_DRAFTS_DIR",
    "ONBOARDING_STEPS",
    "OnboardingBot",
    "OnboardingStats",
    "build_onboarding_embed",
]
