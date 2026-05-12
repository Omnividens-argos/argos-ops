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
