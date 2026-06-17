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

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from argos_ops import fleet_memory
from argos_ops.agents.base import BaseAgent, RunResult, run_agent
from argos_ops.breakers import reset as reset_breaker_facade
from argos_ops.breakers import trip as trip_breaker_facade
from argos_ops.config import get_settings, refresh_settings
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
from argos_ops.logging import redact_secrets
from argos_ops.ops_dashboard import atelier, atelier_audit, atelier_history, auth, console
from argos_ops.ops_dashboard.api.marketing import router as marketing_router
from argos_ops.ops_dashboard.api.poles import router as poles_router
from argos_ops.ops_dashboard.api.pub import router as pub_router
from argos_ops.ops_dashboard.api.stripe_webhook import router as stripe_router
from argos_ops.ops_dashboard.cohorts import compute_cohorts
from argos_ops.ops_dashboard.inbox_actions import reject_draft, validate_draft
from argos_ops.ops_dashboard.inbox_scanner import (
    read_output_content,
    read_peek_file,
    scan_all_outputs,
    scan_inbox_drafts,
)
from argos_ops.ops_dashboard.models import (
    AgentConfigPayload,
    AgentConfigResponse,
    AgentPerfStats,
    AgentRunRow,
    AgentSummary,
    BotMemoryView,
    BreakerInfo,
    CashSnapshot,
    CashSubBreakdown,
    CashTicketBreakdown,
    CohortsResponse,
    ConsoleActPayload,
    ConsoleActResponse,
    ConsoleInResponse,
    ConsoleStatusResponse,
    FactCreatePayload,
    FactPinPayload,
    FactRow,
    FilePeekResponse,
    FleetMemoryStats,
    FleetMemoryView,
    HealthAgentBreakdown,
    HealthSnapshot,
    InboxActionPayload,
    InboxActionResponse,
    InboxDraft,
    InSourceRow,
    KPIsOverview,
    ManualRunResponse,
    OpsLoginPayload,
    OpsLoginResponse,
    OutputContentResponse,
    PipelineSnapshot,
    TripBreakerPayload,
    VisibleBotMemory,
    YamlConfigPatch,
    YamlConfigResponse,
)
from argos_ops.ops_dashboard.pipeline_reader import read_pipeline
from argos_ops.ops_dashboard.yaml_config import (
    ALLOWED_CONFIG_FILES,
    read_config_file,
    write_config_file,
)

# Agents pilotés par l'admin panel. La table peut être enrichie au fur et
# à mesure que de nouveaux agents entrent en prod (P9 ContentBot, etc.).
KNOWN_AGENTS: tuple[str, ...] = (
    "DigestBuilder",
    "EmailBot",
    "SupportBot",
    "FinanceBot",
    "FleetWatchdog",
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
    "KeywordRadar",
    "LandingOptimizer",
    "TestimonialHunter",
    # Sprint contenu — writers multi-canal (skills humain-in-the-loop,
    # invoqués via /draft-* : non-runnables) + EditorialBot (orchestrateur,
    # runnable). Cf. argos_ops/social/ + argos_ops/agents/editorial_bot.py.
    "LinkedInWriter",
    "MastodonWriter",
    "BlueskyWriter",
    "MetaWriter",
    "XWriter",
    "TruthSocialWriter",
    "EditorialBot",
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
    # Juridique & Compliance (P22.K)
    "RGPDAuditor",
    "AIActComplianceBot",
    "BloctelGuard",
    "ContractDeadlineBot",
    "IncidentLogger",
    # Communication (P22.L) — EmailBot deja en tete de tuple (P5 historique)
    "ReplyBot",
    "PressMonitor",
    "MediaListBuilder",
    "BrandGuardBot",
    # Documentation & Knowledge interne (P22.M)
    "DocLinter",
    "DiagramGenerator",
    "ADRWriter",
    # Meta-Ops (P22.B/C + Axe 3.2) — DigestBuilder/FleetWatchdog/OrchestratorBot
    # deja en tete de tuple (P4/P22.B + fusion D-031 des 4 watchers agent_runs)
    "KillSwitchOperator",
    "BotConfigManager",
    "MemoryCurator",
    "CapabilityRouter",
)

