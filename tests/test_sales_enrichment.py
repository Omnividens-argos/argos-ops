"""Tests unitaires de ``argos_ops.sales.enrichment`` (P22.H Sales Sprint 3).

Heuristiques offline → tests purement déterministes (zéro mock).
"""

from __future__ import annotations

from argos_ops.sales.enrichment import (
    enrich_lead,
    guess_emails,
    score_bant,
    score_persona,
)


def test_guess_emails_returns_5_candidates_for_complete_name() -> None:
    guesses = guess_emails("Marc Dupont", "acme.fr")
    assert len(guesses) == 5
    assert guesses[0].email == "marc.dupont@acme.fr"
    assert guesses[0].pattern == "firstname.lastname"
    assert guesses[0].confidence == 70


def test_guess_emails_handles_accents() -> None:
    guesses = guess_emails("Sarah Côté", "tech.io")
    assert guesses[0].email == "sarah.cote@tech.io"


def test_guess_emails_empty_for_single_name() -> None:
    assert guess_emails("Madonna", "acme.fr") == []


def test_score_persona_marc() -> None:
    p = score_persona("CISO chez Acme SA")
    assert p.name == "marc"
    assert p.score >= 40
    assert "ciso" in p.matched_keywords


def test_score_persona_sarah() -> None:
    p = score_persona("Founder & CEO")
    assert p.name == "sarah"
    assert p.score >= 60  # 2 keywords match → 80


def test_score_persona_thomas() -> None:
    p = score_persona("Tech Lead Backend")
    assert p.name == "thomas"


def test_score_persona_unknown_for_empty_title() -> None:
    assert score_persona(None).name == "unknown"
    assert score_persona("").name == "unknown"
    # Titre sans match dans le dictionnaire
    assert score_persona("Pâtissier").name == "unknown"


def test_score_bant_qualified_persona_marc_with_breach() -> None:
    bant = score_bant(
        title="CISO",
        company_size_hint=120,
        has_recent_breach=True,
        has_recent_ciso_hire=False,
        has_recent_fundraise=False,
    )
    # budget=30 + authority=25 + need=25 + timing=5 = 85
    assert bant.total == 85
    assert bant.is_qualified


def test_score_bant_below_threshold_with_unknown_persona() -> None:
    bant = score_bant(
        title=None,
        company_size_hint=10,
        has_recent_breach=False,
    )
    # budget=10 + authority=5 + need=10 + timing=5 = 30
    assert bant.total == 30
    assert not bant.is_qualified


def test_enrich_lead_returns_full_payload() -> None:
    payload = enrich_lead(
        full_name="Marc Dupont",
        domain="acme.fr",
        title_hint="CISO",
        company_size_hint=120,
    )
    assert payload["full_name"] == "Marc Dupont"
    assert payload["domain"] == "acme.fr"
    assert isinstance(payload["email_guesses"], list)
    assert len(payload["email_guesses"]) == 5
    assert payload["persona"]["name"] == "marc"
    assert payload["bant"]["total"] >= 40
