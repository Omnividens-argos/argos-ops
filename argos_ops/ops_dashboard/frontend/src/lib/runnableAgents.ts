// Liste canonique des agents déclenchables manuellement via "Run now"
// depuis le panel. DOIT rester alignée avec
// ``argos_ops/ops_dashboard/app.py::RUNNABLE_AGENTS``. Si tu ajoutes un
// bot runnable côté backend, ajoute-le ici aussi (sinon le bouton sera
// caché côté UI).

export const RUNNABLE_AGENTS: ReadonlySet<string> = new Set<string>([
  "DigestBuilder",
  "EmailBot",
  "FinanceBot",
  "BotHealthBot",
  "OrchestratorBot",
  // Direction & Stratégie (P22.E).
  "StrategyBot",
  "OKRTracker",
  "BoardReporter",
  "DecisionLogger",
  // Finance & Trésorerie (P22.F).
  "InvoicePredictor",
  "ExpenseAuditor",
  "TaxBot",
  "ReconcileBot",
  "BurnRateMonitor",
  "VendorContractWatcher",
  // Sales / Commercial (P22.H).
  "OutboundBot",
  "LeadEnricher",
  "ProspectMiner",
  "IntentSignalsBot",
  "MeetingBooker",
  "DemoFollowupBot",
  "ProposalBot",
  "ContractGenerator",
  "DealRiskScorer",
  // Marketing & Growth (P22.I).
  "SEOBot",
  "ContentBot",
  "AdBot",
  "TrendSpotter",
  "NewsletterBot",
  "SocialAnalytics",
  "KeywordRadar",
  "LandingOptimizer",
  "TestimonialHunter",
  // Sprint contenu — EditorialBot runnable. Les 6 writers (LinkedInWriter…)
  // sont des skills /draft-* humain-in-the-loop → NON runnables (pas ici).
  "EditorialBot",
  // Customer Success & Support (P22.G).
  "SupportBot",
  "ReviewBot",
  "ChurnPredictor",
  "OnboardingBot",
  "HealthScoreBot",
  "KBUpdater",
  "NPSCollector",
  "UpsellSpotter",
  "EscalationRouter",
  // Produit & R&D (P22.J).
  "ChangelogBot",
  "ReleaseNotesBot",
  "FeedbackAggregator",
  "RoadmapPublisher",
  "BugTriageBot",
  // Tech / SRE / Sécurité IT (P22.C/D).
  "UptimeMonitor",
  "DependencyAuditor",
  "LogAnomalyDetector",
  "BackupVerifier",
  "SSLExpirer",
  "DNSGuard",
  "SecretRotator",
  "CIFlakeTracker",
  // Veille & Threat Intelligence (P22.D).
  "CompetitorWatcher",
  "BreachWatcher",
  "RegulatoryWatcher",
  "CVEMonitor",
  "DarkWebMonitor",
  // Juridique & Compliance (P22.K).
  "RGPDAuditor",
  "AIActComplianceBot",
  "BloctelGuard",
  "ContractDeadlineBot",
  "IncidentLogger",
  // Communication (P22.L) — EmailBot déjà en tête.
  "ReplyBot",
  "PressMonitor",
  "MediaListBuilder",
  "BrandGuardBot",
  // Documentation (P22.M) — DiagramGenerator/ADRWriter exclus (input slug requis).
  "DocLinter",
  // Meta-Ops (P22.B/C).
  "BotPerfAnalyzer",
  "ErrorTriageBot",
  "KillSwitchOperator",
  "BotConfigManager",
]);
