"""Circuit breakers et kill switches Argos Ops (Partie 15).

Façade publique des breakers : wrappers async qui ouvrent leur propre
``session_scope``. Les agents les utilisent sans devoir gérer la session.

Deux familles de breakers cohabitent :

1. **Kill switches globaux par agent** — un breaker nommé d'après l'agent
   (``DigestBuilder``, ``EmailBot``, ``FinanceBot``…) que le fondateur peut
   trip manuellement depuis l'Admin Control Panel (P16). Quand trip,
   :func:`argos_ops.agents.base.run_agent` court-circuite l'exécution
   (status=``killed_by_breaker``). Pas de trip auto sur cette famille.

2. **Breakers métier** — déclenchés automatiquement par la logique de
   l'agent quand une anomalie business est détectée (chute MRR, burst
   d'erreurs API, etc.). Ne bloquent pas l'agent — ils notifient
   Discord et restent visibles dans le dashboard jusqu'à reset manuel
   via ``/reset-breaker``. La cause racine doit être corrigée avant
   reset (cf. P15.2 du plan).

Inventaire des breakers métier actuellement câblés (Sprint 1) :

- ``mrr_drop_critical`` — MRR -10 % ou plus sur 7 j (FinanceBot)
- ``stripe_api_error_burst`` — ≥ 3 runs FinanceBot ``failed`` sur 24 h
- ``email_smtp_failures_burst`` — ≥ 3 runs EmailBot ``failed`` sur 24 h
- ``outbound_volume_exceeded`` — CSV inbox > OUTBOUND_DAILY_MAX nouveaux
  leads (OutboundBot P13.A) — protège contre un export massif accidentel

Les breakers du plan original (``ad_spend_runaway``, ``email_spam_complaints``,
``judge_disagreement``, etc.) seront ajoutés au fur et à mesure que leurs
agents respectifs entreront en production (P12, P14).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from pydantic import SecretStr

from argos_ops.crm.db import session_scope
from argos_ops.crm.repository import (
    count_recent_failed_runs as _count_recent_failed_runs,
)
from argos_ops.crm.repository import (
    get_breaker as _get_breaker,
)
from argos_ops.crm.repository import (
    is_breaker_tripped as _is_breaker_tripped,
)
from argos_ops.crm.repository import (
    list_tripped_breakers as _list_tripped_breakers,
)
from argos_ops.crm.repository import (
    reset_breaker as _reset_breaker,
)
from argos_ops.crm.repository import (
    trip_breaker as _trip_breaker,
)
from argos_ops.notifications.discord import Embed, send_embed

# Couleurs canoniques par niveau de sévérité (hex int Discord embed.color)
SEVERITY_COLORS: dict[str, int] = {
    "critical": 0xDC2626,  # rouge
    "warning": 0xF97316,  # orange
    "info": 0x3B82F6,  # bleu
}

# Préfixes texte par sévérité (volontairement sans emoji ambigu pour le linter).
SEVERITY_PREFIXES: dict[str, str] = {
    "critical": "[CRITICAL]",
    "warning": "[WARNING]",
    "info": "[INFO]",
}


@dataclass(frozen=True)
class BreakerStatus:
    """État simplifié d'un breaker pour les UIs et l'API."""

    name: str
    tripped: bool
    tripped_at: datetime | None = None
    reason: str | None = None
    reset_after: datetime | None = None


# =============================================================================
# API publique — wrappers session_scope
# =============================================================================
async def trip(name: str, reason: str, *, reset_after: datetime | None = None) -> None:
    """Trip un breaker (idempotent — réécrit le motif si déjà tripped)."""
    async with session_scope() as session:
        await _trip_breaker(session, name, reason, reset_after=reset_after)
    logger.warning(f"Breaker '{name}' tripped — {reason}")


async def reset(name: str) -> None:
    """Reset manuel d'un breaker. No-op si jamais tripped ou déjà reset."""
    async with session_scope() as session:
        await _reset_breaker(session, name)
    logger.info(f"Breaker '{name}' reset")