# Racine de la mémoire de flotte (Cockpit LOT 2). Module-level pour que les
# tests puissent la patcher vers un tmp_path.
FLEET_MEMORY_ROOT = fleet_memory.FLEET_MEMORY_DIR

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
        "FleetWatchdog",
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
        "KeywordRadar",
        "LandingOptimizer",
        "TestimonialHunter",
        # Sprint contenu — EditorialBot est runnable (lit le digest TrendSpotter
        # et écrit une queue de recommandations). Les 6 writers (LinkedInWriter,
        # MastodonWriter, BlueskyWriter, MetaWriter, XWriter, TruthSocialWriter)
        # sont des SKILLS humain-in-the-loop invoqués via /draft-* : pas de
        # subclass BaseAgent → exclus de RUNNABLE_AGENTS (Run now renvoie 400).
        "EditorialBot",
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
        "BackupVerifier",
        "SSLExpirer",
        "DNSGuard",
        "SecretRotator",
        "CIFlakeTracker",
        # Veille & Threat Intelligence (P22.D) — watchers veille publique.
        "CompetitorWatcher",
        "BreachWatcher",
        "RegulatoryWatcher",
        "CVEMonitor",
        "DarkWebMonitor",
        # Juridique & Compliance (P22.K) — bots audit-only / interactif.
        # IncidentLogger.run() est un health-check passif (l'append du
        # post-mortem se fait via slash /log-incident).
        # BloctelGuard est cron-only par design (command=None).
        "RGPDAuditor",
        "AIActComplianceBot",
        "BloctelGuard",
        "ContractDeadlineBot",
        "IncidentLogger",
        # Communication (P22.L) — EmailBot deja runnable depuis P5/P16.B.
        # ReplyBot drafte du contenu (humain-in-the-loop).
        "ReplyBot",
        "PressMonitor",
        "MediaListBuilder",
        "BrandGuardBot",
        # Documentation & Knowledge interne (P22.M).
        # DocLinter audit-only sans input. DiagramGenerator + ADRWriter
        # exigent un slug/draft passé via slash (input humain), donc
        # exclus de RUNNABLE_AGENTS : leur "Run now" panel n'aurait pas
        # de contexte (cf. clause "documenté pourquoi : interactif" de
        # la checklist QA).
        "DocLinter",
        # Meta-Ops (P22.B/C + Axe 3.2) — DigestBuilder/FleetWatchdog/OrchestratorBot
        # deja runnable depuis P4/P22.B. FleetWatchdog (fusion D-031 des 4 watchers
        # agent_runs) tourne en Task Scheduler toutes les 6h mais "Run now" reste
        # utile pour debug ponctuel.
        "KillSwitchOperator",
        "BotConfigManager",
        "MemoryCurator",
        "CapabilityRouter",
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
    if name == "FleetWatchdog":
        from argos_ops.agents.fleet_watchdog import FleetWatchdog

        return FleetWatchdog()
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
    if name == "EditorialBot":
        from argos_ops.agents.editorial_bot import EditorialBot

        return EditorialBot()
    if name == "SocialAnalytics":
        from argos_ops.agents.social_analytics import SocialAnalytics

        return SocialAnalytics()
    if name == "KeywordRadar":
        from argos_ops.agents.keyword_radar import KeywordRadar

        return KeywordRadar()
    if name == "LandingOptimizer":
        from argos_ops.agents.landing_optimizer import LandingOptimizer

        return LandingOptimizer()
    if name == "TestimonialHunter":
        from argos_ops.agents.testimonial_hunter import TestimonialHunter

        return TestimonialHunter()
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
    if name == "ReplyBot":
        from argos_ops.agents.reply_bot import ReplyBot

        return ReplyBot()
    if name == "PressMonitor":
        from argos_ops.agents.press_monitor import PressMonitor

        return PressMonitor()
    if name == "MediaListBuilder":
        from argos_ops.agents.media_list_builder import MediaListBuilder

        return MediaListBuilder()
    if name == "BrandGuardBot":
        from argos_ops.agents.brand_guard import BrandGuardBot

        return BrandGuardBot()
    if name == "DocLinter":
        from argos_ops.agents.doc_linter import DocLinter

        return DocLinter()
    if name == "KillSwitchOperator":
        from argos_ops.agents.kill_switch import KillSwitchOperator

        return KillSwitchOperator()
    if name == "BotConfigManager":
        from argos_ops.agents.bot_config_manager import BotConfigManager

        return BotConfigManager()
    if name == "MemoryCurator":
        from argos_ops.agents.memory_curator import MemoryCurator

        return MemoryCurator()
    if name == "CapabilityRouter":
        from argos_ops.agents.capability_router import CapabilityRouter

        return CapabilityRouter()
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

# Webhooks tiers (Stripe, …). Montés sous /api/* — accessibles publiquement
# via Caddy (Stripe doit pouvoir nous poster), donc auth = signature HMAC
# côté handler, pas basic auth Caddy.
app.include_router(stripe_router)

# Cockpit archi v2 (pôle/agent/script) — sert la mémoire + insights des pôles
# au shell poles.html. Read-mostly ; le handoff écrit dans le pôle source.
app.include_router(poles_router)

# Pôle Marketing (S2) — file de drafts, calendrier éditorial, KB éditable,
# charte/ton, stats engagement. Mutations scoped à la donnée du pôle Marketing.
app.include_router(marketing_router)

# Pôle Pub (S3) — dashboard campagnes, jauge budget + breaker ad_spend_runaway,
# validation de créas A/B, recos chiffrées « appliquer » (shadow), simulateur.
# Mutations scoped à la donnée du pôle Pub ; le breaker est un latch dans budget.yaml.
app.include_router(pub_router)


# =============================================================================
# Durcissement auth (P16.B/D) — defense-in-depth APPLICATIVE, en complément
# de Caddy. Fail-open : si OPS_DASHBOARD_* n'est pas configuré, le panel reste
# ouvert (dev local + tests inchangés). Cf. auth.py + docs/INFRA_OPS_PANEL.md.
# =============================================================================
@app.middleware("http")
async def ops_auth_guard(request: Request, call_next: Any) -> Any:
    # Le préflight CORS (OPTIONS) ne porte jamais de credentials → laisser
    # passer pour que CORSMiddleware réponde correctement.
    if request.method == "OPTIONS":
        return await call_next(request)

    settings = get_settings()

    # 1. IP allowlist (peer TCP direct). Garde-fou anti-exposition sans Caddy ;
    #    le filtrage « vraie IP » se fait côté Caddy (cf. ops.Caddyfile).
    client_ip = request.client.host if request.client is not None else None
    if not auth.ip_is_allowed(client_ip, settings):
        return JSONResponse(status_code=403, content={"detail": "IP non autorisée"})

    # 2. Basic / JWT. Seulement si l'auth est armée et hors chemins exemptés
    #    (health, webhook Stripe, login).
    if (
        auth.is_basic_auth_enabled(settings)
        and not auth.is_path_exempt(request.url.path)
        and not auth.request_is_authenticated(request.headers.get("Authorization"), settings)
    ):
        headers = {}
        # On ne propose le challenge Basic au navigateur que si la 2FA TOTP
        # n'est pas active (sinon le Basic seul ne passe pas → on évite une
        # popup trompeuse, le client doit utiliser /api/auth/login).
        if not auth.is_totp_enabled(settings):
            headers["WWW-Authenticate"] = 'Basic realm="Argos Ops"'
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentification requise"},
            headers=headers,
        )

    return await call_next(request)


