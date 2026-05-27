// Métadonnées par bot pour la page BotDetail (Phase 2 UX).
//
// Source de vérité côté Python : ARGOS_OPS_PLAN.md Annexe D + docs/COMPLIANCE.md
// + docs/AGENTS_PLAYBOOK.md. Ici on duplique le minimum utile à l'UI :
//   - AI Act risk class
//   - PII traité ? (RGPD)
//   - Skills consommés
//   - Chemin du YAML de config externe (si applicable)
//   - Chemin module Python + doc slash (deeplinks)
//
// Tout ce qui manque retombe sur des valeurs par défaut sûres (« minimal », « non »).

export type AIActRisk = "minimal" | "limited" | "high" | "unacceptable";

export interface BotMetadata {
  /** Doc Annexe D ref / Sprint de livraison — info contexte. */
  sprintRef?: string;
  /** Classe risque AI Act UE. Voir docs/COMPLIANCE.md § AI Act. */
  aiActRisk: AIActRisk;
  /** True si l'agent traite de la PII (RGPD applicable). */
  handlesPII: boolean;
  /** True si l'agent fait de l'outbound BtoC démarchage (Bloctel applicable). */
  needsBloctel?: boolean;
  /** Slug du skill consommé (lookup dans SKILLS_REGISTRY). */
  skills?: string[];
  /** YAML / CSV de config externe lisible / éditable depuis le panel. */
  configFile?: string;
  /** Variables d'env requises (display "manquant" si absent côté env). */
  envVars?: string[];
  /** Modèle Python (deeplink IDE). */
  pythonModule?: string;
  /** Slash command associée (sans le slash). */
  slashCommand?: string;
  /** Cadence cron canonique humaine. */
  schedule?: string;
}

