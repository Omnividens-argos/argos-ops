"""Dataclasses du module outbound (P13).

Pas de logique métier ici — uniquement des conteneurs immuables que
``sequence.py``, ``templates.py`` et l'agent ``OutboundBot`` produisent
et consomment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum


class TouchStep(IntEnum):
    """Les 5 touches canoniques d'une séquence outbound BtoB.

    Cadence par défaut (cf. ``templates.TOUCH_CADENCE_DAYS``) :

    - ``DISCOVERY`` (D+0) — opener personnalisé, 1 question simple
    - ``VALUE`` (D+3) — drop de valeur (blog post, mini-démo)
    - ``CASE`` (D+7) — étude de cas concrète chiffrée
    - ``PROOF`` (D+14) — preuve sociale (témoignage, feature spécifique)
    - ``BREAKUP`` (D+30) — break-up email court, dernière relance

    Si une touche déclenche une réponse, la séquence s'arrête (géré côté
    futur connecteur Zimbra inbound — pas dans P13 shadow).
    """

    DISCOVERY = 1
    VALUE = 2
    CASE = 3
    PROOF = 4
    BREAKUP = 5


@dataclass(frozen=True)
class LeadInput:
    """Une ligne brute du CSV inbox — entrée du pipeline outbound.

    Format CSV minimal attendu (header obligatoire) :

    ``full_name,domain,title_hint,linkedin_url``

    Seuls ``full_name`` et ``domain`` sont obligatoires. Les deux autres
    accélèrent / précisent l'enrichissement par le skill ``lead-enricher``.
    """

    full_name: str
    domain: str
    title_hint: str | None = None
    linkedin_url: str | None = None


@dataclass
class Touch:
    """État d'une touche dans une séquence.

    Le ``body`` est ``None`` en scaffold (Python pur) et rempli ensuite
    par le slash `/draft-outbound` (skill outbound-drafter à venir).
    """

    step: TouchStep
    scheduled_date: date
    body: str | None = None
    subject: str | None = None
    judge_score: int | None = None
    judge_verdict: str | None = None  # 'auto_send' | 'queued' | 'killed'
    status: str = "scaffold"  # scaffold | drafted | sent | replied | skipped
    sent_at: str | None = None  # ISO 8601 si envoyé (live mode P13.B)


@dataclass
class SequenceState:
    """État d'une séquence complète pour un lead — sérialisé dans meta.yaml."""

    lead_slug: str
    full_name: str
    domain: str
    enriched_path: str | None  # chemin relatif vers data/outbound/enriched/<slug>.md
    opt_out_token: str
    sequence_status: str = "scaffold"  # scaffold | drafting | active | done | killed
    touches: list[Touch] = field(default_factory=list)
    created_at: str = ""  # ISO 8601 datetime à la création du scaffold
    notes: str | None = None


__all__ = ["LeadInput", "SequenceState", "Touch", "TouchStep"]
