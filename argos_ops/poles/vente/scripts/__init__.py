"""Bras déterministes (scripts) du pôle Vente & Relation Client (archi v2, S4).

Chaque script hérite de :class:`~argos_ops.poles.base.BaseScript`, fait du travail
pur et idempotent (lit un fichier ``data/poles/vente/…``, calcule, écrit sa
mémoire) et ne décide rien : c'est le :class:`~argos_ops.poles.vente.agent.VenteAgent`
qui lit cette mémoire et agit. 100 % fichiers / local-first (D-017).
"""

from __future__ import annotations

from argos_ops.poles.vente.scripts.bloctel_guard import BloctelGuardScript
from argos_ops.poles.vente.scripts.churn_predictor import ChurnPredictorScript
from argos_ops.poles.vente.scripts.contract_generator import ContractGeneratorScript
from argos_ops.poles.vente.scripts.email_bot import EmailBotScript
from argos_ops.poles.vente.scripts.escalation_router import EscalationRouterScript
from argos_ops.poles.vente.scripts.health_score import HealthScoreScript
from argos_ops.poles.vente.scripts.lead_enricher import LeadEnricherScript
from argos_ops.poles.vente.scripts.meeting_booker import MeetingBookerScript
from argos_ops.poles.vente.scripts.outbound_sender import OutboundSenderScript
from argos_ops.poles.vente.scripts.proposal_bot import ProposalBotScript
from argos_ops.poles.vente.scripts.prospect_miner import ProspectMinerScript
from argos_ops.poles.vente.scripts.upsell_spotter import UpsellSpotterScript

# Ordre = ordre d'exécution cron canonique du pôle (cf. pole.yaml).
VENTE_SCRIPTS = (
    EmailBotScript,
    ProspectMinerScript,
    LeadEnricherScript,
    BloctelGuardScript,
    MeetingBookerScript,
    OutboundSenderScript,
    EscalationRouterScript,
    ChurnPredictorScript,
    HealthScoreScript,
    UpsellSpotterScript,
    ProposalBotScript,
    ContractGeneratorScript,
)

__all__ = [
    "VENTE_SCRIPTS",
    "BloctelGuardScript",
    "ChurnPredictorScript",
    "ContractGeneratorScript",
    "EmailBotScript",
    "EscalationRouterScript",
    "HealthScoreScript",
    "LeadEnricherScript",
    "MeetingBookerScript",
    "OutboundSenderScript",
    "ProposalBotScript",
    "ProspectMinerScript",
    "UpsellSpotterScript",
]
