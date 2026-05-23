"""Scoring de pipe commercial — utilisé par DealRiskScorer.

Politique : un deal est ``stalled`` si > 14 jours sans activité **et**
encore au stade ``discovery``/``demo_done``/``proposal_sent``. Les deals
``won``/``lost`` sont écartés du scoring (ils ne sont plus dans le pipe
actif). Les ``contract_sent`` sont scorés mais avec un seuil plus
tolérant (30j) car la signature légale prend du temps.

Le score 0-100 combine :

- **Inactivité** : 0-50 pts (1 pt par jour, cappé à 50)
- **Montant** : 0-30 pts (deal > 5k€/mois pèse plus, perdre un gros
  client est plus coûteux)
- **Stade** : 0-20 pts (plus on est avancé dans le pipe, plus le
  risque coûte cher — un proposal_sent stalled = -20 pts vs
  discovery)
"""

from __future__ import annotations

from datetime import date

from argos_ops.sales.models import Deal, DealStage, DealStalledFlag

STALLED_THRESHOLD_DAYS: dict[DealStage, int] = {
    DealStage.DISCOVERY: 14,
    DealStage.DEMO_SCHEDULED: 7,  # un démo annoncé sans suivi = très chaud à perdre
    DealStage.DEMO_DONE: 14,
    DealStage.PROPOSAL_SENT: 14,
    DealStage.CONTRACT_SENT: 30,  # signature légale = patience
}
"""Seuils d'inactivité par stade au-delà desquels on flag stalled."""


_STAGE_RISK_BONUS: dict[DealStage, int] = {
    DealStage.DISCOVERY: 5,
    DealStage.DEMO_SCHEDULED: 12,
    DealStage.DEMO_DONE: 15,
    DealStage.PROPOSAL_SENT: 20,
    DealStage.CONTRACT_SENT: 18,
}


def score_deal_risk(deal: Deal, *, today: date | None = None) -> DealStalledFlag:
    """Calcule le risque + flag stalled d'un deal.

    Les stades ``won`` / ``lost`` retournent ``risk_score=0`` et
    ``is_stalled=False`` — ils ne sont plus dans le pipe actif. Le
    caller (``DealRiskScorer``) filtre normalement avant d'arriver
    ici, mais on est défensif au cas où.
    """
    today = today or date.today()
    days_since = (today - deal.last_activity_at).days
    if days_since < 0:
        days_since = 0

    if deal.stage in {DealStage.WON, DealStage.LOST}:
        return DealStalledFlag(
            deal=deal,
            days_since_activity=days_since,
            risk_score=0,
            is_stalled=False,
            reason=f"deal {deal.stage.value} — pipe inactif",
        )

    threshold = STALLED_THRESHOLD_DAYS.get(deal.stage, 14)
    is_stalled = days_since > threshold

    inactivity_pts = min(50, days_since)
    if deal.amount_eur >= 5000:
        amount_pts = 30
    elif deal.amount_eur >= 1500:
        amount_pts = 20
    elif deal.amount_eur >= 500:
        amount_pts = 10
    else:
        amount_pts = 5
    stage_pts = _STAGE_RISK_BONUS.get(deal.stage, 0)
    risk_score = min(100, inactivity_pts + amount_pts + stage_pts)

    if is_stalled:
        reason = (
            f"stalled {days_since}j (seuil {threshold}j pour stade "
            f"{deal.stage.value}) — montant {deal.amount_eur}€/mois"
        )
    else:
        reason = (
            f"actif {days_since}j depuis dernière activité "
            f"(seuil {threshold}j pour {deal.stage.value})"
        )
    return DealStalledFlag(
        deal=deal,
        days_since_activity=days_since,
        risk_score=risk_score,
        is_stalled=is_stalled,
        reason=reason,
    )


__all__ = ["STALLED_THRESHOLD_DAYS", "score_deal_risk"]
