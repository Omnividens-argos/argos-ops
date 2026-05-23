"""Module Sales — utilitaires partagés par les 9 bots du Sprint 3 (P22.H).

Conformément à D-017 (local-first, zéro API LLM) tout est déterministe :

- :mod:`models` — dataclasses partagées (Prospect, Signal, MeetingRequest,
  Deal, ProposalContext).
- :mod:`enrichment` — heuristiques BANT / persona ICP / patterns d'email,
  porte le skill markdown ``lead-enricher`` en Python pur.
- :mod:`ical` — génération d'invitations RFC 5545 (iCalendar) à attacher
  aux mails de RDV démo.
- :mod:`scoring` — scoring de pipe (DealRiskScorer) et flag des deals
  stalled > 14j.
- :mod:`templates` — rendu de devis / contrats / mails à partir de
  templates Markdown + variables compte (Pandoc pour PDF si dispo).

Aucun module ici ne fait d'IO réseau outbound — les bots de l'agent
``argos_ops/agents/`` orchestrent le call SMTP / scraping public et
appellent ces helpers pour la logique métier pure.
"""

from __future__ import annotations

from argos_ops.sales.enrichment import (
    BANTScore,
    EmailGuess,
    PersonaHint,
    enrich_lead,
    guess_emails,
    score_bant,
    score_persona,
)
from argos_ops.sales.ical import build_ical_invite
from argos_ops.sales.models import (
    Deal,
    DealStage,
    DealStalledFlag,
    IntentSignal,
    MeetingRequest,
    ProposalContext,
    Prospect,
    ProspectSource,
)
from argos_ops.sales.scoring import score_deal_risk
from argos_ops.sales.templates import (
    PROPOSAL_TEMPLATE,
    render_contract,
    render_demo_followup,
    render_proposal,
    try_render_pdf,
)

__all__ = [
    "PROPOSAL_TEMPLATE",
    "BANTScore",
    "Deal",
    "DealStage",
    "DealStalledFlag",
    "EmailGuess",
    "IntentSignal",
    "MeetingRequest",
    "PersonaHint",
    "ProposalContext",
    "Prospect",
    "ProspectSource",
    "build_ical_invite",
    "enrich_lead",
    "guess_emails",
    "render_contract",
    "render_demo_followup",
    "render_proposal",
    "score_bant",
    "score_deal_risk",
    "score_persona",
    "try_render_pdf",
]