export const BOT_METADATA: Record<string, BotMetadata> = {
  // ===== Direction & Stratégie =====
  StrategyBot: {
    sprintRef: "P22.E livré 2026-05-23",
    aiActRisk: "limited",
    handlesPII: false,
    pythonModule: "argos_ops/agents/strategy_bot.py",
    slashCommand: "run-strategy-digest",
    schedule: "Lundi 8h00 (hebdo)",
  },
  OKRTracker: {
    sprintRef: "P22.E livré 2026-05-23",
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/okr_tracker.py",
    slashCommand: "run-okr-review",
    configFile: "data/okr/2026-Q2.example.yaml",
    schedule: "Mardi 9h00 (hebdo)",
  },
  BoardReporter: {
    sprintRef: "P22.E livré 2026-05-23",
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/board_reporter.py",
    slashCommand: "run-board-pack",
    schedule: "1er du mois à 8h00",
  },
  DecisionLogger: {
    sprintRef: "P22.E livré 2026-05-23",
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/decision_logger.py",
    slashCommand: "log-decision",
  },

  // ===== Finance =====
  FinanceBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["stripe-ops", "zimbra-ops"],
    envVars: ["STRIPE_API_KEY", "ZIMBRA_IMAP_USER", "ZIMBRA_SMTP_PASS"],
    pythonModule: "argos_ops/agents/finance_bot.py",
    slashCommand: "daily-finance-sync",
    schedule: "8h05 quotidien",
  },
  InvoicePredictor: {
    aiActRisk: "minimal",
    handlesPII: false,
    skills: ["stripe-ops"],
    pythonModule: "argos_ops/agents/invoice_predictor.py",
    slashCommand: "run-invoice-forecast",
    schedule: "Lundi 8h10",
  },
  ExpenseAuditor: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/expense_auditor.py",
    slashCommand: "run-expense-audit",
    configFile: "data/expenses/qonto_last.csv",
    schedule: "Lundi 8h15",
  },
  TaxBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    skills: ["stripe-ops"],
    pythonModule: "argos_ops/agents/tax_bot.py",
    slashCommand: "run-tax-prep",
    schedule: "Le 5 du mois à 8h00",
  },
  ReconcileBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    skills: ["stripe-ops"],
    configFile: "data/finance/stripe_payouts.example.yaml",
    pythonModule: "argos_ops/agents/reconcile_bot.py",
    slashCommand: "run-reconcile",
    schedule: "Mardi 8h20",
  },
  BurnRateMonitor: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/strategy/burn.example.yaml",
    pythonModule: "argos_ops/agents/burn_rate_monitor.py",
    schedule: "Quotidien 8h00",
  },
  VendorContractWatcher: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/vendor_contract_watcher.py",
    schedule: "Mardi 9h00",
  },

  // ===== Sales =====
  OutboundBot: {
    sprintRef: "P13.A shadow · live mode pending",
    aiActRisk: "limited",
    handlesPII: true,
    needsBloctel: false,
    skills: ["lead-enricher", "outbound-personalizer", "claude-judge", "zimbra-ops"],
    envVars: ["OUTBOUND_LIVE_MODE", "OUTBOUND_FROM_DOMAIN"],
    pythonModule: "argos_ops/agents/outbound_bot.py",
    slashCommand: "run-outbound-bot",
    schedule: "Manuel + cron 8h30 weekday",
  },
  LeadEnricher: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["lead-enricher"],
    pythonModule: "argos_ops/agents/lead_enricher.py",
    slashCommand: "run-lead-enrich",
  },
  ProspectMiner: {
    aiActRisk: "limited",
    handlesPII: true,
    configFile: "data/sales/prospects/sources.example.yaml",
    pythonModule: "argos_ops/agents/prospect_miner.py",
    slashCommand: "run-prospect-mining",
    schedule: "Mardi + Vendredi 9h00",
  },
  IntentSignalsBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/sales/signals/sources.example.yaml",
    pythonModule: "argos_ops/agents/intent_signals.py",
    slashCommand: "run-intent-signals",
    schedule: "Quotidien 9h15",
  },
  MeetingBooker: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["zimbra-ops"],
    pythonModule: "argos_ops/agents/meeting_booker.py",
    slashCommand: "book-meeting",
  },
  DemoFollowupBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["zimbra-ops", "claude-judge"],
    pythonModule: "argos_ops/agents/demo_followup.py",
    slashCommand: "draft-demo-followup",
  },
  ProposalBot: {
    aiActRisk: "minimal",
    handlesPII: true,
    pythonModule: "argos_ops/agents/proposal_bot.py",
    slashCommand: "draft-proposal",
  },
  ContractGenerator: {
    aiActRisk: "minimal",
    handlesPII: true,
    configFile: "data/contracts/clients.example.yaml",
    pythonModule: "argos_ops/agents/contract_generator.py",
    slashCommand: "draft-contract",
  },
  DealRiskScorer: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/deal_risk_scorer.py",
    slashCommand: "run-deal-scoring",
    schedule: "Lundi 9h30",
  },

  // ===== Marketing =====
  SEOBot: {
    aiActRisk: "limited",
    handlesPII: false,
    skills: ["kb-rag", "seo-brief-writer", "claude-judge"],
    configFile: "data/seo/keywords.yaml",
    pythonModule: "argos_ops/agents/seo_bot.py",
    slashCommand: "generate-seo-brief",
  },
  ContentBot: {
    sprintRef: "P9 draft · P11 live mode pending",
    aiActRisk: "limited",
    handlesPII: false,
    skills: ["kb-rag", "content-writer", "claude-judge", "content-scheduler"],
    envVars: ["LINKEDIN_ACCESS_TOKEN", "MASTODON_TOKEN"],
    pythonModule: "argos_ops/agents/content_bot.py",
    slashCommand: "draft-content",
    schedule: "Mardi + Jeudi 9h00",
  },
  AdBot: {
    sprintRef: "P12 shadow · P12.B live pending",
    aiActRisk: "limited",
    handlesPII: false,
    skills: ["ads-creative-writer", "ads-optimizer", "claude-judge"],
    envVars: ["GOOGLE_ADS_REFRESH_TOKEN", "LINKEDIN_ADS_TOKEN", "META_ADS_TOKEN", "ADS_LIVE_MODE"],
    pythonModule: "argos_ops/agents/ad_bot_live.py",
    slashCommand: "draft-ad",
  },
  TrendSpotter: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/trend_spotter.py",
    slashCommand: "run-trend-spot",
    schedule: "Quotidien 7h30",
  },
  NewsletterBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["claude-judge", "zimbra-ops"],
    pythonModule: "argos_ops/agents/newsletter_bot.py",
    slashCommand: "draft-newsletter",
    schedule: "Premier vendredi du mois",
  },
  SocialAnalytics: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/social_analytics.py",
    slashCommand: "run-social-analytics",
    schedule: "Lundi 8h45",
  },
  BacklinkOutreach: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["claude-judge", "zimbra-ops"],
    pythonModule: "argos_ops/agents/backlink_outreach.py",
    slashCommand: "run-backlink-outreach",
  },
  KeywordRadar: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/seo/keywords.yaml",
    pythonModule: "argos_ops/agents/keyword_radar.py",
    slashCommand: "run-keyword-radar",
    schedule: "Mardi 9h00",
  },
  LandingOptimizer: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/landing_optimizer.py",
    slashCommand: "run-landing-optim",
    schedule: "Lundi 10h00",
  },
  WebinarPromoter: {
    aiActRisk: "limited",
    handlesPII: false,
    skills: ["claude-judge"],
    pythonModule: "argos_ops/agents/webinar_promoter.py",
    slashCommand: "promote-webinar",
  },
  TestimonialHunter: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["claude-judge", "zimbra-ops"],
    pythonModule: "argos_ops/agents/testimonial_hunter.py",
    slashCommand: "draft-testimonial-request",
  },
  CaseStudyDrafter: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["claude-judge"],
    pythonModule: "argos_ops/agents/case_study_drafter.py",
    slashCommand: "draft-case-study",
  },

  // ===== CS / Support =====
  SupportBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["kb-rag"],
    pythonModule: "argos_ops/agents/support_bot.py",
    slashCommand: "run-support-tier1",
  },
  ReviewBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["zimbra-ops", "claude-judge"],
    pythonModule: "argos_ops/agents/review_bot.py",
    slashCommand: "run-review-campaign",
  },
  ChurnPredictor: {
    aiActRisk: "limited",
    handlesPII: true,
    pythonModule: "argos_ops/agents/churn_predictor.py",
    slashCommand: "run-churn-predict",
    schedule: "Quotidien 8h00",
  },
  OnboardingBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["zimbra-ops", "claude-judge"],
    pythonModule: "argos_ops/agents/onboarding_bot.py",
    slashCommand: "run-onboarding",
    schedule: "Quotidien 8h30",
  },
  HealthScoreBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/health_score.py",
    slashCommand: "run-health-scores",
    schedule: "Quotidien 7h00",
  },
  KBUpdater: {
    aiActRisk: "minimal",
    handlesPII: false,
    skills: ["claude-judge"],
    pythonModule: "argos_ops/agents/kb_updater.py",
    slashCommand: "draft-kb-update",
  },
  NPSCollector: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["zimbra-ops"],
    pythonModule: "argos_ops/agents/nps_collector.py",
    slashCommand: "run-nps-campaign",
  },
  UpsellSpotter: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/upsell_spotter.py",
    slashCommand: "run-upsell-spots",
    schedule: "Vendredi 9h00",
  },
  EscalationRouter: {
    aiActRisk: "limited",
    handlesPII: true,
    pythonModule: "argos_ops/agents/escalation_router.py",
    slashCommand: "run-ticket-triage",
    schedule: "Toutes les 15 min",
  },

  // ===== Produit & R&D =====
  ChangelogBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/changelog_bot.py",
    slashCommand: "draft-changelog",
  },
  ReleaseNotesBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    skills: ["claude-judge"],
    pythonModule: "argos_ops/agents/release_notes.py",
    slashCommand: "draft-release-notes",
  },
  FeedbackAggregator: {
    aiActRisk: "minimal",
    handlesPII: true,
    pythonModule: "argos_ops/agents/feedback_aggregator.py",
    slashCommand: "run-feedback-digest",
    schedule: "Vendredi 9h30",
  },
  RoadmapPublisher: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/roadmap_publisher.py",
    slashCommand: "publish-roadmap",
  },
  BugTriageBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/bug_triage.py",
    slashCommand: "run-bug-triage",
    schedule: "Quotidien 9h00",
  },

  // ===== Tech / SRE =====
  UptimeMonitor: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/uptime/endpoints.yaml",
    pythonModule: "argos_ops/agents/uptime_monitor.py",
    slashCommand: "run-uptime",
    schedule: "Toutes les 5 min",
  },
  DependencyAuditor: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/dependency_auditor.py",
    slashCommand: "run-dep-audit",
    schedule: "Quotidien 7h00",
  },
  LogAnomalyDetector: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/log_anomaly.py",
    slashCommand: "run-log-anomalies",
    schedule: "Toutes les heures",
  },
  BackupVerifier: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/backup_verifier.py",
    schedule: "Quotidien 6h00",
  },
  SSLExpirer: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/ssl_expirer.py",
    schedule: "Quotidien 6h30",
  },
  DNSGuard: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/dns_guard.py",
    schedule: "Toutes les heures",
  },
  SecretRotator: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/secrets/rotation_log.yaml",
    pythonModule: "argos_ops/agents/secret_rotator.py",
    slashCommand: "run-secret-audit",
    schedule: "Quotidien 6h45",
  },
  CIFlakeTracker: {
    aiActRisk: "minimal",
    handlesPII: false,
    envVars: ["GITHUB_TOKEN"],
    pythonModule: "argos_ops/agents/ci_flake_tracker.py",
    slashCommand: "run-ci-flakes",
    schedule: "Lundi 9h00",
  },

  // ===== Veille =====
  CompetitorWatcher: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/competitor_watcher.py",
    slashCommand: "run-competitor-watch",
    schedule: "Lundi 9h45",
  },
  BreachWatcher: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/breach_watcher.py",
    slashCommand: "run-breach-watch",
    schedule: "Quotidien 6h00",
  },
  RegulatoryWatcher: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/regulatory_watcher.py",
    slashCommand: "run-regulatory-watch",
    schedule: "Quotidien 7h00",
  },
  CVEMonitor: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/cve_monitor.py",
    slashCommand: "run-cve-monitor",
    schedule: "Quotidien 6h15",
  },
  DarkWebMonitor: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/dw_monitor.py",
    slashCommand: "run-dw-monitor",
    schedule: "Quotidien 6h30",
  },
  BountyRadar: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/bounty_radar.py",
  },

  // ===== Juridique & Compliance =====
  RGPDAuditor: {
    aiActRisk: "high",
    handlesPII: false,
    configFile: "data/compliance/rgpd_registry.example.yaml",
    pythonModule: "argos_ops/agents/rgpd_auditor.py",
    slashCommand: "run-rgpd-audit",
    schedule: "Lundi 10h00",
  },
  AIActComplianceBot: {
    aiActRisk: "high",
    handlesPII: false,
    pythonModule: "argos_ops/agents/ai_act_compliance.py",
    slashCommand: "run-ai-act-audit",
    schedule: "Lundi 10h15",
  },
  BloctelGuard: {
    aiActRisk: "high",
    handlesPII: true,
    needsBloctel: true,
    pythonModule: "argos_ops/agents/bloctel_guard.py",
  },
  ContractDeadlineBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/contract_deadline.py",
    slashCommand: "run-contract-deadlines",
    schedule: "Lundi 10h30",
  },
  IncidentLogger: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/incident_logger.py",
    slashCommand: "log-incident",
  },

  // ===== Communication =====
  EmailBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["zimbra-ops", "email-classifier", "kb-rag"],
    envVars: ["ZIMBRA_IMAP_USER", "ZIMBRA_IMAP_PASS", "ZIMBRA_SMTP_USER", "ZIMBRA_SMTP_PASS"],
    pythonModule: "argos_ops/agents/email_bot.py",
    slashCommand: "run-email-bot",
    schedule: "Toutes les 15 min",
  },
  ReplyBot: {
    aiActRisk: "limited",
    handlesPII: true,
    skills: ["claude-judge", "kb-rag"],
    pythonModule: "argos_ops/agents/reply_bot.py",
    slashCommand: "draft-replies",
  },
  PressMonitor: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/press_monitor.py",
    slashCommand: "run-press-monitor",
    schedule: "Quotidien 7h00",
  },
  PressReleaseDrafter: {
    aiActRisk: "limited",
    handlesPII: false,
    skills: ["claude-judge"],
    pythonModule: "argos_ops/agents/press_release_drafter.py",
    slashCommand: "draft-press-release",
  },
  MediaListBuilder: {
    aiActRisk: "limited",
    handlesPII: true,
    pythonModule: "argos_ops/agents/media_list_builder.py",
    slashCommand: "run-media-list-build",
    schedule: "Lundi 9h15",
  },
  CrisisCommBot: {
    aiActRisk: "limited",
    handlesPII: false,
    skills: ["claude-judge"],
    pythonModule: "argos_ops/agents/crisis_comm.py",
    slashCommand: "draft-crisis-response",
  },
  SpokespersonPrep: {
    aiActRisk: "limited",
    handlesPII: false,
    pythonModule: "argos_ops/agents/spokesperson_prep.py",
    slashCommand: "prep-interview",
  },
  BrandGuardBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/brand_guard.py",
    slashCommand: "run-brand-audit",
    schedule: "Quotidien 8h00",
  },

  // ===== Documentation =====
  DocLinter: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/doc_linter.py",
    slashCommand: "run-doc-lint",
    schedule: "Lundi 11h00",
  },
  DiagramGenerator: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/diagram_generator.py",
    slashCommand: "gen-diagram",
  },
  ADRWriter: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/adr_writer.py",
    slashCommand: "write-adr",
  },

  // ===== Meta-Ops =====
  DigestBuilder: {
    aiActRisk: "minimal",
    handlesPII: false,
    skills: ["digest-builder"],
    pythonModule: "argos_ops/agents/digest_builder.py",
    slashCommand: "morning-digest",
    schedule: "Quotidien 8h00 Paris",
  },
  BotHealthBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/bot_health.py",
    slashCommand: "run-bot-health",
    schedule: "Toutes les 2 h",
  },
  OrchestratorBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/agent_config/baseline.yaml",
    pythonModule: "argos_ops/agents/orchestrator.py",
    slashCommand: "orchestrate",
  },
  BotPerfAnalyzer: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/bot_perf_analyzer.py",
    slashCommand: "run-bot-perf",
    schedule: "Lundi 10h00",
  },
  ErrorTriageBot: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/error_triage.py",
    slashCommand: "run-error-triage",
    schedule: "Quotidien 8h15",
  },
  KillSwitchOperator: {
    aiActRisk: "minimal",
    handlesPII: false,
    pythonModule: "argos_ops/agents/kill_switch.py",
  },
  BotConfigManager: {
    aiActRisk: "minimal",
    handlesPII: false,
    configFile: "data/agent_config/baseline.yaml",
    pythonModule: "argos_ops/agents/bot_config_manager.py",
    slashCommand: "run-config-drift",
    schedule: "Quotidien 8h00",
  },
};

