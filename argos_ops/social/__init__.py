"""Connecteurs sociaux Argos Ops — P11 + Sprint B.

Wrappers minces autour des APIs LinkedIn, Mastodon et Bluesky. Tous les
connecteurs respectent un contrat commun :

- ``post(text: str, *, dry_run: bool) -> PublishResult`` — publie ou
  retourne un résultat shadow si credentials absents OU ``dry_run=True``
- ``PublishResult`` contient ``status`` (``published`` / ``shadow`` /
  ``failed``), ``platform``, ``url`` (None en shadow), ``error``
"""

from __future__ import annotations

from argos_ops.social.bluesky import BlueskyClient
from argos_ops.social.linkedin import LinkedInClient
from argos_ops.social.mastodon import MastodonClient
from argos_ops.social.publisher import PublishResult, publish_draft

__all__ = [
    "BlueskyClient",
    "LinkedInClient",
    "MastodonClient",
    "PublishResult",
    "publish_draft",
]
