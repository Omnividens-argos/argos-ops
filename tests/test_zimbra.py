"""Tests unitaires du wrapper IMAP/SMTP OVH Zimbra.

Couvrent les helpers déterministes (is_noreply, extract_domain). Les
appels IMAP/SMTP réels sont validés en intégration via test live D-005.
"""

from __future__ import annotations

import pytest

from argos_ops.integrations.zimbra import (
    build_signature_html,
    build_signature_text,
    extract_domain,
    is_noreply,
)


# =============================================================================
# is_noreply
# =============================================================================
@pytest.mark.parametrize(
    "addr",
    [
        "noreply@example.com",
        "no-reply@example.com",
        "donotreply@example.com",
        "do-not-reply@example.com",
        "mailer-daemon@example.com",
        "postmaster@example.com",
        "bounces@example.com",
        "bounce@example.com",
        "  NoReply@Example.COM  ",  # case + trim
    ],
)
def test_is_noreply_detects_auto_senders(addr: str) -> None:
    assert is_noreply(addr) is True


@pytest.mark.parametrize(
    "addr",
    [
        "marc.dupont@bank.fr",
        "ciso@example.com",
        "contact@omnividens.fr",
        "support@vendor.io",
        "",
    ],
)
def test_is_noreply_passes_normal_senders(addr: str) -> None:
    assert is_noreply(addr) is False


# =============================================================================
# extract_domain
# =============================================================================
def test_extract_domain_simple() -> None:
    assert extract_domain("marc@bank.fr") == "bank.fr"


def test_extract_domain_uppercase_normalised() -> None:
    assert extract_domain("Marc@BANK.fr") == "bank.fr"


def test_extract_domain_with_brackets() -> None:
    """Forme parfois rencontrée dans les headers : ``<addr@dom.com>``."""
    assert extract_domain("Marc Dupont <marc@bank.fr>") == "bank.fr"


def test_extract_domain_returns_none_for_invalid() -> None:
    assert extract_domain("not-an-email") is None
    assert extract_domain("") is None


def test_extract_domain_returns_none_for_empty_domain() -> None:
    assert extract_domain("user@") is None


# =============================================================================
# Signature (text + HTML)
# =============================================================================
def test_signature_text_brutalist_mono_format() -> None:
    """Format brutaliste mono : header crochets + lignes préfixées >."""
    sig = build_signature_text(
        contact_email="contact@omnividens.fr",
        tagline="Argos — on scanne, vous corrigez.",
        site_url="https://omnividens.fr",
        ai_disclosure="Email rédigé par notre assistant Argos Ops.",
    )
    assert "[ ARGOS // OMNIVIDENS ]" in sig
    # Le préfixe « Argos — » est retiré pour éviter la redondance
    assert "> on scanne, vous corrigez." in sig
    assert "> contact@omnividens.fr" in sig
    assert "> https://omnividens.fr" in sig
    assert "# Email rédigé par notre assistant Argos Ops." in sig


def test_signature_text_keeps_tagline_when_no_brand_prefix() -> None:
    """Tagline custom sans préfixe ``Argos — `` doit être préservée telle quelle."""
    sig = build_signature_text(
        contact_email="x@y.fr",
        tagline="Le pentest qui voit tout.",
        site_url="https://y.fr",
        ai_disclosure="d",
    )
    assert "> Le pentest qui voit tout." in sig


def test_signature_html_brutalist_mono_format() -> None:
    html = build_signature_html(
        contact_email="contact@omnividens.fr",
        tagline="Argos — on scanne, vous corrigez.",
        site_url="https://omnividens.fr",
        ai_disclosure="Email rédigé par notre assistant Argos Ops.",
    )
    assert "[ ARGOS // OMNIVIDENS ]" in html
    assert "&gt; on scanne, vous corrigez." in html
    assert 'href="mailto:contact@omnividens.fr"' in html
    assert 'href="https://omnividens.fr"' in html
    assert "omnividens.fr</a>" in html  # site_label sans préfixe https://
    assert "# Email rédigé par notre assistant Argos Ops." in html
    # Style brutaliste : police monospace + fond grisé
    assert "monospace" in html
    assert "#fafafa" in html
    assert "<script" not in html.lower()


def test_signature_text_no_trailing_double_newline() -> None:
    """La signature doit être propre (pas de blanc final excessif)."""
    sig = build_signature_text(
        contact_email="x@y.fr", tagline="t", site_url="https://y.fr", ai_disclosure="d"
    )
    assert not sig.endswith("\n\n\n")