@app.post("/api/auth/login", response_model=OpsLoginResponse)
async def ops_login(payload: OpsLoginPayload) -> OpsLoginResponse:
    """Échange identifiants Basic (+ code TOTP si configuré) contre un JWT.

    404 si l'auth applicative n'est pas armée (rien à connecter). 503 si le
    secret JWT manque (impossible d'émettre une session). 401 si creds ou
    code TOTP invalides.
    """
    settings = get_settings()
    if not auth.is_basic_auth_enabled(settings):
        raise HTTPException(status_code=404, detail="Auth applicative désactivée")
    if settings.ops_dashboard_jwt_secret is None:
        raise HTTPException(status_code=503, detail="OPS_DASHBOARD_JWT_SECRET non configuré")
    if not auth.verify_basic_auth(payload.username, payload.password, settings):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not auth.verify_totp(payload.totp_code or "", settings):
        raise HTTPException(status_code=401, detail="Code TOTP invalide")
    token = auth.issue_session_token(payload.username, settings)
    return OpsLoginResponse(token=token, expires_in_minutes=auth.DEFAULT_SESSION_TTL_MINUTES)


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
        inputs=run.inputs,
        outputs=run.outputs,
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


@app.get("/api/runs/{run_id}", response_model=AgentRunRow)
async def get_run(run_id: int) -> AgentRunRow:
    """Un run précis avec ses IN/OUT — provenance d'un fait mémoire (Memory Hub)."""
    async with session_scope() as session:
        run = await session.get(AgentRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run introuvable : {run_id}")
        return _run_to_row(run)


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


# =============================================================================
# Mémoire de flotte — Cockpit Console (LOT 2)
# =============================================================================
def _fact_to_row(fact: fleet_memory.Fact) -> FactRow:
    return FactRow(
        id=fact.id,
        bot=fact.bot,
        kind=fact.kind,
        body=fact.body,
        source=fact.source,
        confidence=fact.confidence,
        status=fact.status,
        ttl_days=fact.ttl_days,
        created_at=fact.created_at,
        archived_at=fact.archived_at,
        tags=list(fact.tags),
        pinned=fact.pinned,
        run_id=fact.run_id,
    )


@app.get("/api/agents/{name}/memory", response_model=BotMemoryView)
async def get_agent_memory(
    name: str,
    include_archived: bool = Query(default=False),
) -> BotMemoryView:
    """Assemble le « IN mémoire » d'un bot : sa mémoire + celle qu'il peut lire.

    ``reads`` = bots dont ``name`` lit la mémoire (graphe sortant) ;
    ``read_by`` = bots qui lisent celle de ``name`` (graphe entrant, ``"*"``
    inclus). Respecte strictement le graphe d'accès de ``MEMORY.md``.
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")

    own = await fleet_memory.read_memory(
        name, root=FLEET_MEMORY_ROOT, include_archived=include_archived
    )
    visible_map = await fleet_memory.visible_memory(name, root=FLEET_MEMORY_ROOT)
    graph = await fleet_memory.load_access_graph(root=FLEET_MEMORY_ROOT)

    reads = sorted(b for b in visible_map if b != name)
    read_by = sorted(
        other
        for other, targets in graph.items()
        if other != name and (name in targets or fleet_memory.GRAPH_WILDCARD in targets)
    )
    visible = [
        VisibleBotMemory(bot=b, facts=[_fact_to_row(f) for f in mem.facts])
        for b, mem in sorted(visible_map.items())
        if b != name
    ]
    return BotMemoryView(
        bot=name,
        own=[_fact_to_row(f) for f in own.facts],
        visible=visible,
        reads=reads,
        read_by=read_by,
    )


@app.post("/api/agents/{name}/memory", response_model=FactRow, status_code=201)
async def append_agent_memory(name: str, payload: FactCreatePayload) -> FactRow:
    """Ajoute manuellement un fait à la mémoire d'un bot depuis la Console.

    Idempotent par corps (même contenu = même ``fact_id``, pas de doublon).
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Le corps du fait est vide")
    fact = await fleet_memory.append_fact(
        name,
        payload.body,
        kind=payload.kind,
        source=payload.source or "admin_panel",
        confidence=payload.confidence,
        tags=tuple(payload.tags),
        ttl_days=payload.ttl_days,
        pinned=payload.pinned,
        root=FLEET_MEMORY_ROOT,
    )
    return _fact_to_row(fact)


@app.post("/api/agents/{name}/memory/{fact_id}/archive", response_model=FactRow)
async def archive_agent_memory(name: str, fact_id: str) -> FactRow:
    """Archive un fait (soft delete). Suppression dure = MemoryCurator (P20)."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    fact = await fleet_memory.archive_fact(name, fact_id, root=FLEET_MEMORY_ROOT)
    if fact is None:
        raise HTTPException(status_code=404, detail=f"Fait introuvable : {fact_id}")
    return _fact_to_row(fact)


# =============================================================================
# Mémoire de flotte — Memory Hub global (vue + contrôle manuel)
# =============================================================================
def _ensure_known_fact_bot(name: str) -> None:
    """Garde-fou des mutations Memory Hub : bot connu du panel OU déjà sur disque.

    (Un dossier mémoire peut exister pour un bot retiré du catalogue — on doit
    quand même pouvoir nettoyer ses faits.)
    """
    if name in KNOWN_AGENTS or name in fleet_memory.list_bots(root=FLEET_MEMORY_ROOT):
        return
    raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")


@app.get("/api/memory", response_model=FleetMemoryView)
async def get_fleet_memory() -> FleetMemoryView:
    """Toute la mémoire de flotte, tous bots confondus (actifs + archivés).

    Alimente le Memory Hub : le filtrage (bot / kind / statut / texte) se fait
    côté client — l'échelle (fichiers locaux) ne justifie pas de pagination.
    """
    facts: list[FactRow] = []
    for bot in fleet_memory.list_bots(root=FLEET_MEMORY_ROOT):
        mem = await fleet_memory.read_memory(bot, root=FLEET_MEMORY_ROOT, include_archived=True)
        facts.extend(_fact_to_row(f) for f in mem.facts)
    facts.sort(key=lambda f: f.created_at, reverse=True)

    stats = FleetMemoryStats(
        total=len(facts),
        active=sum(1 for f in facts if f.status == "active"),
        archived=sum(1 for f in facts if f.status == "archived"),
        pinned=sum(1 for f in facts if f.pinned),
        bots=len({f.bot for f in facts}),
    )
    return FleetMemoryView(
        facts=facts,
        stats=stats,
        bots=sorted({f.bot for f in facts}),
        kinds=sorted({f.kind for f in facts}),
    )


@app.post("/api/memory/{name}/{fact_id}/pin", response_model=FactRow)
async def pin_fleet_fact(name: str, fact_id: str, payload: FactPinPayload) -> FactRow:
    """(Dé)pin un fait — un fait pinned n'est jamais nettoyé par MemoryCurator."""
    _ensure_known_fact_bot(name)
    fact = await fleet_memory.set_pinned(name, fact_id, payload.pinned, root=FLEET_MEMORY_ROOT)
    if fact is None:
        raise HTTPException(status_code=404, detail=f"Fait introuvable : {fact_id}")
    return _fact_to_row(fact)


@app.post("/api/memory/{name}/{fact_id}/restore", response_model=FactRow)
async def restore_fleet_fact(name: str, fact_id: str) -> FactRow:
    """Restaure un fait archivé (pendant inverse de l'archivage)."""
    _ensure_known_fact_bot(name)
    fact = await fleet_memory.restore_fact(name, fact_id, root=FLEET_MEMORY_ROOT)
    if fact is None:
        raise HTTPException(status_code=404, detail=f"Fait introuvable : {fact_id}")
    return _fact_to_row(fact)


@app.delete("/api/memory/{name}/{fact_id}", status_code=204)
async def delete_fleet_fact(name: str, fact_id: str) -> Response:
    """Supprime définitivement un fait (hard delete, contrôle manuel assumé)."""
    _ensure_known_fact_bot(name)
    deleted = await fleet_memory.delete_fact(name, fact_id, root=FLEET_MEMORY_ROOT)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Fait introuvable : {fact_id}")
    return Response(status_code=204)


# =============================================================================
# Console bot — découple générer / agir (Cockpit LOT 3)
# =============================================================================
@app.get("/api/agents/{name}/console/in", response_model=ConsoleInResponse)
async def get_console_in(
    name: str,
    own: bool = Query(default=True),
    accessible: bool = Query(default=True),
) -> ConsoleInResponse:
    """Compose le « IN » mémoire d'un bot pour la console (sources cochables).

    Mémoire propre + mémoire accessible (graphe). Skills / data sont overlayés
    côté frontend (depuis ``botMetadata``). C'est la base réversible de la
    génération : voir ce qu'on donnerait à l'IA avant de générer quoi que ce soit.
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    comp = await console.compose_in(
        name,
        include_own_memory=own,
        include_accessible_memory=accessible,
        include_skills=False,
        include_data=False,
        root=FLEET_MEMORY_ROOT,
    )
    return ConsoleInResponse(
        bot=comp.bot,
        sources=[
            InSourceRow(key=s.key, label=s.label, count=s.count, detail=s.detail)
            for s in comp.sources
        ],
        context_chars=len(comp.context_text),
    )


@app.get("/api/agents/{name}/console/status", response_model=ConsoleStatusResponse)
async def get_console_status(name: str) -> ConsoleStatusResponse:
    """État de la console : moteur génération dispo + SHADOW/LIVE + runnable."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    # ``live`` relu à chaud (Settings fraîches) → le badge SHADOW/LIVE reflète un
    # flip de flag sans redémarrer le panel (Axe 4). ``engine_enabled`` reste sur
    # le singleton (cohérent avec le gate des WS atelier).
    return ConsoleStatusResponse(
        engine_enabled=get_settings().ops_atelier_enabled,
        live=console.read_live_status(name),
        runnable=name in RUNNABLE_AGENTS,
    )


@app.websocket("/api/agents/{name}/console/generate")
async def console_generate_ws(websocket: WebSocket, name: str) -> None:
    """GÉNÈRE (réversible) : compose le IN → moteur atelier headless → draft +
    auto-jugement → verdict. Ne déclenche AUCUNE action. Auth + flag identiques
    à l'atelier (même moteur Claude Code local)."""
    settings = get_settings()
    client_ip = websocket.client.host if websocket.client is not None else None
    if name not in KNOWN_AGENTS or not atelier.ws_authorized(
        client_ip=client_ip,
        authorization=websocket.headers.get("authorization"),
        token=websocket.query_params.get("token"),
        settings=settings,
    ):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    if not settings.ops_atelier_enabled:
        await websocket.send_json({"type": "disabled"})
        await websocket.close()
        return

    session = atelier.AtelierSession(claude_bin=settings.ops_atelier_claude_bin)
    await websocket.send_json({"type": "ready"})
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") != "generate":
                continue
            task = str(msg.get("task", "")).strip()
            if not task:
                continue
            comp = await console.compose_in(
                name,
                include_own_memory=bool(msg.get("own", True)),
                include_accessible_memory=bool(msg.get("accessible", True)),
                include_skills=bool(msg.get("skills_on", True)),
                include_data=bool(msg.get("data_on", True)),
                skills=tuple(str(s) for s in (msg.get("skills") or [])),
                data_summary=str(msg.get("data_summary", "")),
                root=FLEET_MEMORY_ROOT,
            )
            prompt = console.build_generate_prompt(name, task, comp)
            buffer: list[str] = []
            async for event in session.send(prompt, permission_mode="read"):
                if event.get("kind") == "text":
                    buffer.append(str(event.get("text", "")))
                    await websocket.send_json({"type": "delta", "text": event["text"]})
                elif event.get("kind") == "error":
                    await websocket.send_json(
                        {"type": "error", "message": event.get("message", "")}
                    )
            raw = "".join(buffer)
            try:
                result = console.parse_generation(raw)
                await websocket.send_json(
                    {
                        "type": "verdict",
                        "draft": result.draft,
                        "verdict": result.verdict,
                        "scores": {
                            "factual": result.report.factual_score,
                            "tone": result.report.tone_score,
                            "legal": result.report.legal_score,
                            "global": result.report.global_score,
                        },
                        "rationale": result.report.rationale,
                    }
                )
            except ValueError as exc:
                # Parsing raté : on rend quand même le brut, sans verdict.
                await websocket.send_json({"type": "parse_error", "message": str(exc), "raw": raw})
    except WebSocketDisconnect:
        session.interrupt()


@app.post("/api/agents/{name}/console/act", response_model=ConsoleActResponse)
async def console_act(name: str, payload: ConsoleActPayload) -> ConsoleActResponse:
    """AGIR (irréversible) : déclenche le bot APRÈS validation. Gâchette stricte.

    ``killed`` → jamais. Sinon → approbation humaine obligatoire. L'action réelle
    vs shadow dépend du flag live propre au bot (cf. ``is_bot_live``)."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")
    # AGIR = point de vérité : on rafraîchit le singleton Settings pour qu'un flip
    # de flag live reflété par le badge le soit AUSSI par le bot lancé ci-dessous
    # (cohérence badge↔action sans redémarrage, Axe 4).
    settings = refresh_settings()
    live = console.is_bot_live(name, settings)

    def _audit(*, acted: bool, outcome: str, result: RunResult | None = None) -> None:
        atelier_audit.record(
            atelier_audit.AuditEvent(
                action="console_act",
                mode="console",
                bot=name,
                verdict=payload.verdict,
                approved=payload.approved,
                acted=acted,
                live=live,
                outcome=outcome,
                result_status=result.status if result else None,
                result_error=result.error if result else None,
            )
        )

    if not console.can_act(payload.verdict, human_approved=payload.approved):
        killed = payload.verdict == "killed"
        reason = "verdict killed — action bloquée" if killed else "approbation humaine requise"
        _audit(acted=False, outcome="blocked_killed" if killed else "blocked_not_approved")
        return ConsoleActResponse(acted=False, live=live, reason=reason)

    if name not in RUNNABLE_AGENTS:
        _audit(acted=False, outcome="not_runnable")
        return ConsoleActResponse(
            acted=False, live=live, reason=f"{name} non lançable (interactif / watcher)"
        )

    result = await run_agent(_build_agent(name))
    _audit(acted=True, outcome="executed", result=result)
    # Redaction homogène avec le retour MCP run_bot : un bot mal écrit qui
    # mettrait un secret dans output_summary/error ne le fait pas fuiter dans
    # le navigateur cockpit (défense en profondeur, Axe 4).
    return ConsoleActResponse(
        acted=True,
        live=live,
        status=result.status,
        output_summary=redact_secrets(result.output_summary) if result.output_summary else None,
        error=redact_secrets(result.error) if result.error else None,
    )


# =============================================================================
# Atelier libre embarqué — Claude Code piloté depuis le panel (Cockpit)
# =============================================================================
@app.get("/api/atelier/status")
async def atelier_status() -> dict[str, bool]:
    """Indique si l'atelier est activé (flag local OPS_ATELIER_ENABLED)."""
    return {"enabled": get_settings().ops_atelier_enabled}


@app.get("/api/atelier/sessions")
async def atelier_sessions() -> list[dict[str, str]]:
    """Liste les anciennes conversations Claude de ce repo (récentes d'abord)."""
    if not get_settings().ops_atelier_enabled:
        return []
    return [meta.__dict__ for meta in atelier_history.list_sessions()]


@app.get("/api/atelier/sessions/{session_id}")
async def atelier_transcript(session_id: str) -> dict[str, Any]:
    """Relit le transcript d'une conversation (pour la rouvrir et la reprendre)."""
    if not get_settings().ops_atelier_enabled:
        raise HTTPException(status_code=404, detail="Atelier désactivé")
    return {"id": session_id, "items": atelier_history.read_transcript(session_id)}


async def _stream_atelier_turn(
    websocket: WebSocket,
    session: atelier.AtelierSession,
    text: str,
    permission_mode: atelier.PermissionMode,
) -> None:
    """Streame un tour Claude vers le WS (tâche de fond, ne lève jamais)."""
    try:
        async for event in session.send(text, permission_mode=permission_mode):
            await websocket.send_json({"type": "event", "event": event})
        await websocket.send_json({"type": "turn_complete", "session_id": session.session_id})
    except WebSocketDisconnect:
        session.interrupt()
    except Exception as exc:  # un tour qui crashe ne doit pas tuer la session
        logger.warning(f"Atelier — tour en erreur : {exc}")
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "event", "event": {"kind": "error", "message": str(exc)}}
            )


