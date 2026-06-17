"""Scripts (bras déterministes) du pôle Pub — archi v2 (S3).

Chaque script hérite de :class:`~argos_ops.poles.base.BaseScript`, porte une
logique *pure et déterministe* (optimiser / pousser) et **écrit sa propre
mémoire** de pôle (``data/poles/pub/scripts/<name>/memory/``). Aucun n'envoie de
Discord ni ne touche la DB : c'est le :class:`~argos_ops.poles.pub.agent.PubAgent`
qui lit cette mémoire et planifie (D-017, local-first).

- ``ads_optimizer`` : CSV de campagnes → recos chiffrées + jauge budget + breaker.
- ``ad_bot``        : pousseur shadow (créas validées + recos appliquées), bridé
  par le breaker.
"""

from __future__ import annotations

from argos_ops.poles.pub.scripts.ad_bot import AdBotScript
from argos_ops.poles.pub.scripts.ads_optimizer import AdsOptimizerScript

# Ordre = ordre d'exécution cron canonique du pôle (optimiser AVANT de pousser).
PUB_SCRIPTS = (
    AdsOptimizerScript,
    AdBotScript,
)

__all__ = [
    "PUB_SCRIPTS",
    "AdBotScript",
    "AdsOptimizerScript",
]
