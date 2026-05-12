"""FinanceBot — synchronisation Stripe + dunning automatique (P7).

Pipeline :

1. Pull toutes les subs Stripe → upsert `companies` (stripe_customer_id,
   subscription_status, mrr_eur, stripe_synced_at)
2. Pull les invoices `status='open'` → classification dunning J+3 / J+7 / J+15
3. Pour chaque facture sous-classifiée + dont la relance n'a pas déjà été
   envoyée à ce niveau, drafter + envoyer email via Zimbra SMTP, logger
   l'interaction sortante
4. Calculer MRR total + comparer au MRR 7 jours plus tôt → alerte Discord
   si baisse > 5 %
5. Logger `agent_runs.output_summary` avec metrics canoniques

D-017 : aucun appel LLM ici. Les emails de relance sont des templates
paramétrés (pas drafted par Claude — ton dégradé pré-écrit, factuel).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from loguru import logger
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.breakers import count_recent_failed, trip_with_notification
from argos_ops.config import get_settings
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import Company, Lead
from argos_ops.crm.repository import (
    add_interaction,
    get_or_create_company,
    get_or_create_lead,
)
from argos_ops.integrations.stripe_client import (
    DunningLevel,
    StripeInvoice,
    StripeSubscription,
    classify_dunning_level,
    compute_arr_eur,
    compute_mrr_eur,
    fetch_active_subscriptions,
    fetch_open_invoices,
)
from argos_ops.integrations.zimbra import send_email
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

# =============================================================================
# Templates relances dunning
# =============================================================================
DUNNING_TEMPLATES: dict[DunningLevel, dict[str, str]] = {
    "J+3": {
        "subject": "Petit rappel — facture {invoice_id}",
        "body": (
            "Bonjour,\n\n"
            "Petit rappel : la facture {invoice_id} d'un montant de {amount} € "
            "était attendue le {due_date}. Stripe a peut-être eu un souci avec "
            "votre moyen de paiement.\n\n"
            "Vous pouvez la régler directement ici : {invoice_url}\n\n"
            "Si c'est déjà fait, merci d'ignorer ce message.\n\n"
            "À bientôt,"
        ),
    },
    "J+7": {
        "subject": "Facture impayée — {invoice_id}",
        "body": (
            "Bonjour,\n\n"
            "La facture {invoice_id} ({amount} €) est impayée depuis le "
            "{due_date}. Merci de régulariser sous 7 jours pour éviter "
            "la suspension de votre abonnement.\n\n"
            "Lien de paiement : {invoice_url}\n\n"
            "Si vous avez une question ou un problème pour régler, "
            "répondez à ce mail — un humain prendra le relais.\n\n"
            "Cordialement,"
        ),
    },
    "J+15": {
        "subject": "Suspension imminente — facture {invoice_id}",
        "body": (
            "Bonjour,\n\n"
            "Votre facture {invoice_id} ({amount} €) est impayée depuis "
            "plus de 15 jours. Votre abonnement Argos sera suspendu sous "
            "48 h sans régularisation.\n\n"
            "Lien de paiement : {invoice_url}\n\n"
            "Si vous traversez une difficulté, contactez-nous — on trouve "
            "toujours une solution. Répondez simplement à ce mail.\n\n"
            "Cordialement,"
        ),
    },
}


def render_dunning_email(level: DunningLevel, invoice: StripeInvoice) -> tuple[str, str] | None:
    """Renvoie ``(subject, body)`` rendu pour le niveau, ou None si level='none'."""
    if level == "none":
        return None
    tpl = DUNNING_TEMPLATES[level]
    due_date_str = invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else "n/a"
    ctx = {
        "invoice_id": invoice.id,
        "amount": f"{invoice.amount_due_eur:.2f}",
        "due_date": due_date_str,
        "invoice_url": invoice.hosted_invoice_url or "(lien non disponible)",
    }
    return tpl["subject"].format(**ctx), tpl["body"].format(**ctx)


# =============================================================================
# Stats
# =============================================================================
@dataclass
class FinanceStats:
    """Photo d'un run FinanceBot — sérialisé dans ``agent_runs.output_summary``."""

    n_subs: int = 0
    n_active_subs: int = 0
    mrr_eur: Decimal = Decimal("0.00")
    arr_eur: Decimal = Decimal("0.00")
    mrr_delta_pct: float | None = None
    n_open_invoices: int = 0
    n_dunning_sent_j3: int = 0
    n_dunning_sent_j7: int = 0
    n_dunning_sent_j15: int = 0
    n_companies_synced: int = 0

    def summary(self) -> str:
        delta = f"mrr_delta={self.mrr_delta_pct:+.1f}% " if self.mrr_delta_pct is not None else ""
        return (
            f"mrr={self.mrr_eur} arr={self.arr_eur} {delta}"
            f"active_subs={self.n_active_subs}/{self.n_subs} "
            f"open_inv={self.n_open_invoices} "
            f"dunning_sent_3={self.n_dunning_sent_j3} "
            f"dunning_sent_7={self.n_dunning_sent_j7} "
            f"dunning_sent_15={self.n_dunning_sent_j15} "
            f"companies_synced={self.n_companies_synced}"
        ).strip()