@app.websocket("/api/atelier/ws")
async def atelier_ws(websocket: WebSocket) -> None:
    """WebSocket full-duplex de l'atelier. Auth re-vérifiée ici (le middleware
    HTTP ne couvre pas les WS). Local-only + flag opt-in."""
    settings = get_settings()
    client_ip = websocket.client.host if websocket.client is not None else None
    if not atelier.ws_authorized(
        client_ip=client_ip,
        authorization=websocket.headers.get("authorization"),
        token=websocket.query_params.get("token"),
        settings=settings,
    ):
        await websocket.close(code=4403)
        return

    await websocket.accept()
    if not settings.ops_atelier_enabled:
        await websocket.send_json({"type": "disabled"})
        await websocket.close()
        return

    session = atelier.AtelierSession(claude_bin=settings.ops_atelier_claude_bin)
    await websocket.send_json({"type": "ready"})
    current_turn: asyncio.Task[None] | None = None

    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")
            if mtype == "interrupt":
                # Tue le proc ; on NE cancel PAS current_turn : la sentinelle du
                # _pump clôt le tour naturellement quand le proc est réellement
                # mort → le verrou _busy reste pris jusque-là (invariant strict
                # « 1 subprocess à la fois », sans fenêtre 2-process). La Task
                # devient .done() d'elle-même et rouvre le slot (Axe 4).
                session.interrupt()
            elif mtype == "resume":
                # Rouvre une ancienne conversation : le prochain tour reprendra
                # son contexte via --resume <session_id>.
                sid = msg.get("session_id")
                if isinstance(sid, str) and sid:
                    session.session_id = sid
                    await websocket.send_json({"type": "resumed", "session_id": sid})
            elif mtype == "user":
                text = str(msg.get("text", "")).strip()
                mode = msg.get("permission_mode", "read")
                if mode not in ("read", "fleet"):
                    mode = "read"
                if not text:
                    continue
                if current_turn is not None and not current_turn.done():
                    # Un tour est déjà in-flight : on REJETTE (rate-limit Axe 4),
                    # pas de file d'attente — l'humain renverra après le tour.
                    await websocket.send_json({"type": "busy"})
                    continue
                atelier_audit.record(
                    atelier_audit.AuditEvent(
                        action="atelier_turn",
                        mode=mode,
                        prompt_excerpt=atelier_audit.excerpt(text),
                        session_id=session.session_id,
                        client_ip=client_ip,
                    )
                )
                current_turn = asyncio.create_task(
                    _stream_atelier_turn(websocket, session, text, mode)
                )
    except WebSocketDisconnect:
        session.interrupt()
        if current_turn is not None:
            current_turn.cancel()


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


