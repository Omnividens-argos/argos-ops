"""Scripts (bras déterministes) du pôle Marketing — archi v2 (S2).

Chaque script hérite de :class:`~argos_ops.poles.base.BaseScript`, porte une
logique *pure et déterministe* (publier / agréger / auditer) et **écrit sa propre
mémoire** de pôle (``data/poles/marketing/scripts/<name>/memory/``). Aucun
n'envoie de Discord ni ne touche la DB : c'est le
:class:`~argos_ops.poles.marketing.agent.MarketingAgent` qui lit cette mémoire et
agit (D-017, local-first).

- ``content_bot``        : publie les drafts validés & échus (shadow local-first).
- ``social_analytics``   : agrège l'engagement social 7j par canal.
- ``media_list_builder`` : audite la DB des journalistes / médias cyber.
"""

from __future__ import annotations

from argos_ops.poles.marketing.scripts.content_bot import ContentBotScript
from argos_ops.poles.marketing.scripts.media_list_builder import MediaListBuilderScript
from argos_ops.poles.marketing.scripts.social_analytics import SocialAnalyticsScript

# Ordre = ordre d'exécution cron canonique du pôle (cf. pole.yaml).
MARKETING_SCRIPTS = (
    ContentBotScript,
    SocialAnalyticsScript,
    MediaListBuilderScript,
)

__all__ = [
    "MARKETING_SCRIPTS",
    "ContentBotScript",
    "MediaListBuilderScript",
    "SocialAnalyticsScript",
]