async def is_tripped(name: str) -> bool:
    """Variant standalone pour les scripts (les agents passent par BaseAgent)."""
    async with session_scope() as session:
        return await _is_breaker_tripped(session, name)


async def status(name: str) -> BreakerStatus | None:
    """État détaillé d'un breaker — ``None`` s'il n'a jamais été tripped."""
    async with session_scope() as session:
        breaker = await _get_breaker(session, name)
    if breaker is None:
        return None
    return BreakerStatus(
        name=breaker.name,
        tripped=breaker.tripped,
        tripped_at=breaker.tripped_at,
        reason=breaker.reason,
        reset_after=breaker.reset_after,
    )


async def list_tripped() -> list[BreakerStatus]:
    """Liste tous les breakers actuellement tripped (auto-reset par délai exclus)."""
    async with session_scope() as session:
        breakers = await _list_tripped_breakers(session)
    return [
        BreakerStatus(
            name=b.name,
            tripped=b.tripped,
            tripped_at=b.tripped_at,
            reason=b.reason,
            reset_after=b.reset_after,
        )
        for b in breakers
    ]


async def count_recent_failed(agent_name: str, *, window_minutes: int = 60 * 24) -> int:
    """Compte les runs ``failed`` d'un agent sur une fenêtre.

    Utilisé par la logique de détection burst : si N runs consécutifs ont
    échoué, l'agent trip son breaker métier ``<agent>_api_error_burst``.
    """
    async with session_scope() as session:
        return await _count_recent_failed_runs(
            session, agent_name=agent_name, window_minutes=window_minutes
        )


# =============================================================================
# Helpers métier — détection + notification Discord en une opération
# =============================================================================
async def trip_with_notification(
    name: str,
    reason: str,
    *,
    discord_webhook: SecretStr | None,
    severity: str = "warning",
    reset_after: datetime | None = None,
) -> None:
    """Trip + envoie un embed Discord pour alerter le fondateur.

    Idempotent : si le breaker est déjà tripped, ne refait ni trip ni notif
    Discord (évite le spam à chaque cron). L'humain doit reset via
    ``/reset-breaker`` une fois la cause corrigée pour qu'un nouveau trip
    puisse re-alerter.

    ``severity`` contrôle la couleur de l'embed :
    - ``critical`` → rouge (urgence P0, action immédiate attendue)
    - ``warning`` → orange (action sous 24 h)
    - ``info`` → bleu (informatif, ne nécessite pas d'action)
    """
    if await is_tripped(name):
        logger.debug(f"Breaker '{name}' déjà tripped — skip notif Discord (idempotence)")
        return
    await trip(name, reason, reset_after=reset_after)
    if discord_webhook is None:
        logger.warning(f"Breaker '{name}' tripped mais aucun webhook Discord configuré")
        return
    color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["warning"])
    title_prefix = SEVERITY_PREFIXES.get(severity, SEVERITY_PREFIXES["warning"])
    try:
        await send_embed(
            discord_webhook,
            Embed(
                title=f"{title_prefix} Breaker '{name}' tripped",
                description=reason,
                color=color,
                footer="Reset via /reset-breaker une fois la cause racine corrigée",
                timestamp=datetime.now().astimezone().isoformat(),
            ),
        )
    except Exception as exc:
        logger.error(f"Notif Discord breaker '{name}' a échoué : {exc}")


def in_minutes(n: int) -> datetime:
    """Sucre syntaxique : retourne un ``datetime`` à N minutes dans le futur (UTC).

    Utile pour les breakers auto-reset (ex : pause Gmail rate-limit pendant 1 h
    puis reprise automatique sans intervention humaine).
    """
    from datetime import UTC

    return datetime.now(UTC) + timedelta(minutes=n)


__all__ = [
    "BreakerStatus",
    "count_recent_failed",
    "in_minutes",
    "is_tripped",
    "list_tripped",
    "reset",
    "status",
    "trip",
    "trip_with_notification",
]
