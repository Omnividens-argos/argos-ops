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

from argos_ops.agents.base import BaseAgent, run_agent
from argos_ops.breakers import reset as reset_breaker_facade
from argos_ops.breakers import trip as trip_breaker_facade
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentConfig, AgentRun, Breaker
from argos_ops.crm.repository import (
    count_open_tickets,
    count_recent_leads,
    get_agent_config,
    get_breaker,
    get_last_run_per_agent,
    list_recent_agent_runs,
    list_tripped_breakers,
    sum_active_mrr_eur,
    update_agent_config,
)
from argos_ops.ops_dashboard.models import (
    AgentConfigPayload,
    AgentConfigResponse,
    AgentRunRow,
    AgentSummary,
    BreakerInfo,
    KPIsOverview,
    ManualRunResponse,
    TripBreakerPayload,
)

# Agents pilotés par l'admin panel. La table peut être enrichie au fur et
# à mesure que de nouveaux agents entrent en prod (P9 ContentBot, etc.).
KNOWN_AGENTS: tuple[str, ...] = (
    "DigestBuilder",
    "EmailBot",
    "SupportBot",
    "FinanceBot",
    "BotHealthBot",
    "OrchestratorBot",
    # Direction & Stratégie (P22.E)
    "StrategyBot",
    "OKRTracker",
    "BoardReporter",
    "DecisionLogger",
    # Finance & Trésorerie (P22.F)
    "InvoicePredictor",
    "ExpenseAuditor",
    "TaxBot",
    "ReconcileBot",
    "BurnRateMonitor",
    "VendorContractWatcher",
    # Sales / Commercial (P22.H)
    "OutboundBot",
    "LeadEnricher",
    "ProspectMiner",
    "IntentSignalsBot",
    "MeetingBooker",
    "DemoFollowupBot",
    "ProposalBot",
    "ContractGenerator",
    "DealRiskScorer",
    # Marketing & Growth (P22.I)
    "SEOBot",
    "ContentBot",
    "AdBot",
    "TrendSpotter",
    "NewsletterBot",
    "SocialAnalytics",
    "BacklinkOutreach",
    "KeywordRadar",
    "LandingOptimizer",
    "WebinarPromoter",
    "TestimonialHunter",
    "CaseStudyDrafter",
    # Customer Success & Support (P22.G)
    "ReviewBot",
    "ChurnPredictor",
    "OnboardingBot",
    "HealthScoreBot",
    "KBUpdater",
    "NPSCollector",
    "UpsellSpotter",
    "EscalationRouter",
    # Produit & R&D (P22.J)
    "ChangelogBot",
    "ReleaseNotesBot",
    "FeedbackAggregator",
    "RoadmapPublisher",
    "BugTriageBot",
    # Tech / SRE / Sécurité IT (P22.C/D)
    "UptimeMonitor",
    "DependencyAuditor",
    "LogAnomalyDetector",
    "BackupVerifier",
    "SSLExpirer",
    "DNSGuard",
    "SecretRotator",
    "CIFlakeTracker",
    # Veille & Threat Intelligence (P22.D)
    "CompetitorWatcher",
    "BreachWatcher",
    "RegulatoryWatcher",
    "CVEMonitor",
    "DarkWebMonitor",
    "BountyRadar",
    # Juridique & Compliance (P22.K)
    "RGPDAuditor",
    "AIActComplianceBot",
    "BloctelGuard",
    "ContractDeadlineBot",
    "IncidentLogger",
)