@app.get("/api/inbox/drafts", response_model=list[InboxDraft])
async def list_inbox_drafts() -> list[InboxDraft]:
    """File unifiée des drafts en attente de validation humaine (P16 / Phase 1 UX).

    Scanne ``data/`` à la recherche des markdown drafts produits par les bots
    (ContentBot, SEOBot, ProposalBot, etc.), lit leur frontmatter YAML et
    filtre ceux qui sont encore en attente (status draft / pending_review /
    drafted). Retour trié du plus récent au plus ancien.
    """
    return scan_inbox_drafts()


@app.post(
    "/api/inbox/drafts/validate",
    response_model=InboxActionResponse,
    status_code=200,
)
async def validate_inbox_draft(payload: InboxActionPayload, draft_id: str) -> InboxActionResponse:
    """Marque un draft comme ``validated`` + horodate dans son frontmatter.

    ``draft_id`` est passé en query-param parce qu'il contient des '/' qui
    posent problème en path-param. L'idempotence est garantie par le scanner
    qui filtre les drafts en statut final (cf. ``inbox_scanner._FINAL_STATUSES``).
    """
    path = validate_draft(draft_id, note=payload.note)
    return InboxActionResponse(
        id=draft_id,
        status="validated",
        file_path=_inbox_relative(path),
        timestamp=datetime.now(UTC),
    )


