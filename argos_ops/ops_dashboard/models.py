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


class RunIOItem(BaseModel):
    """Une entrée (IN) ou sortie (OUT) structurée d'un run — cf.
    ``argos_ops.agents.base.IOItem``. Affiché dans l'onglet Travail (IN→OUT)
    du détail bot."""

    label: str
    kind: str = "other"
    detail: str | None = None
    ref: str | None = None
    count: int | None = None


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
    inputs: list[RunIOItem] | None = None
    outputs: list[RunIOItem] | None = None


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


class PipelineDeal(BaseModel):
    """Un deal du pipeline commercial (Phase 5 UX).

    Source : ``data/sales/deals/pipe.yaml`` (maintenu manuellement par le
    fondateur, lu par DealRiskScorer).
    """

    deal_id: str
    company: str
    stage: str
    amount_eur: float | None = None
    last_activity_at: datetime | None = None
    days_since_activity: int | None = None
    owner: str | None = None
    notes: str | None = None
    risk_level: Literal["healthy", "stalled", "at_risk"] = "healthy"


class PipelineSnapshot(BaseModel):
    """Snapshot du pipeline commercial — alimente la page Pipeline."""

    has_data: bool
    file_path: str
    total_deals: int
    total_amount_eur: float
    deals: list[PipelineDeal]
    last_refreshed_at: datetime


class CohortRow(BaseModel):
    """Une ligne de cohorte de rétention (Phase 5 UX)."""

    signup_month: str  # "2026-01"
    cohort_size: int
    retained_by_month: list[int]  # nombre actifs à M+0, M+1, M+2…


class CohortsResponse(BaseModel):
    """Table de rétention par cohorte de signup (Phase 5 UX)."""

    has_data: bool
    months_tracked: int
    rows: list[CohortRow]
    last_refreshed_at: datetime


class OutputContentResponse(BaseModel):
    """Contenu raw d'un output markdown (Phase 4 UX — Outputs library)."""

    file_path: str
    content: str


class FilePeekResponse(BaseModel):
    """Contenu raw d'un fichier source (modale « voir la donnée » des cards
    IN/OUT de l'onglet Travail). Read-only, texte, whitelist d'extensions."""

    file_path: str
    content: str
    truncated: bool = False
    suffix: str


class InboxActionPayload(BaseModel):
    """Payload pour POST /api/inbox/{id}/validate et /reject.

    ``note`` (validate) ou ``reason`` (reject) — capté tel quel dans le
    frontmatter du markdown pour audit. Limité à 280 chars côté backend.
    """

    note: str | None = None
    reason: str | None = None


class InboxActionResponse(BaseModel):
    """Confirmation d'une mutation inbox — renvoie l'état nouveau du draft."""

    id: str
    status: str
    file_path: str
    timestamp: datetime


class YamlConfigResponse(BaseModel):
    """Lecture d'un YAML de config externe (Phase 2 UX bot detail)."""

    agent_name: str
    relative_path: str
    exists: bool
    content: str
    last_modified: datetime | None = None


class YamlConfigPatch(BaseModel):
    """Payload PATCH /api/agents/{name}/config-yaml."""

    content: str


class CashSubBreakdown(BaseModel):
    """Décomposition Stripe par statut d'abonnement."""

    active: int
    trialing: int
    past_due: int
    canceled: int
    other: int


class CashTicketBreakdown(BaseModel):
    """Décomposition tickets par priorité (P0/P1/P2/autre)."""

    p0: int
    p1: int
    p2: int
    other: int


class CashSnapshot(BaseModel):
    """Snapshot Cash & Customers — alimente la page éponyme (Phase 3 UX).

    Tout est dérivable de ``companies`` (Stripe) + ``leads`` + ``tickets``,
    pas de table dédiée. Coût constant — quelques counts SQL.
    """

    mrr_eur: float
    arr_eur: float
    active_subscriptions: int
    subs_breakdown: CashSubBreakdown
    leads_last_24h: int
    leads_last_7d: int
    leads_last_30d: int
    open_tickets: int
    tickets_breakdown: CashTicketBreakdown
    last_refreshed_at: datetime


class HealthAgentBreakdown(BaseModel):
    """Décomposition des agents par état config (Phase 3 UX page Health)."""

    enabled: int
    disabled: int
    paused: int


class HealthSnapshot(BaseModel):
    """Snapshot Health & Compliance — alimente la page éponyme.

    Infrastructure & flotte : DB OK ?, combien de runs, combien d'agents
    dans quel état, breakers tripped. La partie compliance (AI Act / RGPD /
    Bloctel) est calculée client-side depuis ``BOT_METADATA`` (lib/botMetadata.ts)
    + la liste agents — pas besoin de la dupliquer en DB.
    """

    db_ok: bool
    runs_last_24h: int
    runs_last_7d: int
    failed_last_24h: int
    failed_last_7d: int
    agents_breakdown: HealthAgentBreakdown
    tripped_breakers: int
    tripped_breaker_names: list[str]
    last_refreshed_at: datetime


