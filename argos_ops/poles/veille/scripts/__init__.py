"""Scripts (bras déterministes) du pôle Veille — archi v2.

Chaque script hérite de :class:`~argos_ops.poles.base.BaseScript`, porte une
logique *pure et déterministe* (fetch / parse / diff / score) migrée depuis les
anciens agents ``argos_ops.agents.*``, et **écrit sa propre mémoire** de pôle
(``data/poles/veille/scripts/<name>/memory/``). Aucun n'envoie de Discord ni ne
touche la DB : c'est le :class:`~argos_ops.poles.veille.agent.VeilleAgent` qui
lit cette mémoire et agit (D-017, local-first).
"""

from __future__ import annotations

from argos_ops.poles.veille.scripts.breach_watcher import BreachWatcherScript
from argos_ops.poles.veille.scripts.competitor_watcher import CompetitorWatcherScript
from argos_ops.poles.veille.scripts.cve_monitor import CVEMonitorScript
from argos_ops.poles.veille.scripts.darkweb_monitor import DarkWebMonitorScript
from argos_ops.poles.veille.scripts.intent_signals import IntentSignalsScript
from argos_ops.poles.veille.scripts.keyword_radar import KeywordRadarScript
from argos_ops.poles.veille.scripts.press_monitor import PressMonitorScript
from argos_ops.poles.veille.scripts.regulatory_watcher import RegulatoryWatcherScript
from argos_ops.poles.veille.scripts.trend_spotter import TrendSpotterScript

# Ordre = ordre d'exécution cron canonique du pôle (cf. pole.yaml).
VEILLE_SCRIPTS = (
    TrendSpotterScript,
    CompetitorWatcherScript,
    BreachWatcherScript,
    RegulatoryWatcherScript,
    CVEMonitorScript,
    DarkWebMonitorScript,
    PressMonitorScript,
    KeywordRadarScript,
    IntentSignalsScript,
)

__all__ = [
    "VEILLE_SCRIPTS",
    "BreachWatcherScript",
    "CVEMonitorScript",
    "CompetitorWatcherScript",
    "DarkWebMonitorScript",
    "IntentSignalsScript",
    "KeywordRadarScript",
    "PressMonitorScript",
    "RegulatoryWatcherScript",
    "TrendSpotterScript",
]
