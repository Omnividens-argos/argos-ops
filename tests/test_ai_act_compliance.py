"""Tests unitaires de :mod:`argos_ops.agents.ai_act_compliance` (P22.E)."""

from __future__ import annotations

from argos_ops.agents.ai_act_compliance import (
    AgentClassification,
    build_report,
    classify_all,
    discover_agents,
)
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.notifications.discord import GREEN, RED, YELLOW


class _DummyMinimal(BaseAgent):
    name = "DummyMinimal"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        return RunResult(status="success")


class _DummyUnclassified(BaseAgent):
    name = "DummyUnclassified"

    async def run(self) -> RunResult:
        return RunResult(status="success")


class _DummyProhibited(BaseAgent):
    name = "DummyProhibited"
    ai_act_risk_class = "prohibited"

    async def run(self) -> RunResult:
        return RunResult(status="success")


# =============================================================================
# classify_all
# =============================================================================
def test_classify_all_reads_attribute() -> None:
    classifications = classify_all([_DummyMinimal, _DummyProhibited])
    by_name = {c.name: c.risk for c in classifications}
    assert by_name["DummyMinimal"] == "minimal"
    assert by_name["DummyProhibited"] == "prohibited"


def test_classify_all_unclassified_when_missing() -> None:
    classifications = classify_all([_DummyUnclassified])
    assert classifications[0].risk == "unclassified"


# =============================================================================
# build_report
# =============================================================================
def _cls(name: str, risk: str) -> AgentClassification:
    return AgentClassification(name=name, module="m", risk=risk)  # type: ignore[arg-type]


def test_build_report_green_all_classified() -> None:
    report = build_report([_cls("a", "minimal"), _cls("b", "limited")])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_with_unclassified() -> None:
    report = build_report([_cls("a", "minimal"), _cls("b", "unclassified")])
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_with_prohibited() -> None:
    report = build_report([_cls("a", "minimal"), _cls("b", "prohibited")])
    assert report.alert_color == RED
    assert report.should_alert is True


# =============================================================================
# discover_agents — smoke test contre le vrai package
# =============================================================================
def test_discover_agents_finds_known_classes() -> None:
    classes = discover_agents("argos_ops.agents")
    names = {c.__name__ for c in classes}
    # Smoke check : on attend au moins un agent connu existant en pré-P22.E
    assert "DigestBuilder" in names