@app.post(
    "/api/inbox/drafts/reject",
    response_model=InboxActionResponse,
    status_code=200,
)
async def reject_inbox_draft(payload: InboxActionPayload, draft_id: str) -> InboxActionResponse:
    """Marque un draft comme ``rejected`` + raison dans son frontmatter."""
    path = reject_draft(draft_id, reason=payload.reason)
    return InboxActionResponse(
        id=draft_id,
        status="rejected",
        file_path=_inbox_relative(path),
        timestamp=datetime.now(UTC),
    )


@app.get("/api/outputs/index", response_model=list[InboxDraft])
async def list_all_outputs() -> list[InboxDraft]:
    """Index complet des drafts produits par les bots (Phase 4 UX).

    Identique à ``/api/inbox/drafts`` mais sans filtre status — renvoie aussi
    les drafts ``validated`` / ``rejected`` / ``posted``. Source : scan
    filesystem (cf. ``inbox_scanner.scan_all_outputs``). Le frontend filtre
    côté UI.
    """
    return scan_all_outputs()


@app.get("/api/outputs/content", response_model=OutputContentResponse)
async def get_output_content(path: str = Query(..., min_length=1)) -> OutputContentResponse:
    """Lit le contenu raw d'un draft markdown (read-only).

    ``path`` est le chemin relatif au repo (ex.
    ``data/content/drafts/2026-05-14-linkedin-faux-positifs-dast.md``).
    Whitelist implicite : seuls les ``.md`` sont servis, et le path doit
    être sous la racine du repo (anti-traversée).
    """
    content = read_output_content(path)
    return OutputContentResponse(file_path=path, content=content)