export interface SkillInfo {
  slug: string;
  label: string;
  description: string;
  /** Chemin relatif sous .claude/skills/ ou indication d'un helper Python. */
  location: string;
}

export const SKILLS_REGISTRY: Record<string, SkillInfo> = {
  "kb-rag": {
    slug: "kb-rag",
    label: "kb-rag",
    description: "Recherche similarité fastembed local + pgvector cosine sur la KB Argos.",
    location: ".claude/skills/kb-rag/",
  },
  "claude-judge": {
    slug: "claude-judge",
    label: "claude-judge",
    description: "Agent-juge Tier 1 — note draft sur 3 axes (factual / tone / legal).",
    location: ".claude/skills/claude-judge/",
  },
  "zimbra-ops": {
    slug: "zimbra-ops",
    label: "zimbra-ops",
    description: "IMAP/SMTP OVH Zimbra — lire / drafter / envoyer / marquer emails.",
    location: ".claude/skills/zimbra-ops/",
  },
  "stripe-ops": {
    slug: "stripe-ops",
    label: "stripe-ops",
    description: "Wrapper Stripe + MRR/ARR + dunning J+3/J+7/J+15.",
    location: ".claude/skills/stripe-ops/",
  },
  "email-classifier": {
    slug: "email-classifier",
    label: "email-classifier",
    description: "Classifie inbound en lead_chaud / question_tech / sav / spam / etc.",
    location: ".claude/skills/email-classifier/",
  },
  "digest-builder": {
    slug: "digest-builder",
    label: "digest-builder",
    description: "Construit l'embed Discord du digest quotidien.",
    location: ".claude/skills/digest-builder/",
  },
  "seo-brief-writer": {
    slug: "seo-brief-writer",
    label: "seo-brief-writer",
    description: "Brief blog SEO structuré depuis keyword + KB Argos.",
    location: ".claude/skills/seo-brief-writer/",
  },
  "content-writer": {
    slug: "content-writer",
    label: "content-writer",
    description: "Post social adapté au canal (LinkedIn / Mastodon) depuis topic + KB.",
    location: ".claude/skills/content-writer/",
  },
  "ads-creative-writer": {
    slug: "ads-creative-writer",
    label: "ads-creative-writer",
    description: "3 variantes d'annonce Ads (Google RSA / LinkedIn / Meta).",
    location: ".claude/skills/ads-creative-writer/",
  },
  "ads-optimizer": {
    slug: "ads-optimizer",
    label: "ads-optimizer",
    description: "Analyse CSV Ads, propose 3-5 recommandations chiffrées.",
    location: ".claude/skills/ads-optimizer/",
  },
  "content-scheduler": {
    slug: "content-scheduler",
    label: "content-scheduler",
    description: "Choisit heure / jour optimal pour publier un draft social.",
    location: ".claude/skills/content-scheduler/",
  },
  "lead-enricher": {
    slug: "lead-enricher",
    label: "lead-enricher",
    description: "Enrichit un lead BtoB (email, titre, signaux ICP, BANT).",
    location: ".claude/skills/lead-enricher/",
  },
  "outbound-personalizer": {
    slug: "outbound-personalizer",
    label: "outbound-personalizer",
    description: "1 ligne hyper-personnalisée pour cold email.",
    location: ".claude/skills/outbound-personalizer/",
  },
  compliance: {
    slug: "compliance",
    label: "compliance (helper)",
    description: "Helper Python — checks déterministes RGPD / AI Act.",
    location: "argos_ops/compliance.py",
  },
};

export function lookupBot(name: string): BotMetadata {
  return (
    BOT_METADATA[name] ?? {
      aiActRisk: "minimal",
      handlesPII: false,
    }
  );
}

export function lookupSkill(slug: string): SkillInfo | null {
  return SKILLS_REGISTRY[slug] ?? null;
}

export const AI_ACT_LABEL: Record<AIActRisk, string> = {
  minimal: "Minimal",
  limited: "Limited (transparence)",
  high: "High risk",
  unacceptable: "Unacceptable",
};
