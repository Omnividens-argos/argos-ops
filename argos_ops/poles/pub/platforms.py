"""Catalogue des **plateformes publicitaires** du pôle Pub (archi v2, S3).

Source de vérité *pure* partagée par l'agent (qui route une idée de campagne vers
des plateformes), les scripts (``ads_optimizer`` parse un CSV par plateforme,
``ad_bot`` pousse par plateforme) et le cockpit (validation de créa + compteur de
caractères par contrainte). Miroir des contraintes réelles des formats d'annonce
et du skill ``ads-creative`` :

- **Google Search (RSA)** : jusqu'à 15 titres ≤ 30 car. + descriptions ≤ 90 car.
- **LinkedIn Sponsored** : 1 intro ≤ 600 car. + 1 headline ≤ 150 car.
- **Meta (Facebook/Instagram)** : 1 texte principal ≤ 125 car. + 1 titre ≤ 40 car.

Aucune I/O, aucune API tierce, aucun LLM ici : c'est de la donnée de référence.
``keyword_targeted`` distingue Google (ciblage par mot-clé → action *drop keyword*
possible) des plateformes à ciblage par audience.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdPlatform:
    """Une plateforme publicitaire et ses contraintes de créa."""

    id: str
    label: str
    creative_skill: str
    headline_max: int  # longueur max d'UN titre
    headline_count: int  # nombre de titres attendus (RSA = jusqu'à 15)
    primary_max: int  # texte principal / 1re description
    keyword_targeted: bool = False  # ciblage par mot-clé (Google) vs audience

    def headline_ok(self, text: str) -> bool:
        return len(text) <= self.headline_max

    def primary_ok(self, text: str) -> bool:
        return len(text) <= self.primary_max


# Ordre = priorité d'affichage dans le cockpit (search → social pro → social grand public).
PLATFORMS: tuple[AdPlatform, ...] = (
    AdPlatform(
        "google_search",
        "Google Search (RSA)",
        "ads-creative",
        headline_max=30,
        headline_count=15,
        primary_max=90,
        keyword_targeted=True,
    ),
    AdPlatform(
        "linkedin_sponsored",
        "LinkedIn Sponsored",
        "ads-creative",
        headline_max=150,
        headline_count=1,
        primary_max=600,
    ),
    AdPlatform(
        "meta",
        "Meta (Facebook/Instagram)",
        "ads-creative",
        headline_max=40,
        headline_count=1,
        primary_max=125,
    ),
)

_BY_ID: dict[str, AdPlatform] = {p.id: p for p in PLATFORMS}

PLATFORM_IDS: tuple[str, ...] = tuple(p.id for p in PLATFORMS)


def get_platform(platform_id: str) -> AdPlatform | None:
    """La plateforme d'``id`` donné, ou ``None`` si inconnue."""
    return _BY_ID.get(platform_id)


def is_known_platform(platform_id: str) -> bool:
    return platform_id in _BY_ID


__all__ = [
    "PLATFORMS",
    "PLATFORM_IDS",
    "AdPlatform",
    "get_platform",
    "is_known_platform",
]