# =============================================================================
# Sync companies depuis Stripe
# =============================================================================
async def _upsert_company_from_sub(session: AsyncSession, sub: StripeSubscription) -> int | None:
    """Upsert ou récupère la company associée à une subscription Stripe.

    Stratégie d'identification :
    1. Si on a déjà une company avec ``stripe_customer_id`` → MAJ
    2. Sinon, lookup par domaine de l'email customer
    3. Sinon, créer une company orpheline (domain=None) liée au customer Stripe
    """
    # 1) match par stripe_customer_id
    existing = (
        await session.execute(
            select(Company).where(col(Company.stripe_customer_id) == sub.customer_id)
        )
    ).scalar_one_or_none()

    if existing is None and sub.customer_email:
        # 2) match par domaine email
        from argos_ops.integrations.zimbra import extract_domain

        domain = extract_domain(sub.customer_email)
        if domain:
            existing = (
                await session.execute(select(Company).where(col(Company.domain) == domain))
            ).scalar_one_or_none()

    if existing is None:
        # 3) Création d'une company à partir du customer Stripe
        domain_for_new = None
        if sub.customer_email:
            from argos_ops.integrations.zimbra import extract_domain

            domain_for_new = extract_domain(sub.customer_email)
        existing = await get_or_create_company(
            session,
            domain=domain_for_new or f"stripe-{sub.customer_id}",
            name=sub.customer_name,
            source="stripe",
        )

    existing.stripe_customer_id = sub.customer_id
    existing.subscription_status = sub.status
    existing.mrr_eur = sub.mrr_eur
    existing.stripe_synced_at = datetime.now(UTC)
    return existing.id


# =============================================================================
# Détection des relances déjà envoyées
# =============================================================================
async def _has_dunning_been_sent(
    session: AsyncSession, invoice_id: str, level: DunningLevel
) -> bool:
    """Retourne True si une relance ``dunning_<level>`` a déjà été envoyée
    pour cette ``invoice_id`` (recherche par subject + judge_verdict)."""
    sql = text(
        """
        SELECT 1 FROM interactions
        WHERE channel = 'email' AND direction = 'out'
          AND agent_name = 'FinanceBot'
          AND judge_verdict = :verdict
          AND subject LIKE :pattern
        LIMIT 1
        """
    )
    res = (
        await session.execute(
            sql,
            {"verdict": f"dunning_{level}", "pattern": f"%{invoice_id}%"},
        )
    ).first()
    return res is not None


async def _ensure_lead_for_invoice(session: AsyncSession, invoice: StripeInvoice) -> int | None:
    """Lookup ou crée un lead pour un destinataire de relance."""
    if not invoice.customer_email:
        return None
    existing_lead = (
        await session.execute(select(Lead).where(col(Lead.email) == invoice.customer_email))
    ).scalar_one_or_none()
    if existing_lead is not None:
        return existing_lead.id

    # Lookup company par stripe_customer_id
    company_id: int | None = None
    company = (
        await session.execute(
            select(Company).where(col(Company.stripe_customer_id) == invoice.customer_id)
        )
    ).scalar_one_or_none()
    if company is not None:
        company_id = company.id

    lead = await get_or_create_lead(
        session,
        email=invoice.customer_email,
        company_id=company_id,
        full_name=invoice.customer_name,
    )
    return lead.id


# =============================================================================
# MRR baseline (7 jours)
# =============================================================================
_MRR_PATTERN = re.compile(r"mrr=([\d.]+)")


