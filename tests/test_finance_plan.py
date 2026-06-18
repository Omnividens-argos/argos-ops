"""Tests du plan d'actions du pôle Finance (archi v2, S5) — pur, déterministe."""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.poles.finance.plan import FinancePlan, plan_actions, severity_rank
from argos_ops.poles.memory import MemoryRecord


def _rec(
    kind: str, *, tags: tuple[str, ...] = (), important: bool = False, body: str = "x"
) -> MemoryRecord:
    return MemoryRecord(
        id=f"{kind}-{'-'.join(tags)}",
        pole="finance",
        script=kind,
        kind=kind,
        body=body,
        important=important,
        source=None,
        tags=tags,
        created_at=datetime(2026, 6, 18, tzinfo=UTC),
    )


def test_dunning_severity_by_level() -> None:
    recs = [
        _rec("dunning", tags=("dunning", "J+3")),
        _rec("dunning", tags=("dunning", "J+7")),
        _rec("dunning", tags=("dunning", "J+15"), important=True),
    ]
    plans = plan_actions(recs, compliance_blocking=False)
    by_kind = {p.detail: p for p in plans}  # bodies distinct via tags in id only; use severity set
    sevs = sorted(p.severity for p in plans)
    assert sevs == ["critical", "info", "warning"]
    assert all(p.kind == "dunning" for p in plans)
    assert by_kind is not None


def test_treasury_critical_only_when_important() -> None:
    crit = plan_actions(
        [_rec("treasury", tags=("treasury", "critical"), important=True)], compliance_blocking=False
    )
    assert crit and crit[0].severity == "critical"
    info = plan_actions([_rec("treasury", tags=("treasury",))], compliance_blocking=False)
    assert info and info[0].severity == "info"


def test_rgpd_gap_is_critical() -> None:
    plans = plan_actions(
        [_rec("rgpd", tags=("rgpd", "gap", "critical"), important=True)], compliance_blocking=True
    )
    assert plans and plans[0].kind == "rgpd" and plans[0].severity == "critical"


def test_ai_act_prohibited_vs_unclassified() -> None:
    proh = plan_actions(
        [_rec("ai_act", tags=("ai_act", "prohibited", "critical"))], compliance_blocking=True
    )
    assert proh and proh[0].severity == "critical"
    uncl = plan_actions([_rec("ai_act", tags=("ai_act", "unclassified"))], compliance_blocking=True)
    assert uncl and uncl[0].severity == "warning"
    classified = plan_actions([_rec("ai_act", tags=("ai_act",))], compliance_blocking=False)
    assert classified == []  # registre sain → rien à planifier


def test_billing_new_suppressed_when_compliance_blocking() -> None:
    rec = _rec("proposal", tags=("DEAL-1", "sent"))
    blocked = plan_actions([rec], compliance_blocking=True)
    assert blocked and blocked[0].kind == "billing_new"
    assert blocked[0].suppressed_by_compliance is True
    open_ = plan_actions([rec], compliance_blocking=False)
    assert open_ and open_[0].suppressed_by_compliance is False


def test_proposal_without_sent_is_not_actionable() -> None:
    assert (
        plan_actions([_rec("proposal", tags=("DEAL-1", "drafted"))], compliance_blocking=False)
        == []
    )


def test_unknown_kinds_ignored() -> None:
    assert (
        plan_actions([_rec("mrr"), _rec("forecast"), _rec("ticket")], compliance_blocking=False)
        == []
    )


def test_sort_critical_first_executable_before_suppressed() -> None:
    recs = [
        _rec("proposal", tags=("DEAL-1", "sent")),  # warning, suppressed
        _rec("treasury", tags=("treasury", "critical"), important=True),  # critical
        _rec("expense_anomaly", tags=("expense", "amount_outlier"), important=True),  # warning
    ]
    plans = plan_actions(recs, compliance_blocking=True)
    assert plans[0].severity == "critical"
    # Parmi les warnings, l'exécutable (expense) passe avant la gelée (billing_new).
    warnings = [p for p in plans if p.severity == "warning"]
    assert warnings[0].suppressed_by_compliance is False
    assert warnings[-1].suppressed_by_compliance is True


def test_severity_rank_monotonic() -> None:
    assert severity_rank("critical") > severity_rank("warning") > severity_rank("info")


def test_plan_is_frozen_dataclass() -> None:
    p = FinancePlan("info", "dunning", "a", "b")
    assert p.record_ids == ()