class AgentPerfStats(BaseModel):
    """Stats 7 jours utilisées par la card « État live » de BotDetail."""

    agent_name: str
    window_days: int
    total_runs: int
    success_count: int
    failed_count: int
    skipped_count: int
    error_rate: float
    avg_duration_seconds: float | None
    p50_duration_seconds: float | None
    p95_duration_seconds: float | None


class InboxDraft(BaseModel):
    """Un draft en attente de validation humaine dans l'Inbox unifiée.

    Scanné depuis le filesystem (``data/<scope>/...``) — on lit le frontmatter
    YAML de chaque .md pour extraire status / titre / date. Les drafts au
    statut ``validated`` / ``posted`` / ``sent`` sont filtrés out (ils ne sont
    plus en attente).
    """

    id: str
    kind: Literal["email", "social", "proposal", "seo", "press", "doc", "other"]
    title: str
    summary: str | None = None
    status: str
    created_at: datetime
    file_path: str
    agent_name: str | None = None


class OpsLoginPayload(BaseModel):
    """Corps du POST /api/auth/login (durcissement panel, P16.B/D)."""

    username: str
    password: str
    totp_code: str | None = None  # requis seulement si TOTP est configuré


class OpsLoginResponse(BaseModel):
    """Réponse du login : JWT de session à présenter en Bearer."""

    token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in_minutes: int


# =============================================================================
# Mémoire de flotte — Cockpit Console (LOT 2)
# =============================================================================
class FactRow(BaseModel):
    """Un fait de mémoire de flotte sérialisé pour l'API (cf. fleet_memory.Fact)."""

    id: str
    bot: str
    kind: str
    body: str
    source: str | None
    confidence: str
    status: str
    ttl_days: int | None
    created_at: datetime
    archived_at: datetime | None
    tags: list[str]
    pinned: bool = False


class VisibleBotMemory(BaseModel):
    """Mémoire d'un autre bot que celui-ci a le droit de lire (graphe d'accès)."""

    bot: str
    facts: list[FactRow]


class BotMemoryView(BaseModel):
    """Le « IN mémoire » assemblé d'un bot pour la Console Cockpit.

    - ``own`` : faits extraits par le bot lui-même.
    - ``visible`` : mémoire des bots qu'il a le droit de lire (graphe).
    - ``reads`` / ``read_by`` : arêtes du graphe d'accès (sortantes / entrantes).
    """

    bot: str
    own: list[FactRow]
    visible: list[VisibleBotMemory]
    reads: list[str]
    read_by: list[str]


class FactCreatePayload(BaseModel):
    """Corps du POST d'ajout manuel d'un fait depuis la Console."""

    body: str
    kind: str = "note"
    source: str | None = None
    confidence: Literal["low", "medium", "high"] = "medium"
    tags: list[str] = []
    ttl_days: int | None = None
    pinned: bool = False


class FactPinPayload(BaseModel):
    """Corps du POST pin/unpin d'un fait (Memory Hub)."""

    pinned: bool


class FleetMemoryStats(BaseModel):
    """Compteurs globaux affichés en tête du Memory Hub."""

    total: int
    active: int
    archived: int
    pinned: int
    bots: int


class FleetMemoryView(BaseModel):
    """Vue globale de la mémoire de flotte (Memory Hub du cockpit).

    ``facts`` = tous les faits de tous les bots (actifs + archivés), triés du
    plus récent au plus ancien — le filtrage fin (bot / kind / statut /
    recherche) se fait côté client, l'échelle reste petite (fichiers locaux).
    ``kinds`` = vocabulaire observé, pour alimenter le filtre.
    """

    facts: list[FactRow]
    stats: FleetMemoryStats
    bots: list[str]
    kinds: list[str]


# =============================================================================
# Console bot — découple générer / agir (Cockpit LOT 3)
# =============================================================================
class InSourceRow(BaseModel):
    """Une source du IN (case à cocher) composée côté backend."""

    key: str
    label: str
    count: int
    detail: str = ""


class ConsoleInResponse(BaseModel):
    """Le IN composé d'un bot : sources cochées + taille du contexte assemblé."""

    bot: str
    sources: list[InSourceRow]
    context_chars: int


class ConsoleStatusResponse(BaseModel):
    """État de la console d'un bot : moteur dispo + SHADOW/LIVE + runnable."""

    engine_enabled: bool  # OPS_ATELIER_ENABLED — la génération live est dispo
    live: bool  # AGIR déclencherait une action réelle (vs brouillon shadow)
    runnable: bool  # le bot peut être déclenché (« act »)


class ConsoleActPayload(BaseModel):
    """Corps du POST act : verdict de la génération + approbation humaine."""

    verdict: Literal["auto_send", "queued", "killed"]
    approved: bool = False


class ConsoleActResponse(BaseModel):
    """Résultat d'un AGIR depuis la console."""

    acted: bool  # l'action a-t-elle été déclenchée
    live: bool  # en réel (vs shadow)
    status: str | None = None  # status du run si acted
    output_summary: str | None = None
    error: str | None = None
    reason: str | None = None  # si refusé (gâchette)
