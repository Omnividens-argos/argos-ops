"""Dataclasses partagées par les 9 bots Sales (P22.H Sprint 3).

Pas de logique ici — uniquement des conteneurs immuables ou très
légers, consommés par les agents ``argos_ops/agents/{prospect_miner,
lead_enricher, intent_signals, meeting_booker, demo_followup,
proposal_bot, contract_generator, deal_risk_scorer}.py``.

Sérialisation YAML/Markdown faite par ``argos_ops.sales.templates`` et
``argos_ops.sales.ical`` — ce module ne touche pas au filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class ProspectSource(StrEnum):
    """Source publique où un prospect a été identifié.

    Sources explicitement BtoB-friendly :
    - ``annonces_legales`` — BODACC / annonces-legales.fr (création de SA / SAS)
    - ``crunchbase_news`` — RSS levées de fonds (page publique news.crunchbase.com)
    - ``linkedin_jobs`` — flux RSS recherches d'emploi cyber/sec (CISO, RSSI)
    - ``manual`` — saisi à la main par le fondateur dans le CSV inbox

    Pas de scraping LinkedIn agressif (anti-pattern D-016 + ToS).
    Pas de Crunchbase API payante (D-017 zéro SaaS).
    """

    ANNONCES_LEGALES = "annonces_legales"
    CRUNCHBASE_NEWS = "crunchbase_news"
    LINKEDIN_JOBS = "linkedin_jobs"
    MANUAL = "manual"


@dataclass(frozen=True)
class Prospect:
    """Un prospect candidat — output ProspectMiner / input LeadEnricher."""

    full_name: str | None
    company: str
    domain: str
    source: ProspectSource
    title_hint: str | None = None
    raw_signal: str | None = None  # ex : titre de l'annonce, snippet du job
    discovered_at: str = ""  # ISO 8601


class DealStage(StrEnum):
    """Étapes du pipe commercial Argos / Omnividens.

    Cycle court PME (3-6 semaines typiquement) — voir
    ``docs/ESCALATION_RULES.md`` pour les SLA par étape.
    """

    DISCOVERY = "discovery"
    DEMO_SCHEDULED = "demo_scheduled"
    DEMO_DONE = "demo_done"
    PROPOSAL_SENT = "proposal_sent"
    CONTRACT_SENT = "contract_sent"
    WON = "won"
    LOST = "lost"


@dataclass(frozen=True)
class Deal:
    """Un deal dans le pipe — input DealRiskScorer."""

    deal_id: str  # slug stable, ex : "acme-fr-q2-2026"
    company: str
    stage: DealStage
    amount_eur: int  # MRR annualisé proposé, en € entier
    last_activity_at: date
    owner: str = "founder"
    notes: str | None = None


@dataclass(frozen=True)
class DealStalledFlag:
    """Sortie du scoring : un deal flag stalled + raison."""

    deal: Deal
    days_since_activity: int
    risk_score: int  # 0-100 — plus c'est haut, plus c'est en danger
    is_stalled: bool
    reason: str


@dataclass(frozen=True)
class IntentSignal:
    """Signal d'achat capté (breach, embauche CISO, levée).

    ``relevance_score`` est calculé par ``IntentSignalsBot`` en
    fonction de l'ICP — un breach public sur une PME tech FR ≥ 50
    employés scorera plus haut qu'une multinationale US.
    """

    kind: str  # 'breach' | 'ciso_hire' | 'fundraise' | 'cve_critical'
    company: str
    domain: str | None
    published_at: date
    source_url: str
    summary: str
    relevance_score: int  # 0-100


@dataclass
class MeetingRequest:
    """Demande de RDV démo — input MeetingBooker.

    Le fondateur saisit ces lignes dans
    ``data/sales/meetings/requests.yaml`` à la main ou via réponse
    EmailBot. MeetingBooker confirme + génère iCal + draft email.
    """

    request_id: str
    attendee_email: str
    attendee_name: str
    company: str
    starts_at: datetime  # UTC
    duration_minutes: int = 30
    location: str = "Visio (Jitsi / Whereby — lien envoyé H-2)"
    status: str = "pending"  # pending | confirmed | sent | cancelled


@dataclass
class ProposalContext:
    """Variables compte pour générer un devis ou contrat.

    Source : ``data/sales/proposals/<deal_id>/context.yaml`` rempli par
    le fondateur. Aucun champ n'est secret — pas de SecretStr ici.
    """

    deal_id: str
    company: str
    contact_name: str
    contact_email: str
    siret: str | None = None
    plan: str = "Argos Pro"  # ex : "Argos Pro", "Argos Enterprise"
    monthly_price_eur: int = 350
    setup_fee_eur: int = 0
    discount_percent: int = 0
    contract_duration_months: int = 12
    issue_date: date = field(default_factory=date.today)
    validity_days: int = 30
    extras: dict[str, str] = field(default_factory=dict)


__all__ = [
    "Deal",
    "DealStage",
    "DealStalledFlag",
    "IntentSignal",
    "MeetingRequest",
    "ProposalContext",
    "Prospect",
    "ProspectSource",
]
