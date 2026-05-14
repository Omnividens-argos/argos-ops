"""Helpers de conformité RGPD / AI Act (P17).

Centralise les checks déterministes qu'on ne veut **pas** déléguer à un
LLM, parce qu'ils font partie du contrat légal avec l'utilisateur et
doivent être reproductibles à 100 %.

Premier check livré (P17, 2026-05-14) : :func:`is_human_response_requested`
— détecte qu'un email entrant demande explicitement une réponse humaine
(AI Act article 13 + notre engagement public ``data/legal/ai-disclosure.md``
§ 5.2). Quand le check est positif, EmailBot et ``/check-emails`` doivent
**court-circuiter** tout drafting IA et router en file Tier 2 humain.

Le check est :

- **Déterministe** — regex sur texte normalisé, pas d'appel LLM
- **Tolérant à la casse et aux accents** — « Réponse Humaine SVP »,
  « reponse humaine », « RÉPONSE HUMAINE » → tous matchent
- **Tolérant au bruit autour** — la phrase peut être au milieu d'un
  paragraphe ou en signature
- **Conservateur** — préfère un faux positif (humain réexamine pour
  rien) qu'un faux négatif (l'IA répond alors que l'user a demandé un
  humain → violation directe de notre disclosure)
"""

from __future__ import annotations

import re
import unicodedata

# Liste exhaustive des phrases déclencheuses. Synchronisée avec
# ``.claude/skills/email-classifier/SKILL.md`` § « Override AI Act § 5.2 ».
# Ajouter une variante = la mettre ici ET dans le SKILL.md, avec un
# commit qui mentionne explicitement P17 dans le message.
_HUMAN_REQUEST_PHRASES: tuple[str, ...] = (
    # FR
    "reponse humaine",
    "reponse par un humain",
    "reponse d'un humain",
    "un humain svp",
    "un humain s'il vous plait",
    "un humain s il vous plait",
    "pas de bot",
    "pas de chatbot",
    "pas d'ia",
    "pas d ia",
    "pas d'ai",
    "pas d ai",
    "parler a un humain",
    # EN
    "human reply",
    "human please",
    "talk to a human",
    "no bot",
    "no chatbot",
    "no ai",
    "speak to a human",
    "speak with a human",
)

# Fenêtre d'analyse côté body : on regarde les 500 premiers caractères
# après normalisation. Au-delà, on tombe sur des signatures email /
# disclaimers corporate qui faussent le check (« sent from my iPhone »,
# « powered by HubSpot AI », etc.). 500 chars couvrent largement
# l'intro où une demande de routage humain serait formulée.
_BODY_WINDOW_CHARS = 500


def _normalize(text: str) -> str:
    """Lowercase + retire les accents (NFD + drop combining marks)."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower()


def is_human_response_requested(
    *,
    subject: str,
    body: str,
    body_window_chars: int = _BODY_WINDOW_CHARS,
) -> bool:
    """Retourne ``True`` si l'email demande explicitement une réponse humaine.

    Couvre les patterns documentés dans ``data/legal/ai-disclosure.md`` § 5.2
    + variantes anglophones. Match case-insensitive sur texte normalisé sans
    accents, sur le sujet entier + les ``body_window_chars`` premiers
    caractères du corps.

    On utilise des regex avec délimiteurs ``\\b`` pour éviter les faux
    positifs sur des sous-chaînes ("no AI" doit matcher mais "no AIngular
    feedback" ne doit pas).
    """
    if not subject and not body:
        return False

    haystack_subject = _normalize(subject or "")
    haystack_body = _normalize((body or "")[:body_window_chars])
    haystack = f"{haystack_subject}\n{haystack_body}"

    for phrase in _HUMAN_REQUEST_PHRASES:
        normalized_phrase = _normalize(phrase)
        # \b ne suffit pas pour « pas d ia » (qui contient des espaces) ;
        # on entoure d'espaces ou de limites de chaîne pour rester strict.
        pattern = rf"(?:^|\W){re.escape(normalized_phrase)}(?:\W|$)"
        if re.search(pattern, haystack):
            return True
    return False


__all__ = [
    "is_human_response_requested",
]
