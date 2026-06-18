"""Bras déterministes (scripts) du pôle Direction (archi v2, S6).

Chaque script hérite de :class:`~argos_ops.poles.base.BaseScript`, fait du travail
pur et idempotent (lit la vue d'ensemble flotte ou un snapshot
``data/poles/direction/…``, réutilise une brique pure legacy, écrit sa mémoire) et
ne décide rien : c'est le :class:`~argos_ops.poles.direction.agent.DirectionAgent`
qui lit cette mémoire (+ toute la flotte en cross-pôle) et agit. Les faits de
gouvernance (décisions, board pack, OKR off-track, bug P0, feedback récurrent) sont
écrits ``important`` (protégés du nettoyage). 100 % fichiers / local-first (D-017).
"""

from __future__ import annotations

from argos_ops.poles.direction.scripts.board_reporter import BoardReporterScript
from argos_ops.poles.direction.scripts.bug_triage import BugTriageScript
from argos_ops.poles.direction.scripts.changelog_bot import ChangelogBotScript
from argos_ops.poles.direction.scripts.decision_logger import DecisionLoggerScript
from argos_ops.poles.direction.scripts.digest_builder import DigestBuilderScript
from argos_ops.poles.direction.scripts.feedback_aggregator import FeedbackAggregatorScript
from argos_ops.poles.direction.scripts.okr_tracker import OKRTrackerScript
from argos_ops.poles.direction.scripts.roadmap_publisher import RoadmapPublisherScript
from argos_ops.poles.direction.scripts.strategy_bot import StrategyBotScript

# Ordre = ordre d'exécution cron canonique du pôle (cf. pole.yaml).
DIRECTION_SCRIPTS = (
    StrategyBotScript,
    DigestBuilderScript,
    OKRTrackerScript,
    BoardReporterScript,
    DecisionLoggerScript,
    ChangelogBotScript,
    FeedbackAggregatorScript,
    RoadmapPublisherScript,
    BugTriageScript,
)

__all__ = [
    "DIRECTION_SCRIPTS",
    "BoardReporterScript",
    "BugTriageScript",
    "ChangelogBotScript",
    "DecisionLoggerScript",
    "DigestBuilderScript",
    "FeedbackAggregatorScript",
    "OKRTrackerScript",
    "RoadmapPublisherScript",
    "StrategyBotScript",
]
