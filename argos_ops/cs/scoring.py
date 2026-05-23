"""Scoring CS — health score, upsell, churn, classification ticket (P22.G).

Heuristiques explicites (pas de ML) pour rester auditables et
explicables vis-à-vis des clients (RGPD § 22 — décisions
automatisées). Le founder doit pouvoir lire le code et comprendre
pourquoi un compte est rouge.
"""

from __future__ import annotations

from datetime import date

from argos_ops.cs.models import (
    ChurnSignal,
    Customer,
    CustomerPlan,
    HealthBand,
    HealthScore,
    SupportTicket,
    TicketPriority,
    UpsellCandidate,
)

# Seuils health score — modifiables ici sans toucher aux bots
HEALTH_GREEN_MIN = 70
HEALTH_YELLOW_MIN = 40
USAGE_UPSELL_THRESHOLD = 0.80  # 80% du quota plan
USAGE_LOW_THRESHOLD = 0.10  # < 10% du quota = sous-utilisation
NPS_DETRACTOR_MAX = 6
NPS_PROMOTER_MIN = 9
INACTIVITY_RED_DAYS = 30
INACTIVITY_YELLOW_DAYS = 14
TICKETS_30D_YELLOW = 3
TICKETS_30D_RED = 6

# Mots-clés P0 (incident bloquant) / P1 (bug majeur). P2 par défaut.
_P0_KEYWORDS = (
    "prod down",
    "production down",
    "all scans failing",
    "data loss",
    "perte de données",
    "incident",
    "urgent",
    "ne fonctionne plus du tout",
)
_P1_KEYWORDS = (
    "bug",
    "error 500",
    "scan stuck",
    "scan bloqué",
    "ne finit pas",
    "crash",
    "regression",
    "régression",
)


def compute_health_score(customer: Customer) -> HealthScore:
    """Calcule un score 0-100 + bande couleur.

    Pondération :
    - usage (40 pts) — sous-utilisation et sur-utilisation pénalisent
    - tickets 30j (20 pts) — beaucoup de tickets = friction
    - NPS (20 pts) — détracteur = -20, promoteur = +20
    - inactivité (20 pts) — login récent rassure

    Drivers loggés pour audit — le founder voit *pourquoi* un compte
    bascule en rouge.
    """
    score = 50  # baseline
    drivers: list[str] = []

    # --- Usage ---
    quota = customer.usage.scans_quota
    used = customer.usage.scans_this_month
    if quota > 0:
        ratio = used / quota
        if ratio >= USAGE_UPSELL_THRESHOLD:
            score += 20
            drivers.append(f"usage {ratio:.0%} quota (saturé — upsell ready)")
        elif ratio >= 0.30:
            score += 10
            drivers.append(f"usage {ratio:.0%} quota (sain)")
        elif ratio >= USAGE_LOW_THRESHOLD:
            drivers.append(f"usage {ratio:.0%} quota (faible)")
        else:
            score -= 20
            drivers.append(f"usage {ratio:.0%} quota (sous-utilisé — risque)")
    else:
        drivers.append("usage non mesuré (enterprise sur mesure)")

    # --- Tickets 30j ---
    if customer.tickets_30d >= TICKETS_30D_RED:
        score -= 20
        drivers.append(f"{customer.tickets_30d} tickets 30j (friction forte)")
    elif customer.tickets_30d >= TICKETS_30D_YELLOW:
        score -= 10
        drivers.append(f"{customer.tickets_30d} tickets 30j (friction)")
    elif customer.tickets_30d > 0:
        drivers.append(f"{customer.tickets_30d} ticket(s) 30j")

    # --- NPS ---
    if customer.last_nps is not None:
        if customer.last_nps >= NPS_PROMOTER_MIN:
            score += 20
            drivers.append(f"NPS {customer.last_nps} (promoteur)")
        elif customer.last_nps <= NPS_DETRACTOR_MAX:
            score -= 20
            drivers.append(f"NPS {customer.last_nps} (détracteur)")
        else:
            drivers.append(f"NPS {customer.last_nps} (passif)")
    else:
        drivers.append("NPS non collecté")

    # --- Inactivité ---
    last_login = customer.usage.last_login_days_ago
    if last_login is None:
        score -= 20
        drivers.append("jamais loggé (onboarding raté ?)")
    elif last_login >= INACTIVITY_RED_DAYS:
        score -= 20
        drivers.append(f"{last_login}j sans login (alerte)")
    elif last_login >= INACTIVITY_YELLOW_DAYS:
        score -= 10
        drivers.append(f"{last_login}j sans login")
    else:
        score += 10
        drivers.append(f"{last_login}j depuis login")

    score = max(0, min(100, score))
    if score >= HEALTH_GREEN_MIN:
        band = HealthBand.GREEN
    elif score >= HEALTH_YELLOW_MIN:
        band = HealthBand.YELLOW
    else:
        band = HealthBand.RED

    return HealthScore(customer_id=customer.customer_id, score=score, band=band, drivers=drivers)