async def _baseline_mrr_7d_ago(session: AsyncSession) -> Decimal | None:
    """Récupère le MRR du dernier run FinanceBot >= 7 jours en arrière.

    Retourne None si aucun historique exploitable (premier run, ou parsing
    raté). Le MRR est extrait de ``agent_runs.output_summary`` via regex.
    """
    cutoff = datetime.now(UTC) - timedelta(days=7)
    sql = text(
        """
        SELECT output_summary FROM agent_runs
        WHERE agent_name = 'FinanceBot' AND status = 'success'
          AND started_at < :cutoff AND output_summary IS NOT NULL
        ORDER BY started_at DESC
        LIMIT 1
        """
    )
    row = (await session.execute(sql, {"cutoff": cutoff})).first()
    if row is None or not row.output_summary:
        return None
    match = _MRR_PATTERN.search(row.output_summary)
    if match is None:
        return None
    try:
        return Decimal(match.group(1))
    except Exception:
        return None


# =============================================================================
# Notification Discord
# =============================================================================
def build_finance_embed(stats: FinanceStats) -> Embed:
    """Embed digest finance — couleur selon état."""
    color = GREEN
    if stats.mrr_delta_pct is not None and stats.mrr_delta_pct <= -5.0:
        color = RED
    elif stats.n_open_invoices > 0 or stats.n_dunning_sent_j15 > 0:
        color = YELLOW

    delta_str = (
        f"{stats.mrr_delta_pct:+.1f}% vs S-1"
        if stats.mrr_delta_pct is not None
        else "baseline indisponible"
    )

    fields = [
        EmbedField(name="MRR", value=f"{stats.mrr_eur} € ({delta_str})", inline=False),
        EmbedField(name="ARR", value=f"{stats.arr_eur} €", inline=True),
        EmbedField(
            name="Subs actives",
            value=f"{stats.n_active_subs}/{stats.n_subs}",
            inline=True,
        ),
        EmbedField(
            name="Factures impayées",
            value=str(stats.n_open_invoices),
            inline=True,
        ),
        EmbedField(
            name="Relances envoyées",
            value=(
                f"J+3: {stats.n_dunning_sent_j3} · "
                f"J+7: {stats.n_dunning_sent_j7} · "
                f"J+15: {stats.n_dunning_sent_j15}"
            ),
            inline=False,
        ),
    ]
    return Embed(
        title="Argos Ops — Finance daily sync",
        color=color,
        fields=fields,
        footer="Argos Ops • FinanceBot",
    )