@app.get("/api/files/peek", response_model=FilePeekResponse)
async def peek_file(path: str = Query(..., min_length=1)) -> FilePeekResponse:
    """Lit le contenu raw d'un fichier source pour la modale des cards IN/OUT.

    ``path`` est relatif au repo (ex. ``data/uptime/endpoints.yaml``).
    Whitelist d'extensions texte + plafond de taille côté
    ``inbox_scanner.read_peek_file`` (anti-traversée).
    """
    content, truncated = read_peek_file(path)
    return FilePeekResponse(
        file_path=path,
        content=content,
        truncated=truncated,
        suffix=Path(path).suffix.lower(),
    )


@app.get("/api/agents/{name}/config-yaml", response_model=YamlConfigResponse)
async def get_agent_config_yaml(name: str) -> YamlConfigResponse:
    """Lit le YAML de config externe d'un bot (whitelist côté backend).

    Retourne ``exists=False`` si le fichier n'a pas encore été créé (cas
    fréquent pour les ``.example.yaml`` non dupliqués).
    """
    if name not in ALLOWED_CONFIG_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun fichier de config externe pour {name}",
        )
    rel, text, exists = read_config_file(name)
    last_modified: datetime | None = None
    if exists:
        from argos_ops.ops_dashboard.yaml_config import get_allowed_path

        path = get_allowed_path(name)
        last_modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return YamlConfigResponse(
        agent_name=name,
        relative_path=rel,
        exists=exists,
        content=text,
        last_modified=last_modified,
    )


@app.patch("/api/agents/{name}/config-yaml", response_model=YamlConfigResponse)
async def patch_agent_config_yaml(name: str, payload: YamlConfigPatch) -> YamlConfigResponse:
    """Écrit le YAML de config externe d'un bot.

    Valide la syntaxe YAML avant écriture et fait un backup ``.bak.<ts>``.
    Refuse les .csv (read-only) et les payloads > 256 KB.
    """
    if name not in ALLOWED_CONFIG_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun fichier de config externe pour {name}",
        )
    rel, text = write_config_file(name, payload.content)
    from argos_ops.ops_dashboard.yaml_config import get_allowed_path

    path = get_allowed_path(name)
    return YamlConfigResponse(
        agent_name=name,
        relative_path=rel,
        exists=True,
        content=text,
        last_modified=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
    )


@app.get("/api/agents/{name}/perf", response_model=AgentPerfStats)
async def get_agent_perf(
    name: str, window_days: int = Query(default=7, ge=1, le=90)
) -> AgentPerfStats:
    """Stats agrégées sur la fenêtre demandée (par défaut 7 j).

    Utilisé par la card « État live » de BotDetail. Toutes les durées sont
    en secondes. Pas de cache : les valeurs sont recalculées à chaque appel
    (volume < 1000 lignes typique, requête < 10 ms).
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent inconnu : {name}")

    from sqlalchemy import and_
    from sqlmodel import col, select

    from argos_ops.crm.models import AgentRun

    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    async with session_scope() as session:
        stmt = select(AgentRun).where(
            and_(col(AgentRun.agent_name) == name, col(AgentRun.started_at) >= cutoff)
        )
        rows = list((await session.execute(stmt)).scalars().all())

    total = len(rows)
    success = sum(1 for r in rows if r.status == "success")
    failed = sum(1 for r in rows if r.status == "failed")
    skipped = sum(1 for r in rows if (r.status or "").startswith("skipped_"))
    durations = sorted(
        d
        for r in rows
        if (d := _duration_seconds(r)) is not None and r.status in {"success", "failed"}
    )
    error_rate = (failed / total) if total > 0 else 0.0
    return AgentPerfStats(
        agent_name=name,
        window_days=window_days,
        total_runs=total,
        success_count=success,
        failed_count=failed,
        skipped_count=skipped,
        error_rate=round(error_rate, 4),
        avg_duration_seconds=(sum(durations) / len(durations)) if durations else None,
        p50_duration_seconds=_percentile(durations, 0.5),
        p95_duration_seconds=_percentile(durations, 0.95),
    )


def _inbox_relative(path: Path) -> str:
    """Chemin relatif au repo, en forward-slash (cohérent cross-OS)."""
    from argos_ops.ops_dashboard.inbox_scanner import _project_root

    return str(path.resolve().relative_to(_project_root().resolve())).replace("\\", "/")


def _percentile(sorted_values: list[float], q: float) -> float | None:
    """Percentile sur une liste TRIÉE croissante. Renvoie ``None`` si vide."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = max(0, min(len(sorted_values) - 1, round(q * (len(sorted_values) - 1))))
    return sorted_values[idx]


@app.get("/api/sales/pipeline", response_model=PipelineSnapshot)
async def sales_pipeline() -> PipelineSnapshot:
    """Snapshot du pipeline commercial (Phase 5 UX).

    Source : ``data/sales/deals/pipe.yaml`` (maintenu manuellement par le
    fondateur). Si le fichier est absent, retourne ``has_data=False`` —
    l'UI affichera un empty state avec un YAML d'exemple.
    """
    return read_pipeline()


