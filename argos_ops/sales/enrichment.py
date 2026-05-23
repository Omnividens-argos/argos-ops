"""Heuristiques d'enrichissement BtoB — port Python du skill ``lead-enricher``.

Le skill markdown ``.claude/skills/lead-enricher/`` est invoqué via slash
command pour un seul lead (humain-in-the-loop). Ce module Python sert
``LeadEnricher`` (agent cron) qui pré-traite l'inbox CSV entière de
façon non-interactive.

Tout est déterministe et offline (D-017) :

- Génération de candidats email à partir de 5 patterns scorés
  (``firstname.lastname > firstname > flastname > ...``)
- Scoring persona Marc / Sarah / Thomas via mots-clés du titre
- Scoring BANT 0-100 depuis (taille boîte hint, titre, signaux ICP)

Pas d'appel Apollo / Hunter / Clearbit (option payante P13.B si
budget — pas dans le périmètre du Sprint 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PersonaName = Literal["marc", "sarah", "thomas", "unknown"]


@dataclass(frozen=True)
class EmailGuess:
    """Un candidat email pro avec confidence relative.

    ``confidence`` ∈ [0, 100] — pas une probabilité vérifiable, juste
    un ordre stable parmi les guesses. ``firstname.lastname`` reste le
    pattern dominant BtoB FR (~70% des cas).
    """

    email: str
    pattern: str  # libellé humain du pattern utilisé
    confidence: int


@dataclass(frozen=True)
class PersonaHint:
    """Persona ICP probable + raison."""

    name: PersonaName
    score: int  # 0-100
    matched_keywords: tuple[str, ...]


@dataclass(frozen=True)
class BANTScore:
    """Score BANT global 0-100 + sous-scores explicables."""

    budget: int
    authority: int
    need: int
    timing: int
    total: int

    @property
    def is_qualified(self) -> bool:
        """``True`` si total ≥ 40 (seuil ``/draft-outbound`` P13.A)."""
        return self.total >= 40


# =============================================================================
# Email guessing
# =============================================================================
_CLEAN_RE = re.compile(r"[^a-z0-9]")


def _clean(token: str) -> str:
    """Lowercase + strip accents naïf + retire tout sauf [a-z0-9]."""
    # Normalisation accents : remplacer les chars connus FR/EN basiques sans
    # importer unicodedata (volontairement léger).
    replacements = {
        "à": "a",
        "â": "a",
        "ä": "a",
        "ç": "c",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ÿ": "y",
        "ñ": "n",
    }
    lowered = token.lower()
    for src, dst in replacements.items():
        lowered = lowered.replace(src, dst)
    return _CLEAN_RE.sub("", lowered)


def _split_name(full_name: str) -> tuple[str, str] | None:
    """Retourne ``(first, last)`` ou ``None`` si ambigu."""
    parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if len(parts) < 2:
        return None
    first = _clean(parts[0])
    last = _clean(parts[-1])
    if not first or not last:
        return None
    return first, last


def guess_emails(full_name: str, domain: str) -> list[EmailGuess]:
    """Produit 5 candidats email scorés par pattern dominance BtoB FR.

    Confidences calibrées à partir des stats publiques (Hunter.io
    blog 2023) — ordre stable, somme non-normalisée. Le but est le
    *ranking*, pas la probabilité absolue.
    """
    split = _split_name(full_name)
    if split is None:
        return []
    first, last = split
    f = first[0]
    candidates = [
        (f"{first}.{last}@{domain}", "firstname.lastname", 70),
        (f"{first}@{domain}", "firstname", 50),
        (f"{f}{last}@{domain}", "flastname", 35),
        (f"{first}_{last}@{domain}", "firstname_lastname", 18),
        (f"{first}-{last}@{domain}", "firstname-lastname", 12),
    ]
    return [EmailGuess(email=e, pattern=p, confidence=c) for e, p, c in candidates]


# =============================================================================
# Persona scoring
# =============================================================================
_PERSONA_KEYWORDS: dict[PersonaName, tuple[str, ...]] = {
    "marc": (
        # CTO / RSSI / Tech Lead — décideur cyber
        "ciso",
        "rssi",
        "cto",
        "vp engineering",
        "vp eng",
        "head of security",
        "responsable securite",
        "responsable sécurité",
        "security manager",
        "head of it",
    ),
    "sarah": (
        # Founder / CEO — petite équipe, achat direct
        "ceo",
        "founder",
        "co-founder",
        "cofondateur",
        "président",
        "dirigeant",
        "gérant",
        "managing director",
    ),
    "thomas": (
        # Dev / Lead dev — utilisateur produit
        "lead developer",
        "lead dev",
        "senior developer",
        "engineering manager",
        "head of engineering",
        "tech lead",
        "developpeur senior",
        "développeur senior",
    ),
}


def score_persona(title: str | None) -> PersonaHint:
    """Devine le persona ICP depuis le titre de poste.

    Match case-insensitive sur un dictionnaire de mots-clés fixe.
    Retourne ``"unknown"`` si aucun match — c'est volontaire, ne pas
    inventer un persona depuis rien.
    """
    if not title:
        return PersonaHint(name="unknown", score=0, matched_keywords=())
    title_lower = title.lower()
    best: PersonaHint = PersonaHint(name="unknown", score=0, matched_keywords=())
    for persona, keywords in _PERSONA_KEYWORDS.items():
        matched = tuple(kw for kw in keywords if kw in title_lower)
        if matched:
            score = min(100, 40 + 20 * len(matched))
            if score > best.score:
                best = PersonaHint(name=persona, score=score, matched_keywords=matched)
    return best


# =============================================================================
# BANT
# =============================================================================
def score_bant(
    *,
    title: str | None,
    company_size_hint: int | None = None,
    has_recent_breach: bool = False,
    has_recent_ciso_hire: bool = False,
    has_recent_fundraise: bool = False,
) -> BANTScore:
    """Calcule un score BANT (Budget/Authority/Need/Timing) 0-100.

    Heuristiques (calibrées sur l'ICP ``data/knowledge_base/ICP.md``) :

    - **Budget** : taille boîte. < 20 emp = 10, 20-49 = 25, 50-249 = 30,
      ≥ 250 = 25 (trop gros = cycle long, sweet spot 50-249).
    - **Authority** : persona Marc/Sarah = 25, Thomas = 15, unknown = 5.
    - **Need** : breach récent → 25, sinon 10.
    - **Timing** : CISO hire ou levée → 20, sinon 5.
    """
    persona = score_persona(title)
    if persona.name in {"marc", "sarah"}:
        authority = 25
    elif persona.name == "thomas":
        authority = 15
    else:
        authority = 5

    if company_size_hint is None:
        budget = 15
    elif company_size_hint < 20:
        budget = 10
    elif company_size_hint < 50:
        budget = 25
    elif company_size_hint < 250:
        budget = 30
    else:
        budget = 25

    need = 25 if has_recent_breach else 10
    timing = 20 if (has_recent_ciso_hire or has_recent_fundraise) else 5

    total = min(100, budget + authority + need + timing)
    return BANTScore(budget=budget, authority=authority, need=need, timing=timing, total=total)


# =============================================================================
# Enrichment façade
# =============================================================================
def enrich_lead(
    *,
    full_name: str,
    domain: str,
    title_hint: str | None = None,
    company_size_hint: int | None = None,
    has_recent_breach: bool = False,
    has_recent_ciso_hire: bool = False,
    has_recent_fundraise: bool = False,
) -> dict[str, object]:
    """Pipeline complet — retourne le dict serializable d'un lead enrichi.

    Cette façade est ce que ``LeadEnricher`` (agent) appelle pour
    chaque ligne du CSV inbox et sérialise dans
    ``data/outbound/enriched/<slug>.md``.
    """
    emails = guess_emails(full_name, domain)
    persona = score_persona(title_hint)
    bant = score_bant(
        title=title_hint,
        company_size_hint=company_size_hint,
        has_recent_breach=has_recent_breach,
        has_recent_ciso_hire=has_recent_ciso_hire,
        has_recent_fundraise=has_recent_fundraise,
    )
    return {
        "full_name": full_name,
        "domain": domain,
        "title_hint": title_hint,
        "email_guesses": [
            {"email": e.email, "pattern": e.pattern, "confidence": e.confidence} for e in emails
        ],
        "persona": {
            "name": persona.name,
            "score": persona.score,
            "matched_keywords": list(persona.matched_keywords),
        },
        "bant": {
            "budget": bant.budget,
            "authority": bant.authority,
            "need": bant.need,
            "timing": bant.timing,
            "total": bant.total,
            "is_qualified": bant.is_qualified,
        },
    }


__all__ = [
    "BANTScore",
    "EmailGuess",
    "PersonaHint",
    "PersonaName",
    "enrich_lead",
    "guess_emails",
    "score_bant",
    "score_persona",
]
