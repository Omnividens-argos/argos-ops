"""Tests outreach du pôle Vente (archi v2, S4) — enrichissement, éligibilité, Bloctel."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.outbound.models import LeadInput
from argos_ops.poles.vente import outreach


def _write_leads(root: Path, body: str) -> None:
    d = root / "vente" / "outbound" / "inbox"
    d.mkdir(parents=True, exist_ok=True)
    (d / "leads.csv").write_text(body, encoding="utf-8")


def _write_phones(root: Path, body: str) -> None:
    d = root / "vente" / "compliance"
    d.mkdir(parents=True, exist_ok=True)
    (d / "lead_phones.csv").write_text(body, encoding="utf-8")


def _write_bloctel(root: Path, name: str, body: str) -> None:
    d = root / "vente" / "compliance" / "bloctel"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def test_enrich_view_eligible() -> None:
    e = outreach.enrich_view(
        LeadInput(full_name="Marc Dupont", domain="acme-securite.fr", title_hint="CISO")
    )
    assert e.persona == "marc"
    assert e.qualified is True
    assert e.eligible is True
    assert e.best_email == "marc.dupont@acme-securite.fr"


def test_enrich_view_personal_email_ineligible() -> None:
    e = outreach.enrich_view(
        LeadInput(full_name="Jean Bricoleur", domain="gmail.com", title_hint="Gérant")
    )
    assert e.eligible is False
    assert "perso" in e.eligibility_reason


def test_eligibility_bant_floor() -> None:
    ok, _ = outreach.eligibility(best_email="x@corp.fr", bant_total=45)
    assert ok is True
    no, reason = outreach.eligibility(best_email="x@corp.fr", bant_total=30)
    assert no is False and "BANT" in reason


def test_eligibility_missing_email_blocks() -> None:
    # Nom ambigu ⇒ aucune adresse devinable : inéligible même si BANT élevé.
    no, reason = outreach.eligibility(best_email=None, bant_total=90)
    assert no is False and "non identifiable" in reason


def test_enrich_view_ambiguous_name_ineligible() -> None:
    # Un nom mono-token ne produit aucun guess email → best_email None → inéligible.
    e = outreach.enrich_view(LeadInput(full_name="Cher", domain="corp.fr", title_hint="CEO"))
    assert e.best_email is None
    assert e.eligible is False


def test_enrich_and_write_then_load(tmp_path: Path) -> None:
    e = outreach.enrich_and_write(
        LeadInput(full_name="Sarah Martin", domain="techstart.io", title_hint="CEO"),
        poles_root=tmp_path,
    )
    loaded = outreach.load_enriched(poles_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].slug == e.slug
    assert loaded[0].persona == "sarah"


def test_append_leads_dedup(tmp_path: Path) -> None:
    _write_leads(tmp_path, "full_name,domain,title_hint,linkedin_url\nMarc Dupont,acme.fr,CISO,\n")
    added, skipped = outreach.append_leads(
        [
            LeadInput(full_name="Marc Dupont", domain="acme.fr"),  # doublon
            LeadInput(full_name="Claire Moreau", domain="secure-corp.fr", title_hint="RSSI"),
            LeadInput(full_name="Bad", domain="not-a-domain"),  # domaine invalide
        ],
        poles_root=tmp_path,
    )
    assert len(added) == 1 and added[0].full_name == "Claire Moreau"
    assert skipped == 2


def test_bloctel_no_phones_not_frozen(tmp_path: Path) -> None:
    _write_bloctel(tmp_path, "bloctel_2026-06.txt", "+33699000001\n")
    rep = outreach.build_bloctel_report(poles_root=tmp_path, today=date(2026, 6, 17))
    assert rep.should_alert is False  # Bloctel N/A sans téléphone
    assert outreach.outbound_frozen(poles_root=tmp_path, today=date(2026, 6, 17)) is False


def test_bloctel_match_freezes(tmp_path: Path) -> None:
    _write_phones(tmp_path, "identifier,phone\nlead-a,+33611223344\n")
    _write_bloctel(tmp_path, "bloctel_2026-06.txt", "+33611223344\n")
    rep = outreach.build_bloctel_report(poles_root=tmp_path, today=date(2026, 6, 17))
    assert rep.should_alert is True and len(rep.matches) == 1
    assert outreach.outbound_frozen(poles_root=tmp_path, today=date(2026, 6, 17)) is True


def test_bloctel_stale_with_phones_freezes(tmp_path: Path) -> None:
    _write_phones(tmp_path, "identifier,phone\nlead-a,+33611223344\n")
    _write_bloctel(tmp_path, "bloctel_2026-04.txt", "+33699999999\n")  # > 35j
    rep = outreach.build_bloctel_report(poles_root=tmp_path, today=date(2026, 6, 17))
    assert rep.stale is True and rep.should_alert is True


def test_bloctel_phones_but_no_list_freezes(tmp_path: Path) -> None:
    _write_phones(tmp_path, "identifier,phone\nlead-a,+33611223344\n")
    rep = outreach.build_bloctel_report(poles_root=tmp_path, today=date(2026, 6, 17))
    assert rep.list_path is None and rep.should_alert is True


def test_bloctel_unparseable_list_name_freezes_with_clean_summary(tmp_path: Path) -> None:
    _write_phones(tmp_path, "identifier,phone\nlead-a,+33611223344\n")
    _write_bloctel(tmp_path, "bloctel_invalid.txt", "+33699999999\n")  # nom non parsable
    rep = outreach.build_bloctel_report(poles_root=tmp_path, today=date(2026, 6, 17))
    assert rep.list_age_days is None and rep.should_alert is True
    assert "None" not in rep.summary and "illisible" in rep.summary


def test_scaffold_for_lead_idempotent(tmp_path: Path) -> None:
    lead = LeadInput(full_name="Marc Dupont", domain="acme.fr", title_hint="CISO")
    p1 = outreach.scaffold_for_lead(lead, poles_root=tmp_path)
    assert (p1 / "meta.yaml").exists()
    assert outreach.is_scaffolded("marc-dupont-acme-fr", poles_root=tmp_path)
    seqs = outreach.load_sequences(poles_root=tmp_path)
    assert len(seqs) == 1 and len(seqs[0].touches) == 5
