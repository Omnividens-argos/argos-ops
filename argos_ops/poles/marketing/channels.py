"""Catalogue des **canaux** de diffusion du pôle Marketing (archi v2, S2).

Source de vérité *pure* partagée par l'agent (qui route une recommandation vers
des canaux), les scripts (ContentBot publie par canal) et le cockpit (preview
par canal avec compteur de caractères). Chaque canal pointe vers le **skill
writer** dédié de la banque de l'agent (cf. :mod:`argos_ops.poles.marketing.skills`)
et porte sa contrainte de longueur — miroir des connecteurs ``argos_ops.social``
et des writers existants (LinkedIn 1300-2000, Mastodon 300-500, X ≤280, …).

Aucune I/O, aucune API tierce, aucun LLM ici : c'est de la donnée de référence.
``max_chars = 0`` ⇒ pas de plafond dur (blog / newsletter — format long).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    """Un canal de diffusion et sa contrainte éditoriale."""

    id: str
    label: str
    writer_skill: str
    max_chars: int  # 0 = pas de plafond dur (format long)
    min_chars: int = 0
    social: bool = True

    def length_ok(self, text: str) -> bool:
        """Le corps respecte-t-il les bornes du canal ?"""
        n = len(text)
        if self.max_chars and n > self.max_chars:
            return False
        return n >= self.min_chars


# Ordre = priorité d'affichage dans le cockpit (réseaux courts → formats longs).
CHANNELS: tuple[Channel, ...] = (
    Channel("linkedin", "LinkedIn", "linkedin-writer", max_chars=2000, min_chars=1300),
    Channel("mastodon", "Mastodon", "mastodon-writer", max_chars=500, min_chars=300),
    Channel("meta", "Facebook", "meta-writer", max_chars=500),
    Channel("x", "X", "x-writer", max_chars=280),
    Channel("bluesky", "Bluesky", "bluesky-writer", max_chars=300),
    Channel("truth", "Truth Social", "truth-social-writer", max_chars=500),
    Channel("blog", "Blog / SEO", "seo-brief", max_chars=0, social=False),
    Channel("newsletter", "Newsletter", "newsletter", max_chars=0, social=False),
)

_BY_ID: dict[str, Channel] = {c.id: c for c in CHANNELS}

CHANNEL_IDS: tuple[str, ...] = tuple(c.id for c in CHANNELS)


def get_channel(channel_id: str) -> Channel | None:
    """Le canal d'``id`` donné, ou ``None`` si inconnu."""
    return _BY_ID.get(channel_id)


def is_known_channel(channel_id: str) -> bool:
    return channel_id in _BY_ID


__all__ = ["CHANNELS", "CHANNEL_IDS", "Channel", "get_channel", "is_known_channel"]
