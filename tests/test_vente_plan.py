"""Tests du plan d'actions du pôle Vente (archi v2, S4) — routing + gel Bloctel."""

from __future__ import annotations

from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.vente.plan import plan_actions


def _rec(
    kind: str, *, tags: tuple[str, ...] = (), important: bool = False, body: str = "x"
) -> MemoryRecord:
    return MemoryRecord(
        id=f"{kind}{tags}",
        pole="vente",
        script="s",
        kind=kind,
        body=body,
        important=important,
        tags=tags,
    )


def test_empty() -> None:
    assert plan_actions([], outbound_frozen=False) == []


def test_ticket_p0_critical() -> None:
    plans = plan_actions([_rec("ticket", tags=("P0", "critical"))], outbound_frozen=False)
    assert plans[0].severity == "critical" and plans[0].kind == "ticket"


def test_health_red_account() -> None:
    plans = plan_actions(
        [_rec("health", tags=("red", "critical"), important=True)], outbound_frozen=False
    )
    assert plans[0].kind == "account" and plans[0].severity == "critical"


def test_inbound_human_critical() -> None:
    plans = plan_actions(
        [_rec("inbound", tags=("autre", "human_requested", "critical"))], outbound_frozen=False
    )
    assert "HUMAINE" in plans[0].action


def test_lead_outreach_suppressed_when_frozen() -> None:
    rec = _rec("lead", tags=("marc", "qualified"), important=True)
    free = plan_actions([rec], outbound_frozen=False)[0]
    frozen = plan_actions([rec], outbound_frozen=True)[0]
    assert free.kind == "outreach" and free.suppressed_by_compliance is False
    assert frozen.suppressed_by_compliance is True


def test_buying_signal_suppressed_when_frozen() -> None:
    rec = _rec("intent_signal", tags=("intent",), important=True)
    frozen = plan_actions([rec], outbound_frozen=True)[0]
    assert frozen.kind == "outreach" and frozen.suppressed_by_compliance is True


def test_meeting_and_argument_info() -> None:
    plans = plan_actions(
        [_rec("meeting", tags=("drafted",)), _rec("regulatory", tags=())], outbound_frozen=False
    )
    kinds = {p.kind for p in plans}
    assert kinds == {"meeting", "argument"}


def test_unactionable_kind_skipped() -> None:
    assert (
        plan_actions([_rec("prospect"), _rec("outbound", tags=("shadow",))], outbound_frozen=False)
        == []
    )
