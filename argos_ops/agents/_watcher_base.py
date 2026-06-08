"""Pattern partagé des watcher bots Argos Ops (P22.B/C Meta-Ops + Tech/SRE).

Tous les watchers (``BotHealthBot``, ``BotPerfAnalyzer``,
``UptimeMonitor``, ``ErrorTriageBot``, ``KillSwitchOperator``,
``BotConfigManager``, ``SSLExpirer``, ``SecretRotator``,
``DependencyAuditor``, ``BackupVerifier``) suivent le même cycle :

1. Lire un état (DB, fichier YAML, API publique, filesystem)
2. Construire un ``WatcherReport`` (3 champs canoniques : ``should_alert``,
   ``alert_color``, ``summary``)
3. Si tout est vert → silence Discord (anti-spam)
4. Sinon → push embed sur ``DISCORD_WEBHOOK_OPS_LOGS`` (ou webhook custom)

Ce module factorise le step 3-4 dans :func:`emit_alert_or_silence` pour
éviter de dupliquer la logique « silence vs webhook absent vs push »
N fois. Voir aussi les helpers de formatage (durées, pourcentages, ages)
réutilisables entre watchers.

Contrat important : les ``output_summary`` retournés commencent par
``silence (vert)``, ``silence (``, ``alerte non envoyée``, ou
``alert pushed`` — les slash commands (``.claude/commands/run-*.md``)
parsent ces préfixes pour décider du retour user.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from loguru import logger

from argos_ops.agents.base import IOItem, RunResult
from argos_ops.config import Settings, get_settings
from argos_ops.notifications.discord import Embed, send_embed


class WatcherReport(Protocol):
    """Contrat minimal qu'un report de watcher doit respecter.

    Champs déclarés en ``@property`` pour rester compatibles avec des
    dataclasses ``frozen=True`` (qui exposent leurs attributs en
    read-only et seraient sinon rejetées par le Protocol).
    """

    @property
    def should_alert(self) -> bool: ...
    @property
    def alert_color(self) -> int: ...
    @property
    def summary(self) -> str: ...


async def emit_alert_or_silence[ReportT: WatcherReport](
    report: ReportT,
    *,
    embed_builder: Callable[[ReportT], Embed],
    agent_name: str,
    webhook_attr_name: str = "discord_webhook_ops_logs",
    settings: Settings | None = None,
    inputs: list[IOItem] | None = None,
    outputs: list[IOItem] | None = None,
) -> RunResult:
    """Politique commune des watchers : silence si vert, alerte sinon.

    - ``embed_builder`` reçoit le report et retourne l'``Embed`` à pusher
    - ``webhook_attr_name`` permet de cibler un autre webhook que celui
      par défaut (ex : ``discord_webhook_alerts`` pour les events critiques)
    - ``settings`` injectable pour les tests (sinon ``get_settings()``)
    - ``inputs`` / ``outputs`` : IN/OUT structuré du watcher (cf. IOItem) pour
      l'onglet Travail du cockpit. Optionnel — un watcher non instrumenté laisse
      ``None`` et l'UI retombe sur une vue dérivée.

    Garantit ces préfixes canoniques dans ``output_summary`` :
    - ``silence (vert) — …`` quand tout est ok
    - ``alerte non envoyée (webhook absent) — …`` si le webhook n'est
      pas configuré
    - ``alert pushed — …`` quand l'embed est posté avec succès
    """
    ins = inputs or []
    outs = outputs or []
    if not report.should_alert:
        logger.info(f"{agent_name} — tout vert, silence Discord ({report.summary})")
        return RunResult(
            status="success",
            output_summary=f"silence (vert) — {report.summary}",
            extras={"alerted": False, "summary": report.summary},
            inputs=ins,
            outputs=outs,
        )

    settings = settings or get_settings()
    webhook = getattr(settings, webhook_attr_name, None)
    if webhook is None:
        logger.warning(
            f"{agent_name} — alerte détectée mais {webhook_attr_name.upper()} non configuré"
        )
        return RunResult(
            status="success",
            output_summary=f"alerte non envoyée (webhook absent) — {report.summary}",
            extras={"alerted": False, "summary": report.summary},
            inputs=ins,
            outputs=outs,
        )

    embed = embed_builder(report)
    await send_embed(webhook, embed)
    logger.info(f"{agent_name} — embed pushé ({report.summary})")
    return RunResult(
        status="success",
        output_summary=f"alert pushed — {report.summary}",
        extras={"alerted": True, "summary": report.summary},
        inputs=ins,
        outputs=outs,
    )


# =============================================================================
# Helpers de formatage partagés
# =============================================================================
def format_age(age_hours: float | None) -> str:
    """Format ``age_hours`` en chaîne courte humaine (min/h/j)."""
    if age_hours is None:
        return "jamais"
    if age_hours < 1.0:
        return f"{int(age_hours * 60)}min"
    if age_hours < 48.0:
        return f"{age_hours:.1f}h"
    return f"{age_hours / 24:.1f}j"


def format_duration(seconds: float | None) -> str:
    """Format une durée en ms/s/min selon l'échelle."""
    if seconds is None:
        return "n/a"
    if seconds < 1.0:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60.0:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}min"


def format_rate(value: float | None) -> str:
    """Format un ratio 0.0-1.0 en pourcentage."""
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def color_title(color: int, *, green: int, yellow: int, red: int) -> str:
    """Retourne ``"GREEN"`` / ``"YELLOW"`` / ``"RED"`` pour le titre d'embed."""
    if color == red:
        return "RED"
    if color == yellow:
        return "YELLOW"
    if color == green:
        return "GREEN"
    return "OTHER"


__all__ = [
    "WatcherReport",
    "color_title",
    "emit_alert_or_silence",
    "format_age",
    "format_duration",
    "format_rate",
]