@app.get("/api/cash/cohorts", response_model=CohortsResponse)
async def cash_cohorts(months: int = Query(default=6, ge=2, le=24)) -> CohortsResponse:
    """Table de rétention par cohorte de signup mensuelle (Phase 5 UX).

    Approximation tant qu'on n'a pas d'historique d'events Stripe locaux :
    « retained » = ``subscription_status ∈ {active, trialing}`` AUJOURD'HUI.
    """
    async with session_scope() as session:
        return await compute_cohorts(session, months_tracked=months)


@app.get("/api/cash/snapshot", response_model=CashSnapshot)
async def cash_snapshot() -> CashSnapshot:
    """Snapshot Cash & Customers — alimente la page éponyme (Phase 3 UX).

    Lit Companies (Stripe) + Leads + Tickets en quelques requêtes scalaires.
    Pas de cache : volume < 10 k rows, requêtes < 50 ms typique.
    """
    from decimal import Decimal

    from sqlmodel import col, select

    from argos_ops.crm.models import Company, Ticket

    async with session_scope() as session:
        mrr = await sum_active_mrr_eur(session)
        arr = mrr * Decimal("12.0")

        # Companies par subscription_status
        companies_stmt = select(Company)
        companies = list((await session.execute(companies_stmt)).scalars().all())
        active = sum(1 for c in companies if c.subscription_status == "active")
        trialing = sum(1 for c in companies if c.subscription_status == "trialing")
        past_due = sum(1 for c in companies if c.subscription_status == "past_due")
        canceled = sum(1 for c in companies if c.subscription_status == "canceled")
        known_statuses = {"active", "trialing", "past_due", "canceled"}
        other = sum(
            1
            for c in companies
            if c.subscription_status not in known_statuses and c.subscription_status is not None
        )

        # Leads par fenêtre
        leads_24h = await count_recent_leads(session, window_hours=24)
        leads_7d = await count_recent_leads(session, window_hours=24 * 7)
        leads_30d = await count_recent_leads(session, window_hours=24 * 30)

        # Tickets par priorité (tous statuts ouverts)
        tickets_stmt = select(Ticket).where(col(Ticket.status) == "open")
        tickets = list((await session.execute(tickets_stmt)).scalars().all())
        p0 = sum(1 for t in tickets if (t.priority or "").lower() in {"p0", "critical"})
        p1 = sum(1 for t in tickets if (t.priority or "").lower() in {"p1", "high"})
        p2 = sum(1 for t in tickets if (t.priority or "").lower() in {"p2", "medium"})
        t_other = max(0, len(tickets) - p0 - p1 - p2)

    return CashSnapshot(
        mrr_eur=float(mrr),
        arr_eur=float(arr),
        active_subscriptions=active + trialing,
        subs_breakdown=CashSubBreakdown(
            active=active,
            trialing=trialing,
            past_due=past_due,
            canceled=canceled,
            other=other,
        ),
        leads_last_24h=leads_24h,
        leads_last_7d=leads_7d,
        leads_last_30d=leads_30d,
        open_tickets=len(tickets),
        tickets_breakdown=CashTicketBreakdown(p0=p0, p1=p1, p2=p2, other=t_other),
        last_refreshed_at=datetime.now(UTC),
    )


@app.get("/api/health/snapshot", response_model=HealthSnapshot)
async def health_snapshot() -> HealthSnapshot:
    """Snapshot Health & Compliance — alimente la page éponyme (Phase 3 UX).

    Source unique pour la santé de la flotte : combien de runs récents, combien
    d'agents dans quel état config, et la liste des breakers tripped. La partie
    compliance (AI Act / RGPD / Bloctel) est calculée client-side depuis
    ``BOT_METADATA`` — pas besoin de la dupliquer côté backend.
    """
    from sqlmodel import col, select

    from argos_ops.crm.models import AgentConfig as AgentConfigModel
    from argos_ops.crm.models import AgentRun

    # DB ping
    db_ok = False
    try:
        async with session_scope() as session:
            from sqlalchemy import text as sql_text

            await session.execute(sql_text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
    cutoff_7d = datetime.now(UTC) - timedelta(days=7)

    async with session_scope() as session:
        # Runs récents
        runs_24h_stmt = select(AgentRun).where(col(AgentRun.started_at) >= cutoff_24h)
        runs_24h = list((await session.execute(runs_24h_stmt)).scalars().all())
        runs_7d_stmt = select(AgentRun).where(col(AgentRun.started_at) >= cutoff_7d)
        runs_7d = list((await session.execute(runs_7d_stmt)).scalars().all())

        # Agents par état config
        cfg_stmt = select(AgentConfigModel)
        configs = list((await session.execute(cfg_stmt)).scalars().all())
        enabled = sum(1 for c in configs if c.enabled)
        disabled = sum(1 for c in configs if not c.enabled)
        now = datetime.now(UTC)
        paused = sum(1 for c in configs if c.paused_until is not None and c.paused_until > now)

        # Breakers tripped
        tripped = await list_tripped_breakers(session)

    return HealthSnapshot(
        db_ok=db_ok,
        runs_last_24h=len(runs_24h),
        runs_last_7d=len(runs_7d),
        failed_last_24h=sum(1 for r in runs_24h if r.status == "failed"),
        failed_last_7d=sum(1 for r in runs_7d if r.status == "failed"),
        agents_breakdown=HealthAgentBreakdown(
            enabled=enabled,
            disabled=disabled,
            paused=paused,
        ),
        tripped_breakers=len(tripped),
        tripped_breaker_names=[b.name for b in tripped],
        last_refreshed_at=datetime.now(UTC),
    )


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
