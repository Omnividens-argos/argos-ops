"""NPSCollector — Voice of Customer (P22.G CS Sprint 7).

Drafte les emails NPS à envoyer :
- **post-onboarding** : client dont ``onboarding_done_at`` ≥ 14 jours et
  pas de NPS collecté depuis (``last_nps_at`` < ``onboarding_done_at``)
- **post-renew** : client dont ``last_renew_at`` < 21 jours et
  ``last_nps_at`` < ``last_renew_at``

Drafts dans ``data/nps/drafts/<customer>-<reason>.md``. Humain valide et
envoie via ``zimbra-ops``. Idempotent — re-lancer ne recrée pas un draft
existant. Le founder marque la réponse en patchant ``last_nps`` +
``last_nps_at`` dans ``data/cs/customers.yaml`` à la main.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import Customer
from argos_ops.cs.templates import render_nps_email
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_DRAFTS_DIR: Path = REPO_ROOT / "data" / "nps" / "drafts"

POST_ONBOARDING_DELAY_DAYS = 14
POST_RENEW_DELAY_DAYS = 21


@dataclass
class NPSStats:
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


def needs_post_onboarding_nps(customer: Customer, *, today: date) -> bool:
    """True si NPS post-onboarding échu et pas encore collecté."""
    if customer.onboarding_done_at is None:
        return False
    if (today - customer.onboarding_done_at).days < POST_ONBOARDING_DELAY_DAYS:
        return False
    if customer.last_nps_at is None:
        return True
    return customer.last_nps_at < customer.onboarding_done_at


def needs_post_renew_nps(customer: Customer, *, today: date) -> bool:
    """True si NPS post-renew échu et pas encore collecté pour ce renew."""
    if customer.last_renew_at is None:
        return False
    if (today - customer.last_renew_at).days < POST_RENEW_DELAY_DAYS:
        return False
    if customer.last_nps_at is None:
        return True
    return customer.last_nps_at < customer.last_renew_at


def _draft_nps(customer: Customer, reason: str, drafts_dir: Path) -> Path:
    drafts_dir.mkdir(parents=True, exist_ok=True)
    subject, body = render_nps_email(
        contact_first_name=_first_name(customer.contact_name, customer.contact_email),
        company=customer.name,
        reason=reason,
    )
    front = {
        "customer_id": customer.customer_id,
        "to": customer.contact_email,
        "subject": subject,
        "reason": reason,
        "status": "drafted",
    }
    draft_path = drafts_dir / f"{customer.customer_id}-{reason}.md"
    draft_path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}\n",
        encoding="utf-8",
    )
    return draft_path


def build_nps_embed(stats: NPSStats) -> Embed:
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
        title=f"NPSCollector — {stats.drafts_created} demande(s) NPS draftée(s)",
        description=(
            "Lis `data/nps/drafts/<id>-<reason>.md`, audit via `claude-judge`, envoie via `zimbra-ops`."
            if stats.drafts_created > 0
            else "Aucun NPS à demander aujourd'hui."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • NPSCollector",
    )


class NPSCollector(BaseAgent):
    """Drafte les demandes NPS post-onboarding J+14 et post-renew J+21."""

    name = "NPSCollector"
    command = "/run-nps-campaign"
    breaker_name = "NPSCollector"
    ai_act_risk_class = "limited"

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
            logger.info(f"NPSCollector — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        today = date.today()
        stats = NPSStats(customers_seen=len(customers))
        for customer in customers:
            reasons: list[str] = []
            if needs_post_onboarding_nps(customer, today=today):
                reasons.append("onboarding_done")
            if needs_post_renew_nps(customer, today=today):
                reasons.append("renew")
            for reason in reasons:
                draft_path = self._drafts_dir / f"{customer.customer_id}-{reason}.md"
                if draft_path.exists():
                    stats.drafts_skipped += 1
                    continue
                try:
                    created = _draft_nps(customer, reason, self._drafts_dir)
                    stats.drafts_created += 1
                    stats.drafts.append(created.name)
                except Exception as exc:
                    logger.exception(
                        f"NPSCollector — draft {customer.customer_id} {reason} échec : {exc}"
                    )

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.drafts_created > 0:
            try:
                await send_embed(webhook, build_nps_embed(stats))
            except Exception as exc:
                logger.warning(f"NPSCollector — notif Discord échouée : {exc}")

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return str(p)

        inputs = [
            IOItem(
                label="Clients CS",
                kind="file",
                detail="échéances post-onboarding J+14 / post-renew J+21",
                ref=_rel(self._customers_path),
                count=stats.customers_seen,
            )
        ]
        outputs: list[IOItem] = []
        if stats.drafts_created > 0:
            outputs.append(
                IOItem(
                    label="Drafts demandes NPS",
                    kind="draft",
                    detail="envoi humain via zimbra-ops",
                    ref=_rel(self._drafts_dir),
                    count=stats.drafts_created,
                )
            )

        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_DRAFTS_DIR",
    "POST_ONBOARDING_DELAY_DAYS",
    "POST_RENEW_DELAY_DAYS",
    "NPSCollector",
    "NPSStats",
    "build_nps_embed",
    "needs_post_onboarding_nps",
    "needs_post_renew_nps",
]
