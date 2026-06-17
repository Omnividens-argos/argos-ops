"""Tests RDV + devis/contrats du pôle Vente (archi v2, S4)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.vente import meetings, proposals

_REQUESTS = (
    "requests:\n"
    "  - request_id: rdv-1\n    attendee_email: marc@acme.fr\n    attendee_name: Marc\n"
    "    company: Acme\n    starts_at: '2026-06-20T14:00:00+00:00'\n    duration_minutes: 30\n"
    "    status: pending\n"
)


def _write_requests(root: Path) -> None:
    d = root / "vente" / "meetings"
    d.mkdir(parents=True, exist_ok=True)
    (d / "requests.yaml").write_text(_REQUESTS, encoding="utf-8")


def test_book_meeting_writes_ics_and_draft(tmp_path: Path) -> None:
    _write_requests(tmp_path)
    draft = meetings.book_meeting("rdv-1", poles_root=tmp_path)
    assert draft is not None and draft.exists()
    ics = draft.with_suffix(".ics")
    assert ics.exists()
    assert "BEGIN:VCALENDAR" in ics.read_text(encoding="utf-8")
    # statut flippé à drafted → plus pending
    reqs = meetings.load_requests(poles_root=tmp_path)
    assert reqs[0].status == "drafted"
    assert meetings.pending(reqs) == []


def test_book_meeting_unknown(tmp_path: Path) -> None:
    _write_requests(tmp_path)
    assert meetings.book_meeting("nope", poles_root=tmp_path) is None


def _write_proposal(root: Path, deal_id: str, status: str | None) -> None:
    d = root / "vente" / "proposals" / deal_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "context.yaml").write_text(
        f"deal_id: {deal_id}\ncompany: Acme\ncontact_name: Marc\n"
        "contact_email: marc@acme.fr\nplan: Argos Pro\nmonthly_price_eur: 350\n"
        "issue_date: '2026-06-01'\n",
        encoding="utf-8",
    )
    if status is not None:
        (d / "status.yaml").write_text(f"proposal_status: {status}\n", encoding="utf-8")


def test_render_proposal_sets_drafted(tmp_path: Path) -> None:
    _write_proposal(tmp_path, "D1", status=None)
    out = proposals.render_proposal_file("D1", poles_root=tmp_path)
    assert out is not None and out.exists()
    assert "Devis Argos" in out.read_text(encoding="utf-8")
    assert proposals.proposal_status("D1", poles_root=tmp_path) == "drafted"


def test_contract_gated_on_sent(tmp_path: Path) -> None:
    _write_proposal(tmp_path, "D1", status="drafted")
    assert proposals.render_contract_file("D1", poles_root=tmp_path) is None  # pas encore sent
    _write_proposal(tmp_path, "D2", status="sent")
    out = proposals.render_contract_file("D2", poles_root=tmp_path)
    assert out is not None and out.exists()
    assert "Contrat de prestation" in out.read_text(encoding="utf-8")


def test_load_entries(tmp_path: Path) -> None:
    _write_proposal(tmp_path, "D1", status="sent")
    proposals.render_proposal_file("D1", poles_root=tmp_path)
    proposals.render_contract_file("D1", poles_root=tmp_path)
    entries = proposals.load_entries(poles_root=tmp_path)
    assert len(entries) == 1
    assert entries[0].has_proposal and entries[0].has_contract
    assert entries[0].proposal_status == "sent"


def test_proposal_unknown(tmp_path: Path) -> None:
    assert proposals.render_proposal_file("ghost", poles_root=tmp_path) is None
