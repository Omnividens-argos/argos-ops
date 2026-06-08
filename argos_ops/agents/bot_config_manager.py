"""BotConfigManager — Config Ops de la flotte (P22.C Meta-Ops Sprint 2).

Compare la table ``agent_config`` (modifiée via l'Admin Panel P16.B)
avec la baseline canonique stockée dans
``data/agent_config/baseline.yaml`` et alerte Discord sur les drifts.

Use cases typiques :
- Le fondateur a bumpé l'intensité de FinanceBot pour une journée et a
  oublié de la rebaisser → drift détecté
- Un agent a été désactivé manuellement et la décision n'a pas été
  reflétée dans la baseline → drift détecté
- Le daily_limit a été abaissé pour économiser du quota → drift détecté

Politique anti-spam :
- **Silence** Discord si aucun drift sur aucun agent
- **Embed jaune** si ≥1 drift bénin (intensity, daily_limit)
- **Embed rouge** si ≥1 drift critique (``enabled: false`` non baselined)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops, Sprint 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentConfig
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_BASELINE_PATH: Path = REPO_ROOT / "data" / "agent_config" / "baseline.yaml"

# Champs à comparer (autres champs de AgentConfig ignorés volontairement)
COMPARED_FIELDS: tuple[str, ...] = ("enabled", "intensity_level", "daily_limit")

# Drifts considérés critiques (alerte rouge)
CRITICAL_FIELDS: frozenset[str] = frozenset({"enabled"})


@dataclass(frozen=True)
class ConfigDrift:
    """Une différence baseline ↔ DB pour un agent + un champ."""

    agent_name: str
    field: str
    baseline_value: Any
    actual_value: Any


@dataclass(frozen=True)
class ConfigDriftReport:
    """Résultat agrégé du run BotConfigManager."""

    drifts: list[ConfigDrift]
    missing_in_db: list[str]  # agent listé baseline mais aucune row en DB
    missing_in_baseline: list[str]  # row en DB pour agent non listé baseline
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Lecture baseline
# =============================================================================
def load_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict[str, dict[str, Any]]:
    """Lit le YAML et retourne ``{agent_name: {field: value, ...}}``.

    Tolère un fichier vide ou absent (renvoie ``{}``) — l'agent
    n'alerte alors que sur les valeurs DB qui sont elles-mêmes
    intrinsèquement suspectes (``enabled=False``).
    """
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("agents", {}) or {}


# =============================================================================
# Comparaison
# =============================================================================
def _extract_field(config: AgentConfig, field: str) -> Any:
    return getattr(config, field)


async def _load_db_configs(session: AsyncSession) -> dict[str, AgentConfig]:
    stmt = select(AgentConfig)
    return {c.agent_name: c for c in (await session.execute(stmt)).scalars().all()}


async def collect_drifts(
    session: AsyncSession,
    *,
    baseline: dict[str, dict[str, Any]] | None = None,
) -> ConfigDriftReport:
    """Compare baseline et DB, retourne tous les drifts trouvés."""
    if baseline is None:
        baseline = load_baseline()

    db_configs = await _load_db_configs(session)
    drifts: list[ConfigDrift] = []
    missing_in_db: list[str] = []

    for agent_name, expected in baseline.items():
        actual_config = db_configs.get(agent_name)
        if actual_config is None:
            missing_in_db.append(agent_name)
            continue
        for field in COMPARED_FIELDS:
            if field not in expected:
                continue
            expected_value = expected[field]
            actual_value = _extract_field(actual_config, field)
            if expected_value != actual_value:
                drifts.append(
                    ConfigDrift(
                        agent_name=agent_name,
                        field=field,
                        baseline_value=expected_value,
                        actual_value=actual_value,
                    )
                )

    missing_in_baseline = sorted(set(db_configs.keys()) - set(baseline.keys()))

    has_critical = any(d.field in CRITICAL_FIELDS for d in drifts)
    should_alert = bool(drifts) or bool(missing_in_db)

    if has_critical:
        alert_color = RED
    elif should_alert:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    summary_parts = [f"{len(drifts)} drift(s)"]
    if missing_in_db:
        summary_parts.append(f"{len(missing_in_db)} missing in DB")
    if missing_in_baseline:
        summary_parts.append(f"{len(missing_in_baseline)} not baselined")
    summary = " · ".join(summary_parts)

    return ConfigDriftReport(
        drifts=drifts,
        missing_in_db=missing_in_db,
        missing_in_baseline=missing_in_baseline,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
def _format_drift_value(drift: ConfigDrift) -> str:
    return (
        f"`{drift.field}` baseline=`{drift.baseline_value!r}`"
        f" actual=`{drift.actual_value!r}`"
    )


def build_config_drift_embed(
    report: ConfigDriftReport, *, now: datetime | None = None
) -> Embed:
    """Construit l'embed Discord — un field par drift + 1 field pour missing."""
    now = now or datetime.now(UTC)

    fields: list[EmbedField] = []
    by_agent: dict[str, list[ConfigDrift]] = {}
    for drift in report.drifts:
        by_agent.setdefault(drift.agent_name, []).append(drift)
    for agent_name, drifts in by_agent.items():
        fields.append(
            EmbedField(
                name=f"[DRIFT] {agent_name}",
                value="\n".join(_format_drift_value(d) for d in drifts)[:1020],
                inline=False,
            )
        )

    if report.missing_in_db:
        fields.append(
            EmbedField(
                name="Missing in DB",
                value=", ".join(report.missing_in_db)[:1020],
                inline=False,
            )
        )
    if report.missing_in_baseline:
        fields.append(
            EmbedField(
                name="Not baselined",
                value=", ".join(report.missing_in_baseline)[:1020],
                inline=False,
            )
        )

    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BotConfigManager — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BotConfigManager",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class BotConfigManager(BaseAgent):
    """Config Ops — vérifie l'absence de drift agent_config ↔ baseline.yaml."""

    name = "BotConfigManager"
    command = "/run-config-drift"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, baseline_path: Path = DEFAULT_BASELINE_PATH) -> None:
        self._baseline_path = baseline_path

    async def run(self) -> RunResult:
        baseline = load_baseline(self._baseline_path)
        async with session_scope() as session:
            report = await collect_drifts(session, baseline=baseline)
        inputs = [
            IOItem(
                label="Baseline config canonique",
                kind="file",
                detail=str(self._baseline_path),
                ref=str(self._baseline_path),
                count=len(baseline),
            ),
            IOItem(
                label="Config agents en DB",
                kind="db",
                detail="agent_config (enabled / intensity / daily_limit)",
            ),
        ]
        outputs = [
            IOItem(
                label="Drifts détectés",
                kind="other",
                detail=", ".join(
                    f"{d.agent_name}.{d.field}" for d in report.drifts
                )
                or None,
                count=len(report.drifts),
            ),
            IOItem(
                label="Agents baselinés absents en DB",
                kind="other",
                detail=", ".join(report.missing_in_db) or None,
                count=len(report.missing_in_db),
            ),
            IOItem(
                label="Agents en DB non baselinés",
                kind="other",
                detail=", ".join(report.missing_in_baseline) or None,
                count=len(report.missing_in_baseline),
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_config_drift_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "COMPARED_FIELDS",
    "CRITICAL_FIELDS",
    "DEFAULT_BASELINE_PATH",
    "BotConfigManager",
    "ConfigDrift",
    "ConfigDriftReport",
    "build_config_drift_embed",
    "collect_drifts",
    "load_baseline",
]