# Agents qu'on peut déclencher manuellement via "Run now" du panel. SupportBot
# et SEOBot sont interactifs (slash commands) — pas de BaseAgent subclass à
# instancier, donc pas runnables ici. Les autres héritent de BaseAgent et
# passent par ``run_agent`` qui respecte les checks runtime (breaker, disabled,
# paused, daily_limit). OrchestratorBot est runnable en dry-run uniquement
# depuis le panel (live mode passe par CLI explicite).
RUNNABLE_AGENTS: frozenset[str] = frozenset(
    {
        "DigestBuilder",
        "EmailBot",
        "FinanceBot",
        "BotHealthBot",
        "OrchestratorBot",
        # Direction & Stratégie (P22.E) — bots non-interactifs.
        # DecisionLogger.run() est un health-check passif (compte les
        # décisions présentes), pas l'append : l'append reste via slash
        # /log-decision qui collecte les inputs.
        "StrategyBot",
        "OKRTracker",
        "BoardReporter",
        "DecisionLogger",
        # Finance & Trésorerie (P22.F) — bots non-interactifs.
        "InvoicePredictor",
        "ExpenseAuditor",
        "TaxBot",
        "ReconcileBot",
        "BurnRateMonitor",
        "VendorContractWatcher",
        # Sales / Commercial (P22.H) — bots non-interactifs.
        # OutboundBot reste shadow tant que OUTBOUND_LIVE_MODE=false.
        # MeetingBooker/DemoFollowup/Proposal/Contract draftent uniquement,
        # le founder envoie via zimbra-ops après validation.
        "OutboundBot",
        "LeadEnricher",
        "ProspectMiner",
        "IntentSignalsBot",
        "MeetingBooker",
        "DemoFollowupBot",
        "ProposalBot",
        "ContractGenerator",
        "DealRiskScorer",
        # Marketing & Growth (P22.I) — bots non-interactifs.
        # ContentBot publie en shadow tant que CONTENT_LIVE_MODE manque.
        # AdBot reste shadow tant que ADS_LIVE_MODE=false.
        # SEOBot.run() est un health-check passif (compte les briefs présents).
        "SEOBot",
        "ContentBot",
        "AdBot",
        "TrendSpotter",
        "NewsletterBot",
        "SocialAnalytics",
        "BacklinkOutreach",
        "KeywordRadar",
        "LandingOptimizer",
        "WebinarPromoter",
        "TestimonialHunter",
        "CaseStudyDrafter",
        # Customer Success & Support (P22.G) — bots non-interactifs.
        # SupportBot.run() est un health-check passif (compte chunks KB).
        # Le RAG Tier 1 interactif reste via /run-support-tier1 + skill kb-rag.
        "SupportBot",
        "ReviewBot",
        "ChurnPredictor",
        "OnboardingBot",
        "HealthScoreBot",
        "KBUpdater",
        "NPSCollector",
        "UpsellSpotter",
        "EscalationRouter",
        # Produit & R&D (P22.J) — bots audit-only ou drafting interne.
        "ChangelogBot",
        "ReleaseNotesBot",
        "FeedbackAggregator",
        "RoadmapPublisher",
        "BugTriageBot",
        # Tech / SRE / Sécurité IT (P22.C/D) — watchers infra read-only.
        # BackupVerifier, SSLExpirer, DNSGuard sont cron-only par design
        # (pas de slash) mais leur "Run now" reste utile pour debug ponctuel.
        "UptimeMonitor",
        "DependencyAuditor",
        "LogAnomalyDetector",
        "BackupVerifier",
        "SSLExpirer",
        "DNSGuard",
        "SecretRotator",
        "CIFlakeTracker",
        # Veille & Threat Intelligence (P22.D) — watchers veille publique.
        # BountyRadar est cron-only par design (command=None).
        "CompetitorWatcher",
        "BreachWatcher",
        "RegulatoryWatcher",
        "CVEMonitor",
        "DarkWebMonitor",
        "BountyRadar",
        # Juridique & Compliance (P22.K) — bots audit-only / interactif.
        # IncidentLogger.run() est un health-check passif (l'append du
        # post-mortem se fait via slash /log-incident).
        # BloctelGuard est cron-only par design (command=None).
        "RGPDAuditor",
        "AIActComplianceBot",
        "BloctelGuard",
        "ContractDeadlineBot",
        "IncidentLogger",
    }
)


