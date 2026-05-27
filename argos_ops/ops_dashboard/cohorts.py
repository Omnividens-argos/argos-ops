"""Cohort analysis pour l'Admin Control Panel (Phase 5 UX).

Construit une table de rétention mensuelle depuis ``companies`` :
chaque colonne = mois depuis signup (M+0 = mois de signup, M+1 = +1 mois,
etc.). Une company compte comme « retained » à un mois donné si son
``subscription_status`` était toujours actif/trialing à cette date.

Limites volontaires :
- Pas d'historique des statuts → on suppose qu'une company actuellement
  ``canceled`` l'a toujours été à partir d'un certain mois. C'est une
  approximation acceptable tant qu'on n'a pas une table d'events Stripe.
- Pas d'autre signal que ``subscription_status`` (pas d'usage, pas de
  login). Suffit pour un dashboard fondateur.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlmodel import select

from argos_ops.ops_dashboard.models import CohortRow, CohortsResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Combien de mois on suit après signup (= largeur de la table).
DEFAULT_MONTHS_TRACKED = 6


def _month_key(d: datetime) -> str:
    return d.strftime("%Y-%m")


async def compute_cohorts(
    session: AsyncSession,
    *,
    months_tracked: int = DEFAULT_MONTHS_TRACKED,
) -> CohortsResponse:
    """Calcule les cohortes depuis ``companies``.

    Algorithme :
    1. Group companies par mois de ``created_at``
    2. Pour chaque cohorte, compte combien sont retained à M+0, M+1…
    3. « Retained » = subscription_status ∈ {active, trialing} aujourd'hui
       (approximation — pas d'historique d'events Stripe en local).
    """
    from argos_ops.crm.models import Company

    stmt = select(Company)
    companies = list((await session.execute(stmt)).scalars().all())

    if not companies:
        return CohortsResponse(
            has_data=False,
            months_tracked=months_tracked,
            rows=[],
            last_refreshed_at=datetime.now(UTC),
        )

    # Bucket par mois de signup.
    cohorts: dict[str, list[Company]] = {}
    for c in companies:
        if c.created_at is None:
            continue
        key = _month_key(c.created_at)
        cohorts.setdefault(key, []).append(c)

    # Tri chronologique.
    rows: list[CohortRow] = []
    now = datetime.now(UTC)
    sorted_months = sorted(cohorts.keys())

    for month_key in sorted_months:
        members = cohorts[month_key]
        signup_dt = datetime.strptime(month_key, "%Y-%m").replace(tzinfo=UTC)
        # Calcule l'âge de la cohorte en mois (approx 30j).
        age_months = max(0, int((now - signup_dt).days / 30))
        max_observed = min(months_tracked, age_months + 1)

        retained: list[int] = []
        for offset in range(months_tracked):
            if offset > max_observed:
                retained.append(0)
                continue
            # Approximation : on regarde si la company est ENCORE
            # active aujourd'hui. Si non, on suppose qu'elle a churné
            # avant offset (donc 0). Sinon 1.
            count = sum(
                1
                for m in members
                if m.subscription_status in ("active", "trialing")
                or (offset == 0)  # M+0 = forcément la taille de la cohorte
            )
            # Pour M+0, on prend tous les membres (signup mois).
            if offset == 0:
                retained.append(len(members))
            else:
                retained.append(count)

        rows.append(
            CohortRow(
                signup_month=month_key,
                cohort_size=len(members),
                retained_by_month=retained,
            )
        )

    return CohortsResponse(
        has_data=True,
        months_tracked=months_tracked,
        rows=rows,
        last_refreshed_at=datetime.now(UTC),
    )


# Mute le warning d'import unused.
_ = timedelta

__all__ = ["DEFAULT_MONTHS_TRACKED", "compute_cohorts"]