def detect_upsell_candidate(customer: Customer) -> UpsellCandidate | None:
    """Détecte un compte mûr pour upsell : usage ≥ 80% du quota plan."""
    quota = customer.usage.scans_quota
    used = customer.usage.scans_this_month
    if quota <= 0:
        return None  # plan enterprise sur mesure — pas de logique upsell auto
    ratio = used / quota
    if ratio < USAGE_UPSELL_THRESHOLD:
        return None
    suggested = {
        CustomerPlan.STARTER: CustomerPlan.PRO,
        CustomerPlan.PRO: CustomerPlan.ENTERPRISE,
    }.get(customer.plan)
    if suggested is None:
        return None  # déjà au top plan
    reason = (
        f"usage {ratio:.0%} sur quota {quota} scans/mois — proposer {suggested.value} "
        f"avant la prochaine échéance Stripe"
    )
    return UpsellCandidate(
        customer_id=customer.customer_id,
        usage_ratio=round(ratio, 2),
        suggested_plan=suggested,
        reason=reason,
    )


def detect_churn_signals(customer: Customer) -> ChurnSignal | None:
    """Détecte les signaux pré-churn — None si le compte est sain.

    Signaux cumulatifs ; le risk_score est plafonné à 100.
    """
    risk = 0
    signals: list[str] = []

    last_login = customer.usage.last_login_days_ago
    if last_login is not None and last_login >= INACTIVITY_RED_DAYS:
        risk += 35
        signals.append(f"inactif depuis {last_login}j")
    elif last_login is not None and last_login >= INACTIVITY_YELLOW_DAYS:
        risk += 15
        signals.append(f"inactif depuis {last_login}j")

    if customer.last_nps is not None and customer.last_nps <= NPS_DETRACTOR_MAX:
        risk += 30
        signals.append(f"NPS détracteur ({customer.last_nps}/10)")

    if customer.tickets_30d >= TICKETS_30D_RED:
        risk += 25
        signals.append(f"{customer.tickets_30d} tickets 30j (friction)")
    elif customer.tickets_30d >= TICKETS_30D_YELLOW:
        risk += 10
        signals.append(f"{customer.tickets_30d} tickets 30j")

    quota = customer.usage.scans_quota
    used = customer.usage.scans_this_month
    if quota > 0 and used / quota < USAGE_LOW_THRESHOLD:
        risk += 15
        signals.append(f"usage {used / quota:.0%} (sous-utilisation)")

    if not signals:
        return None
    risk = min(100, risk)
    return ChurnSignal(customer_id=customer.customer_id, risk_score=risk, signals=signals)


def classify_ticket_priority(ticket: SupportTicket) -> TicketPriority:
    """Classifie un ticket en P0 / P1 / P2 via mots-clés sujet+body.

    Si déjà classifié manuellement (``ticket.priority``), on respecte
    la classification du fondateur (override humain).
    """
    if ticket.priority is not None:
        return ticket.priority
    haystack = f"{ticket.subject}\n{ticket.body}".lower()
    for kw in _P0_KEYWORDS:
        if kw in haystack:
            return TicketPriority.P0
    for kw in _P1_KEYWORDS:
        if kw in haystack:
            return TicketPriority.P1
    return TicketPriority.P2


def sla_response_hours(priority: TicketPriority, plan: CustomerPlan) -> int:
    """SLA réponse premier message en heures, selon priorité + plan.

    Cohérent avec ``docs/ESCALATION_RULES.md``. Enterprise = SLA divisé
    par 2 sur P0/P1 (contractuel).
    """
    base = {
        TicketPriority.P0: 1,
        TicketPriority.P1: 4,
        TicketPriority.P2: 24,
    }[priority]
    if plan == CustomerPlan.ENTERPRISE and priority in (TicketPriority.P0, TicketPriority.P1):
        return max(1, base // 2)
    return base


def sla_breached(ticket: SupportTicket, priority: TicketPriority, *, today: date) -> bool:
    """Renvoie True si le SLA réponse est dépassé.

    On compare en jours, conservativement : ``opened_at + ceil(sla_h/24)``
    vs aujourd'hui. Calculer en heures réelles demanderait un ``opened_at``
    datetime, hors scope (YAML saisi à la main, granularité jour).
    """
    if ticket.last_response_at is not None:
        return False  # une réponse a été envoyée, SLA respecté
    sla_h = sla_response_hours(priority, ticket.plan)
    sla_days = max(1, (sla_h + 23) // 24)
    return (today - ticket.opened_at).days >= sla_days


__all__ = [
    "HEALTH_GREEN_MIN",
    "HEALTH_YELLOW_MIN",
    "INACTIVITY_RED_DAYS",
    "INACTIVITY_YELLOW_DAYS",
    "NPS_DETRACTOR_MAX",
    "NPS_PROMOTER_MIN",
    "TICKETS_30D_RED",
    "TICKETS_30D_YELLOW",
    "USAGE_LOW_THRESHOLD",
    "USAGE_UPSELL_THRESHOLD",
    "classify_ticket_priority",
    "compute_health_score",
    "detect_churn_signals",
    "detect_upsell_candidate",
    "sla_breached",
    "sla_response_hours",
]
