"""FastAPI app de l'Admin Control Panel (P16.A — read-only).

Endpoints exposés :

- ``GET /api/agents`` — liste des agents avec leur dernier run + état breaker
- ``GET /api/agents/{name}/runs`` — historique paginé des runs d'un agent
- ``GET /api/runs`` — historique paginé global (toutes agents confondus)
- ``GET /api/breakers`` — breakers actuellement tripped
- ``GET /api/kpis/overview`` — KPIs page Overview (MRR, leads, tickets, breakers)
- ``GET /api/health`` — healthcheck simple pour Caddy / monitoring

Pas de mutation en 16.A (toggle/reset/run-now arrivent en 16.B).

Auth : aucune en local. La protection se fait via Caddy basic auth +
IP allowlist côté serveur (P16.B). Ne JAMAIS exposer cette app sans Caddy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun, Breaker
from argos_ops.crm.repository import (
    count_open_tickets,
    count_recent_leads,
    get_last_run_per_agent,
    list_recent_agent_runs,
    list_tripped_breakers,
    sum_active_mrr_eur,
)
from argos_ops.ops_dashboard.models import (
    AgentRunRow,
    AgentSummary,
    BreakerInfo,
    KPIsOverview,
)

# Agents pilotés par l'admin panel. La table peut être enrichie au fur et
# à mesure que de nouveaux agents entrent en prod (P9 ContentBot, etc.).
KNOWN_AGENTS: tuple[str, ...] = (
    "DigestBuilder",
    "EmailBot",
    "SupportBot",
    "FinanceBot",
)

# Mapping breaker → sévérité affichée dans l'UI. Cohérent avec la liste
# du module ``argos_ops.breakers`` (mrr_drop_critical, etc.). Les
# kill switches globaux par agent sont en ``info`` car déclenchés
# manuellement par le fondateur, pas automatiquement.
BREAKER_SEVERITY: dict[str, str] = {
    "mrr_drop_critical": "critical",
    "stripe_api_error_burst": "critical",
    "email_smtp_failures_burst": "critical",
    "DigestBuilder": "info",
    "EmailBot": "info",
    "SupportBot": "info",
    "FinanceBot": "info",
}

app = FastAPI(
    title="Argos Ops — Admin Control Panel",
    description="Cockpit privé du fondateur (P16). Read-only en phase 16.A.",
    version="0.16.0a1",
)

# CORS pour le dev local (Vite frontend sur :5173 → backend sur :9000).
# En prod tout est servi par Caddy sur le même hostname, donc CORS inutile.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# =============================================================================
# Helpers
# =============================================================================
def _duration_seconds(run: AgentRun) -> float | None:
    if run.started_at is None or run.ended_at is None:
        return None
    return (run.ended_at - run.started_at).total_seconds()


def _run_to_row(run: AgentRun) -> AgentRunRow:
    return AgentRunRow(
        id=run.id or 0,
        agent_name=run.agent_name,
        command=run.command,
        started_at=run.started_at,
        ended_at=run.ended_at,
        duration_seconds=_duration_seconds(run),
        status=run.status,
        output_summary=run.output_summary,
        error=run.error,
        cost_estimate_eur=(
            float(run.cost_estimate_eur) if run.cost_estimate_eur is not None else None
        ),
    )


def _breaker_to_info(b: Breaker) -> BreakerInfo:
    return BreakerInfo(
        name=b.name,
        tripped=b.tripped,
        tripped_at=b.tripped_at,
        reason=b.reason,
        reset_after=b.reset_after,
        severity=BREAKER_SEVERITY.get(b.name, "unknown"),
    )


# =============================================================================
# Endpoints
# =============================================================================
@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Healthcheck minimal — DB UP + timestamp serveur."""
    try:
        async with session_scope() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "ok": db_ok,
        "service": "ops_dashboard",
        "version": app.version,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/agents", response_model=list[AgentSummary])
async def list_agents() -> list[AgentSummary]:
    """Liste des agents pilotés par l'admin panel avec leur dernier run + état breaker."""
    async with session_scope() as session:
        last_runs = await get_last_run_per_agent(session)
        tripped = await list_tripped_breakers(session)

    tripped_by_name = {b.name: b for b in tripped}
    out: list[AgentSummary] = []
    for agent_name in KNOWN_AGENTS:
        last_run = last_runs.get(agent_name)
        breaker = tripped_by_name.get(agent_name)
        out.append(
            AgentSummary(
                name=agent_name,
                last_run_status=last_run.status if last_run else None,
                last_run_at=last_run.started_at if last_run else None,
                last_run_duration_seconds=_duration_seconds(last_run) if last_run else None,
                last_run_output_summary=last_run.output_summary if last_run else None,
                last_run_error=last_run.error if last_run else None,
                breaker_tripped=breaker is not None,
                breaker_reason=breaker.reason if breaker else None,
            )
        )
    return out


@app.get("/api/agents/{name}/runs", response_model=list[AgentRunRow])
async def list_agent_runs(
    name: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[AgentRunRow]:
    """Historique des runs d'un agent (tri descendant par ``started_at``)."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    async with session_scope() as session:
        runs = await list_recent_agent_runs(session, agent_name=name, limit=limit)
    return [_run_to_row(r) for r in runs]


@app.get("/api/runs", response_model=list[AgentRunRow])
async def list_runs(limit: int = Query(default=50, ge=1, le=500)) -> list[AgentRunRow]:
    """Historique global des runs (toutes agents confondus, tri descendant)."""
    async with session_scope() as session:
        runs = await list_recent_agent_runs(session, agent_name=None, limit=limit)
    return [_run_to_row(r) for r in runs]


@app.get("/api/breakers", response_model=list[BreakerInfo])
async def list_breakers() -> list[BreakerInfo]:
    """Liste des breakers actuellement tripped (auto-reset par délai pris en compte)."""
    async with session_scope() as session:
        breakers = await list_tripped_breakers(session)
    return [_breaker_to_info(b) for b in breakers]


@app.get("/api/kpis/overview", response_model=KPIsOverview)
async def kpis_overview() -> KPIsOverview:
    """KPIs page Overview — MRR/ARR + leads 24h + tickets ouverts + breakers tripped."""
    from decimal import Decimal

    async with session_scope() as session:
        mrr = await sum_active_mrr_eur(session)
        active_subs = await _count_active_subscriptions(session)
        leads_24h = await count_recent_leads(session, window_hours=24)
        open_tickets = await count_open_tickets(session)
        tripped = await list_tripped_breakers(session)

    arr = mrr * Decimal("12.0")
    return KPIsOverview(
        mrr_eur=float(mrr),
        arr_eur=float(arr),
        active_subscriptions=active_subs,
        leads_last_24h=leads_24h,
        open_tickets=open_tickets,
        tripped_breakers=len(tripped),
        last_refreshed_at=datetime.now(UTC),
    )


async def _count_active_subscriptions(session: Any) -> int:
    """Compteur de companies en subscription active/trialing.

    Implémenté inline (pas dans repository.py) parce que c'est uniquement
    utile au dashboard et que la requête est triviale.
    """
    from sqlmodel import col, select

    from argos_ops.crm.models import Company

    stmt = select(Company).where(col(Company.subscription_status).in_(["active", "trialing"]))
    rows = list((await session.execute(stmt)).scalars().all())
    return len(rows)


__all__ = ["app"]
