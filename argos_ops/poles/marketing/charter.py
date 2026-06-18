"""**Charte éditoriale / ton** du pôle Marketing (archi v2, S2).

Encode la voix de marque Argos que les skills writers respectent et que le
fondateur édite depuis le cockpit : tagline, domaine canonique, principes,
termes bannis (garde-fou **anti-FUD**), ligne de disclosure IA (AI Act § sur la
transparence). Stockée en ``data/poles/marketing/charter.yaml``.

:func:`brand_check` est le contrôle *déterministe* (« le LLM propose, Python
tranche ») réutilisé par le skill ``brand-check`` et le cockpit : il détecte les
écarts mécaniques (mauvais domaine ``.com``, terme anxiogène banni) sans appeler
de LLM. Aligné sur les conventions branding de CLAUDE.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

CHARTER_FILENAME = "charter.yaml"
MARKETING_POLE = "marketing"

# Valeurs par défaut = conventions branding canoniques (CLAUDE.md, mémoire
# signature). Servies si le fichier n'existe pas encore.
DEFAULT_TAGLINE = "Argos — on scanne, vous corrigez."
DEFAULT_DOMAIN = "omnividens.fr"
DEFAULT_VOICE = (
    "Direct, technique mais accessible, factuel. On rassure et on outille — "
    "jamais on ne fait peur. Pas de jargon gratuit, pas de superlatifs vides."
)
DEFAULT_PRINCIPLES: tuple[str, ...] = (
    "Pédagogie d'abord : expliquer la menace ET le réflexe de protection.",
    "Preuves chiffrées plutôt que promesses.",
    "Toujours citer le domaine canonique omnividens.fr.",
    "Mentionner que le contenu est assisté par IA (transparence AI Act).",
)
DEFAULT_AVOID: tuple[str, ...] = (
    "Le FUD (Fear, Uncertainty, Doubt) — pas de catastrophisme.",
    "Dénigrer nommément un concurrent.",
    "Promettre une sécurité « à 100 % » ou « inviolable ».",
)
# Termes anxiogènes / trompeurs proscrits (anti-FUD + anti-sur-promesse).
DEFAULT_BANNED_TERMS: tuple[str, ...] = (
    "catastrophe",
    "apocalypse",
    "inviolable",
    "100% sécurisé",
    "garantie totale",
    "panique",
)
DEFAULT_AI_DISCLOSURE = "Contenu rédigé avec l'assistance d'une IA."


@dataclass(frozen=True)
class Charter:
    """La charte éditoriale du pôle (voix de marque + garde-fous)."""

    tagline: str = DEFAULT_TAGLINE
    domain: str = DEFAULT_DOMAIN
    voice: str = DEFAULT_VOICE
    principles: tuple[str, ...] = DEFAULT_PRINCIPLES
    avoid: tuple[str, ...] = DEFAULT_AVOID
    banned_terms: tuple[str, ...] = DEFAULT_BANNED_TERMS
    ai_disclosure: str = DEFAULT_AI_DISCLOSURE


def charter_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MARKETING_POLE / CHARTER_FILENAME


def _as_tuple(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    return default


def load_charter(*, poles_root: Path = POLES_DIR) -> Charter:
    """Charge la charte (valeurs par défaut si le fichier est absent / vide)."""
    path = charter_path(poles_root=poles_root)
    if not path.exists():
        return Charter()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"charter — YAML invalide, défauts utilisés : {exc}")
        return Charter()
    if not isinstance(raw, dict):
        return Charter()
    return Charter(
        tagline=str(raw.get("tagline") or DEFAULT_TAGLINE),
        domain=str(raw.get("domain") or DEFAULT_DOMAIN),
        voice=str(raw.get("voice") or DEFAULT_VOICE),
        principles=_as_tuple(raw.get("principles"), DEFAULT_PRINCIPLES),
        avoid=_as_tuple(raw.get("avoid"), DEFAULT_AVOID),
        banned_terms=_as_tuple(raw.get("banned_terms"), DEFAULT_BANNED_TERMS),
        ai_disclosure=str(raw.get("ai_disclosure") or DEFAULT_AI_DISCLOSURE),
    )


def save_charter(charter: Charter, *, poles_root: Path = POLES_DIR) -> Charter:
    """Persiste la charte en YAML (crée le dossier du pôle au besoin)."""
    path = charter_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tagline": charter.tagline,
        "domain": charter.domain,
        "voice": charter.voice,
        "principles": list(charter.principles),
        "avoid": list(charter.avoid),
        "banned_terms": list(charter.banned_terms),
        "ai_disclosure": charter.ai_disclosure,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    logger.debug("charter — sauvegardée")
    return charter


# TLD « concurrents » du domaine canonique : citer ``omnividens.com`` / ``.io`` /
# ``.net`` … est un écart de marque (CLAUDE.md : « jamais .com »).
_WRONG_TLDS: frozenset[str] = frozenset({"com", "io", "net", "org", "eu", "co"})


def brand_check(text: str, charter: Charter) -> list[str]:
    """Contrôle déterministe d'un contenu contre la charte. Liste les écarts.

    Détecte : terme banni présent, mauvais domaine (le label de base du domaine
    canonique suivi d'un TLD différent — ``omnividens.com`` / ``.io`` / … au lieu
    de ``omnividens.fr``). Liste vide ⇒ conforme. Ne *réécrit* rien — l'humain
    tranche.
    """
    issues: list[str] = []
    lower = text.lower()
    for term in charter.banned_terms:
        if term.lower() in lower:
            issues.append(f"Terme banni détecté : « {term} » (anti-FUD).")

    # Robuste même si le domaine de charte n'est pas en .fr : on flague tout
    # ``<base>.<tld>`` dont le TLD diffère du canonique. ``(?![a-z])`` évite le
    # faux positif « omnividens.community » (le « com » n'est pas un vrai TLD ici).
    base, _, tld = charter.domain.lower().rpartition(".")
    wrong_tlds = sorted(_WRONG_TLDS - {tld})
    if base and wrong_tlds:
        pattern = re.escape(base) + r"\.(" + "|".join(wrong_tlds) + r")(?![a-z])"
        match = re.search(pattern, lower)
        if match:
            issues.append(
                f"Mauvais domaine : « {match.group(0)} » au lieu de « {charter.domain} »."
            )
    return issues


__all__ = [
    "Charter",
    "brand_check",
    "charter_path",
    "load_charter",
    "save_charter",
]
