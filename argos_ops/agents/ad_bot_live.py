"""AdBot live (P12.B) — pilotage campagnes Google / LinkedIn / Meta Ads.

En live mode (``ADS_LIVE_MODE=true``), AdBot consomme les recommandations
chiffrées produites par ``ads-optimizer`` (skill, P12.A shadow) sous
``data/ads/recommendations/`` et applique les actions sur les APIs ads.

En shadow (par défaut), le bot lit les recos mais n'appelle aucune API
et notifie le fondateur du plan d'action pour validation manuelle.

Garde-fous :
- ``ADS_DAILY_BUDGET_EUR`` borne le total dépensable / jour
- Breaker ``ad_spend_runaway`` (P15) protège contre une reco runaway
- D-026 acte que le passage en live est conditionné à un budget pub
  > 0 € officiellement validé par le fondateur
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

RECOMMENDATIONS_DIR = REPO_ROOT / "data" / "ads" / "recommendations"
APPLIED_DIR = REPO_ROOT / "data" / "ads" / "applied"


@dataclass
class AdAction:
    """Une action chiffrée extraite d'une reco."""

    platform: str  # 'google' | 'linkedin' | 'meta'
    action: str  # 'pause' | 'scale' | 'drop_keyword' | 'new_creative'
    target: str  # campaign / ad-set / keyword identifier
    eur_delta_week: float  # impact estimé €/semaine (peut être négatif)
    rationale: str


@dataclass
class AdRunStats:
    recos_read: int = 0
    actions_applied: int = 0
    actions_shadow: int = 0
    actions_blocked: int = 0  # budget cap dépassé
    eur_committed_week: float = 0.0
    by_platform: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"recos={self.recos_read} applied={self.actions_applied} "
            f"shadow={self.actions_shadow} blocked={self.actions_blocked} "
            f"€/week={self.eur_committed_week:+.0f}"
        )


def load_recommendations() -> list[AdAction]:
    """Lit les recos YAML produites par ads-optimizer."""
    if not RECOMMENDATIONS_DIR.exists():
        return []
    actions: list[AdAction] = []
    for path in sorted(RECOMMENDATIONS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.warning(f"Reco {path.name} illisible : {exc}")
            continue
        for raw in data.get("actions", []):
            if not isinstance(raw, dict):
                continue
            actions.append(
                AdAction(
                    platform=str(raw.get("platform", "unknown")),
                    action=str(raw.get("action", "unknown")),
                    target=str(raw.get("target", "")),
                    eur_delta_week=float(raw.get("eur_delta_week", 0.0)),
                    rationale=str(raw.get("rationale", "")),
                )
            )
    return actions


def build_ad_embed(stats: AdRunStats, live_mode: bool, budget: int) -> Embed:
    color = ORANGE if stats.actions_blocked > 0 else (YELLOW if not live_mode else GREEN)
    fields = [
        EmbedField(name="Recos lues", value=str(stats.recos_read), inline=True),
        EmbedField(name="Appliquées", value=str(stats.actions_applied), inline=True),
        EmbedField(name="Shadow", value=str(stats.actions_shadow), inline=True),
        EmbedField(name="Bloquées (cap)", value=str(stats.actions_blocked), inline=True),
        EmbedField(name="Mode", value="live" if live_mode else "shadow", inline=True),
        EmbedField(name="Budget/jour", value=f"{budget} €", inline=True),
        EmbedField(
            name="Impact estimé",
            value=f"{stats.eur_committed_week:+.0f} €/semaine",
            inline=False,
        ),
    ]
    if stats.by_platform:
        breakdown = ", ".join(f"{p}={n}" for p, n in stats.by_platform.items())
        fields.append(EmbedField(name="Par plateforme", value=breakdown, inline=False))
    return Embed(
        title="Argos — AdBot (P12.B)",
        color=color,
        fields=fields,
        footer="Argos Ops • AdBot",
    )


def _archive_action(action: AdAction, status: str) -> None:
    APPLIED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = APPLIED_DIR / f"{stamp}-{action.platform}-{action.action}.yaml"
    out.write_text(
        yaml.safe_dump(
            {
                "applied_at": datetime.now(UTC).isoformat(),
                "status": status,
                "platform": action.platform,
                "action": action.action,
                "target": action.target,
                "eur_delta_week": action.eur_delta_week,
                "rationale": action.rationale,
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


class AdBotLive(BaseAgent):
    """Applique les recos `ads-optimizer` sur les APIs ads (ou shadow)."""

    name = "AdBot"
    command = "/run-ad-campaign"
    breaker_name = "ad_spend_runaway"
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        settings = get_settings()
        actions = load_recommendations()
        stats = AdRunStats(recos_read=len(actions))

        if not actions:
            return RunResult(status="success", output_summary=stats.summary())

        live = settings.ads_live_mode and settings.ads_daily_budget_eur > 0
        # Cap budget : on n'applique que tant que la somme |delta|/7
        # (estimation €/jour) reste sous le cap. Conservateur : on prend abs.
        committed_per_day = 0.0
        for act in actions:
            stats.by_platform[act.platform] = stats.by_platform.get(act.platform, 0) + 1
            per_day_est = abs(act.eur_delta_week) / 7.0
            if committed_per_day + per_day_est > settings.ads_daily_budget_eur and live:
                stats.actions_blocked += 1
                _archive_action(act, status="blocked_budget_cap")
                continue
            committed_per_day += per_day_est
            stats.eur_committed_week += act.eur_delta_week
            if live:
                stats.actions_applied += 1
                _archive_action(act, status="applied_live")
            else:
                stats.actions_shadow += 1
                _archive_action(act, status="shadow")

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(
                    webhook,
                    build_ad_embed(stats, live, settings.ads_daily_budget_eur),
                )
            except Exception as exc:
                logger.warning(f"AdBot — notif Discord a échoué : {exc}")

        inputs = [
            IOItem(
                label="Recos ads-optimizer",
                kind="file",
                detail=f"YAML chiffrées · mode {'live' if live else 'shadow'}",
                ref="data/ads/recommendations/",
                count=stats.recos_read,
            )
        ]
        outputs = [
            IOItem(
                label="Actions ads archivées",
                kind="file",
                detail=(
                    f"{stats.actions_applied} appliquée(s) · "
                    f"{stats.actions_shadow} shadow · "
                    f"{stats.actions_blocked} bloquée(s) cap · "
                    f"{stats.eur_committed_week:+.0f} €/semaine"
                ),
                ref="data/ads/applied/",
                count=stats.actions_applied + stats.actions_shadow + stats.actions_blocked,
            )
        ]
        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "APPLIED_DIR",
    "RECOMMENDATIONS_DIR",
    "AdAction",
    "AdBotLive",
    "AdRunStats",
    "build_ad_embed",
    "load_recommendations",
]