def _build_agent(name: str) -> BaseAgent:
    """Instancie la classe agent pour le run manuel. Lazy imports pour garder
    le startup FastAPI rapide."""
    if name == "DigestBuilder":
        from argos_ops.agents.digest_builder import DigestBuilder

        return DigestBuilder()
    if name == "EmailBot":
        from argos_ops.agents.email_bot import EmailBot

        return EmailBot()
    if name == "FinanceBot":
        from argos_ops.agents.finance_bot import FinanceBot

        return FinanceBot()
    if name == "BotHealthBot":
        from argos_ops.agents.bot_health import BotHealthBot

        return BotHealthBot()
    if name == "OrchestratorBot":
        # Run now depuis le panel = dry-run par défaut (garde-fou) ;
        # le live mode passe par CLI explicite `scripts/run_orchestrator.py --live`.
        from argos_ops.agents.orchestrator import OrchestratorBot

        return OrchestratorBot(live=False)
    if name == "StrategyBot":
        from argos_ops.agents.strategy_bot import StrategyBot

        return StrategyBot()
    if name == "OKRTracker":
        from argos_ops.agents.okr_tracker import OKRTracker

        return OKRTracker()
    if name == "BoardReporter":
        from argos_ops.agents.board_reporter import BoardReporter

        return BoardReporter()
    if name == "DecisionLogger":
        # Run now = health-check passif (compte les décisions présentes
        # dans le journal canonique). L'append interactif passe par
        # /log-decision côté slash, pas par le panel.
        from argos_ops.agents.decision_logger import (
            DEFAULT_DECISIONS_PATH,
            DecisionLogger,
        )

        return DecisionLogger(output_path=DEFAULT_DECISIONS_PATH)
    if name == "InvoicePredictor":
        from argos_ops.agents.invoice_predictor import InvoicePredictor

        return InvoicePredictor()
    if name == "ExpenseAuditor":
        from argos_ops.agents.expense_auditor import ExpenseAuditor

        return ExpenseAuditor()
    if name == "TaxBot":
        from argos_ops.agents.tax_bot import TaxBot

        return TaxBot()
    if name == "ReconcileBot":
        from argos_ops.agents.reconcile_bot import ReconcileBot

        return ReconcileBot()
    if name == "BurnRateMonitor":
        from argos_ops.agents.burn_rate_monitor import BurnRateMonitor

        return BurnRateMonitor()
    if name == "VendorContractWatcher":
        from argos_ops.agents.vendor_contract_watcher import VendorContractWatcher

        return VendorContractWatcher()
    if name == "OutboundBot":
        from argos_ops.agents.outbound_bot import OutboundBot

        return OutboundBot()
    if name == "LeadEnricher":
        from argos_ops.agents.lead_enricher import LeadEnricher

        return LeadEnricher()
    if name == "ProspectMiner":
        from argos_ops.agents.prospect_miner import ProspectMiner

        return ProspectMiner()
    if name == "IntentSignalsBot":
        from argos_ops.agents.intent_signals import IntentSignalsBot

        return IntentSignalsBot()
    if name == "MeetingBooker":
        from argos_ops.agents.meeting_booker import MeetingBooker

        return MeetingBooker()
    if name == "DemoFollowupBot":
        from argos_ops.agents.demo_followup import DemoFollowupBot

        return DemoFollowupBot()
    if name == "ProposalBot":
        from argos_ops.agents.proposal_bot import ProposalBot

        return ProposalBot()
    if name == "ContractGenerator":
        from argos_ops.agents.contract_generator import ContractGenerator

        return ContractGenerator()
    if name == "DealRiskScorer":
        from argos_ops.agents.deal_risk_scorer import DealRiskScorer

        return DealRiskScorer()
    if name == "SEOBot":
        # Run now = health-check passif (compte les briefs SEO présents).
        # Le drafting interactif passe par /generate-seo-brief côté slash.
        from argos_ops.agents.seo_bot import SEOBot

        return SEOBot()
    if name == "ContentBot":
        from argos_ops.agents.content_bot import ContentBot

        return ContentBot()
    if name == "AdBot":
        from argos_ops.agents.ad_bot_live import AdBotLive

        return AdBotLive()
    if name == "TrendSpotter":
        from argos_ops.agents.trend_spotter import TrendSpotter

        return TrendSpotter()
    if name == "NewsletterBot":
        from argos_ops.agents.newsletter_bot import NewsletterBot

        return NewsletterBot()
    if name == "SocialAnalytics":
        from argos_ops.agents.social_analytics import SocialAnalytics

        return SocialAnalytics()
    if name == "BacklinkOutreach":
        from argos_ops.agents.backlink_outreach import BacklinkOutreach

        return BacklinkOutreach()
    if name == "KeywordRadar":
        from argos_ops.agents.keyword_radar import KeywordRadar

        return KeywordRadar()
    if name == "LandingOptimizer":
        from argos_ops.agents.landing_optimizer import LandingOptimizer

        return LandingOptimizer()
    if name == "WebinarPromoter":
        from argos_ops.agents.webinar_promoter import WebinarPromoter

        return WebinarPromoter()
    if name == "TestimonialHunter":
        from argos_ops.agents.testimonial_hunter import TestimonialHunter

        return TestimonialHunter()
    if name == "CaseStudyDrafter":
        from argos_ops.agents.case_study_drafter import CaseStudyDrafter

        return CaseStudyDrafter()
    if name == "SupportBot":
        # Run now = health-check passif (compte chunks KB indexés).
        # Le RAG Tier 1 interactif passe par /run-support-tier1 + skill kb-rag.
        from argos_ops.agents.support_bot import SupportBot

        return SupportBot()
    if name == "ReviewBot":
        from argos_ops.agents.review_bot import ReviewBot

        return ReviewBot()
    if name == "ChurnPredictor":
        from argos_ops.agents.churn_predictor import ChurnPredictor

        return ChurnPredictor()
    if name == "OnboardingBot":
        from argos_ops.agents.onboarding_bot import OnboardingBot

        return OnboardingBot()
    if name == "HealthScoreBot":
        from argos_ops.agents.health_score import HealthScoreBot

        return HealthScoreBot()
    if name == "KBUpdater":
        from argos_ops.agents.kb_updater import KBUpdater

        return KBUpdater()
    if name == "NPSCollector":
        from argos_ops.agents.nps_collector import NPSCollector

        return NPSCollector()
    if name == "UpsellSpotter":
        from argos_ops.agents.upsell_spotter import UpsellSpotter

        return UpsellSpotter()
    if name == "EscalationRouter":
        from argos_ops.agents.escalation_router import EscalationRouter

        return EscalationRouter()
    if name == "ChangelogBot":
        from argos_ops.agents.changelog_bot import ChangelogBot

        return ChangelogBot()
    if name == "ReleaseNotesBot":
        from argos_ops.agents.release_notes import ReleaseNotesBot

        return ReleaseNotesBot()
    if name == "FeedbackAggregator":
        from argos_ops.agents.feedback_aggregator import FeedbackAggregator

        return FeedbackAggregator()
    if name == "RoadmapPublisher":
        from argos_ops.agents.roadmap_publisher import RoadmapPublisher

        return RoadmapPublisher()
    if name == "BugTriageBot":
        from argos_ops.agents.bug_triage import BugTriageBot

        return BugTriageBot()
    if name == "UptimeMonitor":
        from argos_ops.agents.uptime_monitor import UptimeMonitor

        return UptimeMonitor()
    if name == "DependencyAuditor":
        from argos_ops.agents.dependency_auditor import DependencyAuditor

        return DependencyAuditor()
    if name == "LogAnomalyDetector":
        from argos_ops.agents.log_anomaly import LogAnomalyDetector

        return LogAnomalyDetector()
    if name == "BackupVerifier":
        from argos_ops.agents.backup_verifier import BackupVerifier

        return BackupVerifier()
    if name == "SSLExpirer":
        from argos_ops.agents.ssl_expirer import SSLExpirer

        return SSLExpirer()
    if name == "DNSGuard":
        from argos_ops.agents.dns_guard import DNSGuard

        return DNSGuard()
    if name == "SecretRotator":
        from argos_ops.agents.secret_rotator import SecretRotator

        return SecretRotator()
    if name == "CIFlakeTracker":
        from argos_ops.agents.ci_flake_tracker import CIFlakeTracker

        return CIFlakeTracker()
    if name == "CompetitorWatcher":
        from argos_ops.agents.competitor_watcher import CompetitorWatcher

        return CompetitorWatcher()
    if name == "BreachWatcher":
        from argos_ops.agents.breach_watcher import BreachWatcher

        return BreachWatcher()
    if name == "RegulatoryWatcher":
        from argos_ops.agents.regulatory_watcher import RegulatoryWatcher

        return RegulatoryWatcher()
    if name == "CVEMonitor":
        from argos_ops.agents.cve_monitor import CVEMonitor

        return CVEMonitor()
    if name == "DarkWebMonitor":
        from argos_ops.agents.dw_monitor import DarkWebMonitor

        return DarkWebMonitor()
    if name == "BountyRadar":
        from argos_ops.agents.bounty_radar import BountyRadar

        return BountyRadar()
    if name == "RGPDAuditor":
        from argos_ops.agents.rgpd_auditor import RGPDAuditor

        return RGPDAuditor()
    if name == "AIActComplianceBot":
        from argos_ops.agents.ai_act_compliance import AIActComplianceBot

        return AIActComplianceBot()
    if name == "BloctelGuard":
        from argos_ops.agents.bloctel_guard import BloctelGuard

        return BloctelGuard()
    if name == "ContractDeadlineBot":
        from argos_ops.agents.contract_deadline import ContractDeadlineBot

        return ContractDeadlineBot()
    if name == "IncidentLogger":
        # Run now = health-check passif. L'append d'un post-mortem passe
        # par /log-incident côté slash, pas par le panel.
        from argos_ops.agents.incident_logger import IncidentLogger

        return IncidentLogger()
    raise HTTPException(status_code=404, detail=f"Agent inconnu ou non runnable : {name}")


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


