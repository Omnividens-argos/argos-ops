"""OutboundBot — scaffold de séquences cold email (P13, shadow mode).

Pipeline shadow strict (cron quotidien) :

1. Lit ``data/outbound/inbox/leads.csv`` (manuellement déposé par le
   fondateur ou via export LinkedIn Search)
2. Pour chaque lead, vérifie si la séquence existe déjà (idempotence
   sur ``data/outbound/sequences/<slug>/meta.yaml``)
3. Sinon, scaffold le répertoire (meta.yaml + 5 touch_*.md placeholders
   + cadence D+0/D+3/D+7/D+14/D+30 + opt-out token HMAC pré-calculé)
4. Notification Discord avec stats
5. **N'envoie aucun email** tant que ``OUTBOUND_LIVE_MODE=true`` ET
   ``OUTBOUND_FROM_DOMAIN`` ET ``OUTBOUND_UNSUBSCRIBE_SECRET`` sont tous
   renseignés (P13.B live mode, futur)

Drafting (remplir le body de chaque touche) → ``/draft-outbound <slug>``
humain-in-the-loop, qui invoque les skills ``lead-enricher`` +
``outbound-personalizer`` + ``claude-judge``.

Breaker métier câblé : ``outbound_volume_exceeded`` (P15) — déclenché
si on tente de scaffold plus de ``OUTBOUND_DAILY_MAX`` leads dans la
fenêtre 24 h. Protège contre un CSV qui contiendrait 5000 lignes par
erreur.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.breakers import trip_with_notification
from argos_ops.config import get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.outbound.sequence import (
    INBOX_DIR,
    is_sequence_scaffolded,
    read_inbox_csv,
    scaffold_sequence_dir,
)
from argos_ops.outbound.templates import slugify

DEFAULT_CSV_NAME = "leads.csv"
"""Nom canonique du CSV de leads dans ``data/outbound/inbox/``."""


@dataclass
class ScaffoldStats:
    """Photo d'un run d'OutboundBot — sérialisé dans ``agent_runs.output_summary``."""

    read: int = 0
    already_scaffolded: int = 0
    newly_scaffolded: int = 0
    failures: int = 0
    new_slugs: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"read={self.read} new={self.newly_scaffolded} "
            f"already={self.already_scaffolded} failures={self.failures}"
        )


def build_outbound_embed(stats: ScaffoldStats, live_mode: bool) -> Embed:
    """Embed Discord récap d'un run OutboundBot."""
    color = YELLOW if stats.newly_scaffolded > 0 else GREEN
    mode_label = "live (envoi actif)" if live_mode else "shadow (aucun envoi)"
    fields: list[EmbedField] = [
        EmbedField(name="Lus", value=str(stats.read), inline=True),
        EmbedField(name="Nouveaux scaffold", value=str(stats.newly_scaffolded), inline=True),
        EmbedField(name="Déjà scaffold", value=str(stats.already_scaffolded), inline=True),
        EmbedField(name="Mode", value=mode_label, inline=True),
        EmbedField(name="Échecs", value=str(stats.failures), inline=True),
    ]
    if stats.new_slugs:
        preview = [f"• {s}" for s in stats.new_slugs[:5]]
        if len(stats.new_slugs) > 5:
            preview.append(f"... +{len(stats.new_slugs) - 5} autres")
        fields.append(EmbedField(name="Slugs créés", value="\n".join(preview), inline=False))

    desc = (
        f"Lance `/draft-outbound <slug>` pour drafter le body des touches "
        f"({stats.newly_scaffolded} séquences en attente)."
        if stats.newly_scaffolded > 0
        else "Aucun nouveau lead à scaffold."
    )
    return Embed(
        title=f"Argos — OutboundBot ({stats.newly_scaffolded} nouvelles séquences)",
        description=desc,
        color=color,
        fields=fields,
        footer="Argos Ops • OutboundBot",
    )


class OutboundBot(BaseAgent):
    """Scaffold des séquences outbound — pas d'envoi en P13.A shadow."""

    name = "OutboundBot"
    command = "/run-outbound-bot"
    breaker_name = "OutboundBot"

    async def run(self) -> RunResult:
        settings = get_settings()
        if settings.outbound_unsubscribe_secret is None:
            return RunResult(
                status="failed",
                error=(
                    "OUTBOUND_UNSUBSCRIBE_SECRET manquant — requis même en shadow "
                    "pour pré-calculer les tokens d'opt-out. Génère via "
                    '`python -c "import secrets; print(secrets.token_hex(32))"`.'
                ),
            )

        csv_path = INBOX_DIR / DEFAULT_CSV_NAME
        if not csv_path.exists():
            logger.info(f"OutboundBot — aucun CSV à traiter ({csv_path} absent)")
            return RunResult(
                status="success",
                output_summary="read=0 new=0 already=0 failures=0 (no csv)",
            )

        try:
            leads = read_inbox_csv(csv_path)
        except ValueError as exc:
            logger.error(f"OutboundBot — CSV invalide : {exc}")
            return RunResult(status="failed", error=f"CSV invalide : {exc}")

        stats = ScaffoldStats(read=len(leads))
        logger.info(f"OutboundBot — {len(leads)} lead(s) lu(s) depuis {csv_path}")

        webhook = (
            settings.discord_webhook_ops_logs
            or settings.discord_webhook_alerts
            or settings.discord_webhook_escalations
        )

        # Garde-fou volume : si le CSV contient > daily_max nouveaux leads,
        # on trip le breaker AVANT de scaffold pour ne pas créer 5000
        # répertoires en silence (probable erreur d'export).
        candidate_new = sum(
            1 for lead in leads if not is_sequence_scaffolded(slugify(lead.full_name, lead.domain))
        )
        if candidate_new > settings.outbound_daily_max:
            await trip_with_notification(
                "outbound_volume_exceeded",
                (
                    f"CSV inbox contient {candidate_new} nouveaux leads, soit > "
                    f"OUTBOUND_DAILY_MAX={settings.outbound_daily_max}. "
                    "Probable erreur d'export. Vérifie data/outbound/inbox/leads.csv "
                    "puis `/reset-breaker outbound_volume_exceeded`."
                ),
                discord_webhook=webhook,
                severity="warning",
            )
            return RunResult(
                status="failed",
                error=(
                    f"Volume {candidate_new} > daily_max {settings.outbound_daily_max} — "
                    "breaker outbound_volume_exceeded tripped"
                ),
            )

        secret = settings.outbound_unsubscribe_secret.get_secret_value()
        for lead in leads:
            slug = slugify(lead.full_name, lead.domain)
            try:
                if is_sequence_scaffolded(slug):
                    stats.already_scaffolded += 1
                    continue
                scaffold_sequence_dir(lead, secret=secret)
                stats.newly_scaffolded += 1
                stats.new_slugs.append(slug)
            except Exception as exc:
                stats.failures += 1
                logger.exception(f"OutboundBot — scaffold {slug} a échoué : {exc}")

        if webhook is not None:
            try:
                await send_embed(webhook, build_outbound_embed(stats, settings.outbound_live_mode))
            except Exception as exc:
                logger.warning(f"OutboundBot — notif Discord a échoué : {exc}")
        else:
            logger.warning(
                "OutboundBot — aucun webhook Discord configuré (ops_logs/alerts/escalations)"
            )

        return RunResult(status="success", output_summary=stats.summary())


__all__ = ["DEFAULT_CSV_NAME", "OutboundBot", "ScaffoldStats", "build_outbound_embed"]
