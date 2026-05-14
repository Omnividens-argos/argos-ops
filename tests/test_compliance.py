"""Tests unitaires des helpers conformité (P17).

Garantit que le check :func:`is_human_response_requested` reste
fidèle aux engagements publics dans ``data/legal/ai-disclosure.md`` § 5.2.
Si un test fail après modification du module, c'est qu'on est en train
de violer le contrat — pas de skip, pas de tolérance, on corrige.
"""

from __future__ import annotations

import pytest

from argos_ops.compliance import is_human_response_requested


# =============================================================================
# True cases — toutes les variantes documentées AI Act § 5.2
# =============================================================================
@pytest.mark.parametrize(
    "subject",
    [
        "Réponse humaine SVP",
        "REPONSE HUMAINE",
        "réponse humaine",
        "Re: question — un humain SVP",
        "human reply please",
        "Talk to a human",
        "no bot please",
    ],
)
def test_match_in_subject(subject: str) -> None:
    assert is_human_response_requested(subject=subject, body="bla bla bla")


@pytest.mark.parametrize(
    "body",
    [
        "Bonjour, je préfère une réponse humaine SVP, pas une IA.",
        "Hi team, please no AI on this thread, human reply preferred.",
        "Pas de bot stp, je veux parler à un humain.",
        "Speak to a human, this is important.",
    ],
)
def test_match_in_body(body: str) -> None:
    assert is_human_response_requested(subject="Question sur Argos", body=body)


def test_match_with_accents_normalized() -> None:
    """« RÉPONSE HUMAINE » (majuscules + accents) doit matcher comme « reponse humaine »."""
    assert is_human_response_requested(subject="RÉPONSE HUMAINE", body="")


def test_match_with_punctuation_around() -> None:
    """« réponse humaine. » doit matcher (limite par \\W)."""
    assert is_human_response_requested(subject="OK, réponse humaine.", body="")


def test_match_anywhere_in_body_window() -> None:
    """Phrase dans les 500 premiers chars du body → match."""
    body = "Pad pad pad " * 30 + "no AI please, this is important."
    assert is_human_response_requested(subject="hello", body=body)


# =============================================================================
# False cases — pas de faux positif sur des sous-chaînes
# =============================================================================
def test_no_match_on_empty_inputs() -> None:
    assert not is_human_response_requested(subject="", body="")


def test_no_match_on_unrelated_email() -> None:
    assert not is_human_response_requested(
        subject="Question sur Argos",
        body="Bonjour, j'aimerais savoir si vous supportez les scans GitHub Actions.",
    )


def test_no_match_on_substring_in_word() -> None:
    """« human » dans « inhumane » ne doit pas matcher la phrase « human reply »."""
    assert not is_human_response_requested(
        subject="inhumane workload",
        body="My team's inhumane workload is killing us. Any thoughts?",
    )


def test_no_match_on_no_ai_in_word() -> None:
    """« no AI » dans « no Angular » ne doit pas matcher."""
    assert not is_human_response_requested(
        subject="Question",
        body="Nous n'avons pas d'Angular front, juste du React.",
    )


def test_no_match_when_phrase_is_in_signature_disclaimer() -> None:
    """Si la phrase apparaît au-delà de la fenêtre 500 chars (signature
    corporate type « Powered by HubSpot AI — no AI used in this email »),
    on doit l'ignorer."""
    long_body = ("Hello, just a regular email. " * 30) + " no AI used in this email."
    assert len(long_body) > 500
    assert not is_human_response_requested(
        subject="hello",
        body=long_body,
        body_window_chars=500,
    )


# =============================================================================
# Edge cases
# =============================================================================
def test_subject_only_with_empty_body() -> None:
    assert is_human_response_requested(subject="Réponse humaine SVP", body="")


def test_body_only_with_empty_subject() -> None:
    assert is_human_response_requested(
        subject="",
        body="Réponse humaine SVP, je veux pas d'IA.",
    )


def test_body_window_param_is_respected() -> None:
    """body_window_chars=10 → ne regarde que les 10 premiers chars du body.
    Si la phrase est au char 100, elle ne doit pas matcher."""
    body = "x" * 50 + " no bot please"
    assert not is_human_response_requested(
        subject="hello",
        body=body,
        body_window_chars=10,
    )