# =============================================================================
# Mutations P16.B
# =============================================================================
def _config_to_response(config: AgentConfig) -> AgentConfigResponse:
    return AgentConfigResponse(
        agent_name=config.agent_name,
        enabled=config.enabled,
        intensity_level=config.intensity_level,
        schedule_cron=config.schedule_cron,
        daily_limit=config.daily_limit,
        max_tokens_per_day=config.max_tokens_per_day,
        tier1_threshold=config.tier1_threshold,
        paused_until=config.paused_until,
        notes=config.notes,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )


@app.get("/api/agents/{name}/config", response_model=AgentConfigResponse)
async def get_agent_config_endpoint(name: str) -> AgentConfigResponse:
    """Charge ``agent_config`` (créée à defaults si absente)."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    async with session_scope() as session:
        config = await get_agent_config(session, name)
    return _config_to_response(config)


@app.patch("/api/agents/{name}/config", response_model=AgentConfigResponse)
async def patch_agent_config(name: str, payload: AgentConfigPayload) -> AgentConfigResponse:
    """PATCH partiel sur ``agent_config``. Prend effet au prochain run.

    Source de la mutation : Admin Control Panel (P16.B). L'agent
    ``BaseAgent.run_agent()`` consultera la nouvelle config au prochain
    cycle cron via le wrapper ``argos_ops.agent_runtime.check_runtime_state``.
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    async with session_scope() as session:
        config = await update_agent_config(
            session,
            name,
            enabled=payload.enabled,
            intensity_level=payload.intensity_level,
            schedule_cron=payload.schedule_cron,
            daily_limit=payload.daily_limit,
            max_tokens_per_day=payload.max_tokens_per_day,
            tier1_threshold=payload.tier1_threshold,
            paused_until=payload.paused_until,
            notes=payload.notes,
            updated_by="admin_panel",
            clear_paused=payload.clear_paused,
        )
        # Capture snapshot avant fermeture session (lazy loading garde la
        # référence ouverte sinon).
        snapshot = _config_to_response(config)
    return snapshot