# =============================================================================
# Agent
# =============================================================================
class FinanceBot(BaseAgent):
    """Sync Stripe quotidienne — companies + dunning + MRR alerte."""

    name = "FinanceBot"
    command = "/daily-finance-sync"
    breaker_name = "FinanceBot"

    async def run(self) -> RunResult:
        settings = get_settings()
        if settings.stripe_secret_key is None:
            return RunResult(
                status="failed",
                error="STRIPE_SECRET_KEY manquant dans .env.local",
            )
        if settings.email_user is None or settings.email_password is None:
            return RunResult(
                status="failed",
                error="EMAIL_USER/EMAIL_PASSWORD manquants — voir D-005",
            )

        stats = FinanceStats()

        # 1. Pull subscriptions
        try:
            subs = await fetch_active_subscriptions(settings.stripe_secret_key)
        except Exception as exc:
            logger.error(f"FinanceBot — Stripe subs fetch a échoué : {type(exc).__name__}")
            return RunResult(status="failed", error=f"Stripe subs: {type(exc).__name__}: {exc}")

        stats.n_subs = len(subs)
        stats.n_active_subs = sum(1 for s in subs if s.status in ("active", "trialing"))
        stats.mrr_eur = compute_mrr_eur(subs)
        stats.arr_eur = compute_arr_eur(stats.mrr_eur)

        async with session_scope() as session:
            # 2. Sync companies
            for sub in subs:
                if sub.customer_id:
                    cid = await _upsert_company_from_sub(session, sub)
                    if cid is not None:
                        stats.n_companies_synced += 1

            # 3. MRR delta vs S-1
            baseline = await _baseline_mrr_7d_ago(session)
            if baseline is not None and baseline > 0:
                delta = (stats.mrr_eur - baseline) / baseline * Decimal(100)
                stats.mrr_delta_pct = float(delta)

        # 4. Dunning impayés
        try:
            invoices = await fetch_open_invoices(settings.stripe_secret_key)
        except Exception as exc:
            logger.error(f"FinanceBot — Stripe invoices fetch a échoué : {type(exc).__name__}")
            return RunResult(status="failed", error=f"Stripe invoices: {type(exc).__name__}: {exc}")

        stats.n_open_invoices = len(invoices)

        # Garde-fou : tant que FINANCEBOT_DUNNING_ENABLED n'est pas explicitement
        # à true, on n'envoie pas de relance (mais on log les niveaux détectés).
        # Évite l'envoi accidentel de relances à de vrais clients SecHunter
        # avant d'avoir audité le wording / le ton sur un premier run.
        if not settings.financebot_dunning_enabled:
            for inv in invoices:
                level = classify_dunning_level(inv)
                if level != "none":
                    logger.info(
                        f"[DUNNING_DISABLED] {level} aurait été envoyé pour "
                        f"{inv.id} ({inv.customer_email})"
                    )
        else:
            for inv in invoices:
                level = classify_dunning_level(inv)
                if level == "none":
                    continue
                await self._maybe_send_dunning(inv, level, stats)

        # 5. Notif Discord
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None:
            try:
                await send_embed(webhook, build_finance_embed(stats))
            except Exception as exc:
                logger.warning(f"FinanceBot — notif Discord a échoué : {exc}")

        # 6. Breakers métier (P15) — chute MRR critique + burst d'erreurs API
        await self._maybe_trip_business_breakers(stats, webhook)

        return RunResult(status="success", output_summary=stats.summary())

    async def _maybe_trip_business_breakers(
        self, stats: FinanceStats, discord_webhook: SecretStr | None
    ) -> None:
        """Trip les breakers métier FinanceBot si conditions atteintes.

        ``mrr_drop_critical`` (sévérité ``critical``) — MRR a chuté de plus
        de 10 % sur 7 jours. Signal de churn massif à investiguer en P0.

        ``stripe_api_error_burst`` (sévérité ``critical``) — ≥ 3 runs
        ``failed`` dans les dernières 24 h. L'API Stripe est instable ou
        la clé restreinte a été révoquée. Reset manuel après audit.
        """
        if stats.mrr_delta_pct is not None and stats.mrr_delta_pct <= -10.0:
            await trip_with_notification(
                "mrr_drop_critical",
                f"MRR a chuté de {stats.mrr_delta_pct:.1f} % sur 7 jours — investiguer churn",
                discord_webhook=discord_webhook,
                severity="critical",
            )

        recent_failed = await count_recent_failed("FinanceBot", window_minutes=60 * 24)
        if recent_failed >= 3:
            await trip_with_notification(
                "stripe_api_error_burst",
                (
                    f"{recent_failed} runs FinanceBot ont échoué dans les dernières 24 h — "
                    "investiguer Stripe API (clé révoquée ? rate limit ? incident upstream ?)"
                ),
                discord_webhook=discord_webhook,
                severity="critical",
            )

    async def _maybe_send_dunning(
        self, invoice: StripeInvoice, level: DunningLevel, stats: FinanceStats
    ) -> None:
        """Envoie une relance si pas déjà envoyée à ce niveau."""
        if not invoice.customer_email:
            logger.warning(f"Invoice {invoice.id} sans customer_email — relance impossible")
            return
        async with session_scope() as session:
            already_sent = await _has_dunning_been_sent(session, invoice.id, level)
            if already_sent:
                return

            rendered = render_dunning_email(level, invoice)
            if rendered is None:
                return
            subject, body = rendered

        # Envoi SMTP (hors transaction DB)
        settings = get_settings()
        try:
            await send_email(
                host=settings.email_smtp_host,
                port=settings.email_smtp_port,
                user=settings.email_user or "",
                password=settings.email_password,  # type: ignore[arg-type]
                from_name=settings.email_reply_name,
                to=invoice.customer_email,
                subject=subject,
                body_text=body,
                signature_tagline=settings.email_signature_tagline,
                signature_site_url=settings.email_signature_site_url,
                signature_ai_disclosure=settings.email_signature_ai_disclosure,
            )
        except Exception as exc:
            logger.error(f"FinanceBot — envoi relance {level} pour {invoice.id} a échoué : {exc}")
            return

        # Log interaction outbound
        async with session_scope() as session:
            lead_id = await _ensure_lead_for_invoice(session, invoice)
            await add_interaction(
                session,
                lead_id=lead_id,
                channel="email",
                direction="out",
                agent_name="FinanceBot",
                subject=subject,
                body=body,
                judge_verdict=f"dunning_{level}",
            )

        if level == "J+3":
            stats.n_dunning_sent_j3 += 1
        elif level == "J+7":
            stats.n_dunning_sent_j7 += 1
        elif level == "J+15":
            stats.n_dunning_sent_j15 += 1
        logger.info(f"Relance {level} envoyée à {invoice.customer_email} pour {invoice.id}")


__all__ = [
    "DUNNING_TEMPLATES",
    "FinanceBot",
    "FinanceStats",
    "build_finance_embed",
    "render_dunning_email",
]
