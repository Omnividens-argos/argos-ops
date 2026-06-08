"""AIActComplianceBot — AI Compliance Officer (P22.E Compliance Sprint 8).

Inventorie tous les agents Python qui héritent de :class:`BaseAgent` et
vérifie que chacun expose un attribut ``ai_act_risk_class`` valide
(``minimal`` / ``limited`` / ``high`` / ``prohibited``).

Politique anti-spam :
- **Silence** Discord si tous les agents sont classifiés
- **Embed jaune** si ≥1 agent ``unclassified``
- **Embed rouge** si ≥1 agent ``prohibited`` (incompatible AI Act art. 5)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 9 Compliance, Sprint 8.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from datetime import UTC, datetime

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.compliance import AIActRisk, classify_ai_act_risk
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField


@dataclass(frozen=True)
class AgentClassification:
    """Un agent + sa classification AI Act."""

    name: str
    module: str
    risk: AIActRisk


@dataclass(frozen=True)
class AIActComplianceReport:
    """Résultat agrégé du run AIActComplianceBot."""

    classifications: list[AgentClassification]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Discovery
# =============================================================================
def discover_agents(package_name: str = "argos_ops.agents") -> list[type[BaseAgent]]:
    """Importe tous les sous-modules de ``package_name`` et retourne les
    sous-classes concrètes de :class:`BaseAgent`.

    Skip les modules privés (commencent par ``_``) — ce sont des helpers
    (``_watcher_base``, etc.), pas des agents.
    """
    pkg = importlib.import_module(package_name)
    agents: list[type[BaseAgent]] = []
    seen: set[str] = set()
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package_name}.{info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseAgent)
                and obj is not BaseAgent
                and obj.__name__ not in seen
                and not inspect.isabstract(obj)
            ):
                seen.add(obj.__name__)
                agents.append(obj)
    return agents


def classify_all(agent_classes: list[type[BaseAgent]]) -> list[AgentClassification]:
    """Pour chaque agent, lit son attribut ``ai_act_risk_class`` et classifie."""
    out: list[AgentClassification] = []
    for cls in agent_classes:
        raw = getattr(cls, "ai_act_risk_class", None)
        risk = classify_ai_act_risk(raw)
        out.append(
            AgentClassification(
                name=getattr(cls, "name", cls.__name__),
                module=cls.__module__,
                risk=risk,
            )
        )
    return out


# =============================================================================
# Décision
# =============================================================================
def build_report(classifications: list[AgentClassification]) -> AIActComplianceReport:
    """Construit le report — RED si ``prohibited``, YELLOW si ``unclassified``."""
    has_prohibited = any(c.risk == "prohibited" for c in classifications)
    has_unclassified = any(c.risk == "unclassified" for c in classifications)

    if has_prohibited:
        alert_color = RED
        should_alert = True
    elif has_unclassified:
        alert_color = YELLOW
        should_alert = True
    else:
        alert_color = GREEN
        should_alert = False

    counts = {
        "minimal": sum(1 for c in classifications if c.risk == "minimal"),
        "limited": sum(1 for c in classifications if c.risk == "limited"),
        "high": sum(1 for c in classifications if c.risk == "high"),
        "prohibited": sum(1 for c in classifications if c.risk == "prohibited"),
        "unclassified": sum(1 for c in classifications if c.risk == "unclassified"),
    }
    summary = (
        f"{counts['minimal']} min · {counts['limited']} lim · "
        f"{counts['high']} high · {counts['prohibited']} PROH · "
        f"{counts['unclassified']} UNCL"
    )
    return AIActComplianceReport(
        classifications=classifications,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_RISK_ICON: dict[AIActRisk, str] = {
    "minimal": "[MIN]",
    "limited": "[LIM]",
    "high": "[HIGH]",
    "prohibited": "[PROH]",
    "unclassified": "[UNCL]",
}


def build_ai_act_embed(
    report: AIActComplianceReport, *, now: datetime | None = None
) -> Embed:
    """Embed Discord — un field par agent non conforme."""
    now = now or datetime.now(UTC)
    flagged = [c for c in report.classifications if c.risk in ("prohibited", "unclassified")]
    fields = [
        EmbedField(
            name=f"{_RISK_ICON[c.risk]} {c.name}",
            value=f"`{c.module}`",
            inline=False,
        )
        for c in flagged[:15]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"AIActComplianceBot — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • AIActComplianceBot",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class AIActComplianceBot(BaseAgent):
    """AI Compliance Officer — vérifie le tag AI Act sur chaque agent."""

    name = "AIActComplianceBot"
    command = "/run-ai-act-audit"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, package_name: str = "argos_ops.agents") -> None:
        self._package_name = package_name

    async def run(self) -> RunResult:
        agent_classes = discover_agents(self._package_name)
        classifications = classify_all(agent_classes)
        report = build_report(classifications)
        prohibited = [c for c in classifications if c.risk == "prohibited"]
        unclassified = [c for c in classifications if c.risk == "unclassified"]
        inputs = [
            IOItem(
                label="Agents Python découverts",
                kind="other",
                detail=f"sous-classes BaseAgent dans {self._package_name}",
                count=len(classifications),
            )
        ]
        outputs = [
            IOItem(
                label="Agents prohibited (AI Act art. 5)",
                kind="other",
                detail=", ".join(c.name for c in prohibited) or None,
                count=len(prohibited),
            ),
            IOItem(
                label="Agents non classifiés",
                kind="other",
                detail=", ".join(c.name for c in unclassified) or None,
                count=len(unclassified),
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_ai_act_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "AIActComplianceBot",
    "AIActComplianceReport",
    "AgentClassification",
    "build_ai_act_embed",
    "build_report",
    "classify_all",
    "discover_agents",
]