@app.post("/api/agents/{name}/runs", response_model=ManualRunResponse, status_code=202)
async def run_agent_now(name: str) -> ManualRunResponse:
    """Déclenche manuellement un agent depuis le panel (P16.C).

    Exécution synchrone : les agents Sprint 1 finissent en < 30 s. Le wrapper
    ``run_agent`` applique les runtime checks (breaker tripped, agent disabled,
    paused, daily_limit) — un agent désactivé renverra ``skipped_disabled``
    sans être exécuté, exactement comme via cron. ``status=202`` reflète bien
    que le run a été déclenché ; le verdict final est dans le payload.

    Agents interactifs (SupportBot, SEOBot) : rejetés avec 400 car ils
    n'ont pas de subclass ``BaseAgent`` — ils s'invoquent via slash commands.
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    if name not in RUNNABLE_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"{name} est interactif — utiliser la slash command associée",
        )
    agent = _build_agent(name)
    triggered_at = datetime.now(UTC)
    result = await run_agent(agent)
    return ManualRunResponse(
        agent_name=name,
        triggered_at=triggered_at,
        status=result.status,
        output_summary=result.output_summary,
        error=result.error,
    )


@app.post("/api/breakers/{name}/trip", response_model=BreakerInfo, status_code=201)
async def trip_breaker_endpoint(name: str, payload: TripBreakerPayload) -> BreakerInfo:
    """Trip manuel d'un breaker depuis l'Admin Panel (P16.B).

    Idempotent : si déjà tripped, met à jour la raison + le timestamp.
    Pas de push Discord ici (l'admin agit consciemment, pas besoin de se
    s'auto-notifier). Le push automatique reste utilisé par les agents
    via ``argos_ops.breakers.trip_with_notification``.
    """
    await trip_breaker_facade(name, payload.reason)
    async with session_scope() as session:
        breaker = await get_breaker(session, name)
    if breaker is None:
        raise HTTPException(status_code=500, detail="Breaker créé mais introuvable")
    return _breaker_to_info(breaker)


@app.post("/api/breakers/{name}/reset", response_model=BreakerInfo)
async def reset_breaker_endpoint(name: str) -> BreakerInfo:
    """Reset manuel d'un breaker depuis l'Admin Panel. No-op si jamais tripped."""
    await reset_breaker_facade(name)
    async with session_scope() as session:
        breaker = await get_breaker(session, name)
    if breaker is None:
        # Reset sur un breaker jamais tripped → renvoyer un état "synthétique"
        # plutôt qu'une 404, pour simplifier le frontend.
        return BreakerInfo(
            name=name,
            tripped=False,
            severity=BREAKER_SEVERITY.get(name, "unknown"),
        )
    return _breaker_to_info(breaker)


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
