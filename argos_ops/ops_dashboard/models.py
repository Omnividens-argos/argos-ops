"""Pydantic response schemas pour l'Admin Control Panel (P16.A).

Schémas séparés des SQLModel CRM pour éviter d'exposer le schéma DB côté
API et pour pouvoir formatter les types (Decimal → float, datetime → str ISO).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AgentSummary(BaseModel):
    """Vue d'un agent pour la page Agents Control (read-only en 16.A)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    last_run_status: str | None = None  # 'success' | 'failed' | 'killed_by_breaker' | None
    last_run_at: datetime | None = None
    last_run_duration_seconds: float | None = None
    last_run_output_summary: str | None = None
    last_run_error: str | None = None
    breaker_tripped: bool = False
    breaker_reason: str | None = None


class AgentRunRow(BaseModel):
    """Ligne d'``agent_runs`` exposée par l'API (page Runs + drawer logs)."""

    id: int
    agent_name: str
    command: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float | None = None
    status: str | None = None
    output_summary: str | None = None
    error: str | None = None
    cost_estimate_eur: float | None = None


class BreakerInfo(BaseModel):
    """État courant d'un breaker — affiché dans la page Breakers."""

    name: str
    tripped: bool
    tripped_at: datetime | None = None
    reason: str | None = None
    reset_after: datetime | None = None
    severity: Literal["critical", "warning", "info", "unknown"] = "unknown"


class KPIsOverview(BaseModel):
    """KPIs métier pour la page Overview (homepage du dashboard)."""

    mrr_eur: float
    arr_eur: float
    active_subscriptions: int
    leads_last_24h: int
    open_tickets: int
    tripped_breakers: int
    last_refreshed_at: datetime


def _decimal_to_float(value: Decimal | None) -> float | None:
    """Helper sérialisation Decimal → float (les Decimal ne sont pas JSON-natifs)."""
    return float(value) if value is not None else None


# =============================================================================
# Mutations P16.B — payloads request + responses
# =============================================================================
class AgentConfigPayload(BaseModel):
    """PATCH partiel sur ``agent_config``. Tous les champs sont optionnels.

    Sémantique :
    - ``None`` = ne pas toucher
    - valeur explicite = appliquer
    - ``clear_paused=true`` = effacer ``paused_until`` (seul moyen de
      faire ``paused_until = NULL``, car ``None`` est ambigu)
    """

    enabled: bool | None = None
    intensity_level: int | None = None
    schedule_cron: str | None = None
    daily_limit: int | None = None
    max_tokens_per_day: int | None = None
    tier1_threshold: int | None = None
    paused_until: datetime | None = None
    notes: str | None = None
    clear_paused: bool = False


class AgentConfigResponse(BaseModel):
    """Snapshot de ``agent_config`` retourné après PATCH."""

    agent_name: str
    enabled: bool
    intensity_level: int
    schedule_cron: str | None
    daily_limit: int | None
    max_tokens_per_day: int | None
    tier1_threshold: int
    paused_until: datetime | None
    notes: str | None
    updated_at: datetime
    updated_by: str | None


class TripBreakerPayload(BaseModel):
    """Trip manuel d'un breaker depuis l'Admin Panel."""

    reason: str
    severity: Literal["critical", "warning", "info"] = "warning"


class ManualRunResponse(BaseModel):
    """Réponse de ``POST /api/agents/{name}/runs`` — run manuel depuis le panel.

    L'exécution est synchrone (les agents Sprint 1 finissent en < 30 s), donc le
    verdict final est connu au moment du retour : ``status`` reflète la même
    valeur que la ligne ``agent_runs`` créée par ``run_agent``.
    """

    agent_name: str
    triggered_at: datetime
    status: str
    output_summary: str | None = None
    error: str | None = None
