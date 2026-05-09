"""Tests unitaires du wrapper IMAP/SMTP OVH Zimbra.

Couvrent les helpers déterministes (is_noreply, extract_domain). Les
appels IMAP/SMTP réels sont validés en intégration via test live D-005.
"""

from __future__ import annotations

import pytest

from argos_ops.integrations.zimbra import extract_domain, is_noreply


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
