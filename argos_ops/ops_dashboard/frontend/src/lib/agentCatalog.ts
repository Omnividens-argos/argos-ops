import {
  BookOpen,
  Compass,
  Cpu,
  DollarSign,
  Eye,
  Handshake,
  LifeBuoy,
  Megaphone,
  Package,
  Scale,
  Shield,
  TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// Catalogue des agents Argos Ops — 12 services × 79 bots (révision 2026-05-23).
// Source de vérité : ARGOS_OPS_PLAN.md Annexe D.
// Structure : 1 bot = 1 tâche atomique = 1 poste-clé d'équivalent grande entreprise.
// Descriptions : 1 phrase courte, action verbe en tête, français simple,
// pas de jargon ni d'acronyme non explicité (sauf KPIs métier connus du founder).

export type AgentStatusInCatalog = "active" | "roadmap";

export interface CatalogAgent {
  /** Nom canonique (clé pour matcher /api/agents). null = slot roadmap. */
  name: string | null;
  /** Slug affiché dans la card. */
  displayName: string;
  /** Poste équivalent grande entreprise (sous-titre mono). */
  shortLabel: string;
  /** 1 phrase courte décrivant la tâche atomique du bot. */
  description: string;
  status: AgentStatusInCatalog;
  /** Référence dans le plan (Annexe D · Sprint N, ou Pxx). */
  roadmapRef?: string;
}

export interface CatalogCategory {
  id: string;
  title: string;
  icon: LucideIcon;
  description: string;
  agents: CatalogAgent[];
}

// Ordre des services = pyramide d'exécution :
// Direction donne les directives → Finance / Sales / Marketing exécutent →
// CS, Produit, Tech, Veille, Compliance, Communication, Docs supportent →
// Meta-Ops orchestre tout au-dessus.
export const AGENT_CATEGORIES: CatalogCategory[] = [
  {
    id: "direction",
    title: "Direction & Stratégie",
    icon: Compass,
    description: "Donne les directives et priorise les autres bots.",
    agents: [
      {
        name: "StrategyBot",
        displayName: "StrategyBot",
        shortLabel: "VP Stratégie",
        description: "Synthèse hebdo des KPIs critiques + alerte si on dévie des objectifs.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "OKRTracker",
        displayName: "OKRTracker",
        shortLabel: "Chief of Staff",
        description: "Compare ce qui est réalisé vs les objectifs trimestriels de chaque pôle.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "BoardReporter",
        displayName: "BoardReporter",
        shortLabel: "Investor Relations",
        description: "Génère le board pack mensuel (MRR, burn, runway, NRR).",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "DecisionLogger",
        displayName: "DecisionLogger",
        shortLabel: "Knowledge Steward",
        description: "Capture chaque décision structurante et la range dans DECISIONS.md.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
    ],
  },
  {
    id: "finance",
    title: "Finance & Trésorerie",
    icon: DollarSign,
    description: "Comptabilité, budget, trésorerie, dunning.",
    agents: [
      {
        name: "FinanceBot",
        displayName: "FinanceBot",
        shortLabel: "Contrôleur financier",
        description: "Sync Stripe quotidienne, calcul MRR/ARR et relances impayés J+3/J+7/J+15.",
        status: "active",
      },
      {
        name: null,
        displayName: "InvoicePredictor",
        shortLabel: "Trésorier",
        description: "Forecast la trésorerie à 90 jours depuis les abonnements Stripe actifs.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 4+",
      },
      {
        name: null,
        displayName: "ExpenseAuditor",
        shortLabel: "Contrôleur de gestion",
        description: "Audite les notes de frais et flagge les anomalies (montant, vendor, doublon).",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 10",
      },
      {
        name: null,
        displayName: "TaxBot",
        shortLabel: "Fiscaliste",
        description: "Pré-prépare la TVA mensuelle CA3 et l'IS prévisionnel.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 10",
      },
      {
        name: null,
        displayName: "ReconcileBot",
        shortLabel: "Comptable",
        description: "Rapproche les factures Stripe avec les relevés bancaires Qonto.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 10",
      },
      {
        name: null,
        displayName: "BurnRateMonitor",
        shortLabel: "CFO adjoint",
        description: "Alerte Discord si le burn mensuel dépasse le seuil ou si runway < 9 mois.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 10",
      },
      {
        name: null,
        displayName: "VendorContractWatcher",
        shortLabel: "Achats",
        description: "Alerte avant la tacite reconduction des contrats fournisseurs.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 10",
      },
    ],
  },
  {
    id: "sales",
    title: "Sales / Commercial",
    icon: Handshake,
    description: "Ramener des clients (cible primaire + secondaire).",
    agents: [
      {
        name: "OutboundSender",
        displayName: "OutboundBot",
        shortLabel: "SDR Cold Email",
        description: "Drafte une séquence cold email 5 touches (D+0, D+3, D+7, D+14, D+30).",
        status: "roadmap",
        roadmapRef: "P13.A shadow · P13.B stage · live attend domaine",
      },
      {
        name: "LeadEnricher",
        displayName: "LeadEnricher",
        shortLabel: "Lead Intel",
        description: "Enrichit un lead BtoB depuis nom + domaine (email, titre, signaux ICP).",
        status: "active",
      },
      {
        name: "ProspectMiner",
        displayName: "ProspectMiner",
        shortLabel: "Sourcer",
        description: "Trouve des nouveaux leads ICP via sources publiques (annonces, levées).",
        status: "active",
      },
      {
        name: "IntentSignalsBot",
        displayName: "IntentSignalsBot",
        shortLabel: "Lead Gen Lead",
        description: "Capte les signaux d'achat (breaches publics, embauches CISO, levées).",
        status: "active",
      },
      {
        name: "MeetingBooker",
        displayName: "MeetingBooker",
        shortLabel: "Sales Ops",
        description: "Confirme les RDV démo et envoie les rappels J-1 et H-1.",
        status: "active",
      },
      {
        name: "DemoFollowupBot",
        displayName: "DemoFollowupBot",
        shortLabel: "Account Executive",
        description: "Drafte le mail récap post-démo avec les next steps personnalisés.",
        status: "active",
      },
      {
        name: "ProposalBot",
        displayName: "ProposalBot",
        shortLabel: "Sales Engineer",
        description: "Génère un devis personnalisé depuis le template + variables compte.",
        status: "active",
      },
      {
        name: "ContractGenerator",
        displayName: "ContractGenerator",
        shortLabel: "Sales Legal",
        description: "Génère CGV / MSA depuis template à partir des variables client.",
        status: "active",
      },
      {
        name: "DealRiskScorer",
        displayName: "DealRiskScorer",
        shortLabel: "Sales Manager",
        description: "Score les deals dans le pipe et flagge les stalled > 14 jours.",
        status: "active",
      },
    ],
  },
  {
    id: "marketing",
    title: "Marketing & Growth",
    icon: TrendingUp,
    description: "Top funnel : SEO, ads, social, contenu, growth.",
    agents: [
      {
        name: "SEOBot",
        displayName: "SEOBot",
        shortLabel: "SEO Strategist",
        description: "Drafte des briefs blog SEO structurés depuis un mot-clé + la KB Argos.",
        status: "active",
      },
      {
        name: "ContentBot",
        displayName: "ContentBot",
        shortLabel: "Content Manager",
        description: "Publie 2 à 5 posts par jour sur LinkedIn et Mastodon.",
        status: "active",
      },
      {
        name: "AdBot",
        displayName: "AdBot",
        shortLabel: "Paid Acquisition",
        description: "Pilote les campagnes Google / Meta / LinkedIn Ads (shadow → live).",
        status: "active",
      },
      {
        name: "TrendSpotter",
        displayName: "TrendSpotter",
        shortLabel: "Trend Analyst",
        description: "Détecte les tendances cyber qui alimentent SEOBot et ContentBot.",
        status: "active",
      },
      {
        name: "NewsletterBot",
        displayName: "NewsletterBot",
        shortLabel: "Email Marketing",
        description: "Assemble la newsletter mensuelle depuis le blog + l'actu cyber.",
        status: "active",
      },
      {
        name: "SocialAnalytics",
        displayName: "SocialAnalytics",
        shortLabel: "Community Analytics",
        description: "Reporting hebdo de l'engagement par canal social.",
        status: "active",
      },
      {
        name: "BacklinkOutreach",
        displayName: "BacklinkOutreach",
        shortLabel: "SEO Off-page",
        description: "Prospecte les sites cyber pour proposer des échanges de liens.",
        status: "active",
      },
      {
        name: "KeywordRadar",
        displayName: "KeywordRadar",
        shortLabel: "SEO Specialist",
        description: "Surveille les positions SERP et identifie les opportunités longue traîne.",
        status: "active",
      },
      {
        name: "LandingOptimizer",
        displayName: "LandingOptimizer",
        shortLabel: "CRO Specialist",
        description: "Analyse les heatmaps et propose des variantes A/B pour les pages clés.",
        status: "active",
      },
      {
        name: "WebinarPromoter",
        displayName: "WebinarPromoter",
        shortLabel: "Field Marketing",
        description: "Promote un webinar (teaser LinkedIn, replay edit, mail de relance).",
        status: "active",
      },
      {
        name: "TestimonialHunter",
        displayName: "TestimonialHunter",
        shortLabel: "Customer Marketing",
        description: "Collecte les verbatims clients après chaque NPS positif.",
        status: "active",
      },
      {
        name: "CaseStudyDrafter",
        displayName: "CaseStudyDrafter",
        shortLabel: "Content Senior",
        description: "Drafte un case study à partir d'un compte référence accepté.",
        status: "active",
      },
    ],
  },
  {
    id: "customer-success",
    title: "Customer Success & Support",
    icon: LifeBuoy,
    description: "Onboarding, rétention, support technique.",
    agents: [
      {
        name: "SupportBot",
        displayName: "SupportBot",
        shortLabel: "Support Tier 1",
        description: "Répond aux questions techniques Tier 1 via RAG sur la KB Argos.",
        status: "active",
      },
      {
        name: "ReviewBot",
        displayName: "ReviewBot",
        shortLabel: "Customer Advocacy",
        description: "Sollicite les avis G2 / Capterra / Google des promoteurs (NPS ≥ 9) J+30 post-onboarding.",
        status: "active",
      },
      {
        name: "ChurnPredictor",
        displayName: "ChurnPredictor",
        shortLabel: "Retention Manager",
        description: "Détecte les signaux pré-churn (inactivité, NPS détracteur, tickets, sous-utilisation).",
        status: "active",
      },
      {
        name: "OnboardingBot",
        displayName: "OnboardingBot",
        shortLabel: "CSM Onboarding",
        description: "Drafte la checklist onboarding J+0, J+7 et J+30 de chaque nouveau client (humain envoie).",
        status: "active",
      },
      {
        name: "HealthScoreBot",
        displayName: "HealthScoreBot",
        shortLabel: "CS Ops",
        description: "Calcule un score santé 0-100 par compte (usage + tickets + NPS + inactivité).",
        status: "active",
      },
      {
        name: "KBUpdater",
        displayName: "KBUpdater",
        shortLabel: "Knowledge Manager",
        description: "Détecte les questions répétées en support et drafte les squelettes d'articles KB.",
        status: "active",
      },
      {
        name: "NPSCollector",
        displayName: "NPSCollector",
        shortLabel: "Voice of Customer",
        description: "Drafte les demandes NPS post-onboarding J+14 et post-renew J+21 (humain envoie).",
        status: "active",
      },
      {
        name: "UpsellSpotter",
        displayName: "UpsellSpotter",
        shortLabel: "Account Growth",
        description: "Repère les comptes prêts à l'upsell quand leur usage dépasse 80% du quota plan.",
        status: "active",
      },
      {
        name: "EscalationRouter",
        displayName: "EscalationRouter",
        shortLabel: "Support Lead",
        description: "Trie les tickets P0 / P1 / P2 selon SLA réponse et flag les breach.",
        status: "active",
      },
    ],
  },
  {
    id: "produit",
    title: "Produit & R&D",
    icon: Package,
    description: "Roadmap, release notes, feedback, discovery.",
    agents: [
      {
        name: "ChangelogBot",
        displayName: "ChangelogBot",
        shortLabel: "Product Marketing",
        description: "Génère le changelog Markdown depuis git log entre 2 refs (conventional commits).",
        status: "active",
      },
      {
        name: "ReleaseNotesBot",
        displayName: "ReleaseNotesBot",
        shortLabel: "Product Manager",
        description: "Drafte des release notes user-friendly depuis spec.yaml (humain peaufine et publie).",
        status: "active",
      },
      {
        name: "FeedbackAggregator",
        displayName: "FeedbackAggregator",
        shortLabel: "Product Discovery",
        description: "Agrège les demandes clients (email, support, Discord) par thème dans un digest.",
        status: "active",
      },
      {
        name: "RoadmapPublisher",
        displayName: "RoadmapPublisher",
        shortLabel: "Head of Product",
        description: "Génère la roadmap publique depuis l'Annexe D interne (codes sprint retirés).",
        status: "active",
      },
      {
        name: "BugTriageBot",
        displayName: "BugTriageBot",
        shortLabel: "QA Lead",
        description: "Classifie les issues GitHub par sévérité (P0/P1/P2) et suggère un label (read-only).",
        status: "active",
      },
    ],
  },
  {
    id: "tech-it",
    title: "Tech / SRE / Sécurité IT",
    icon: Shield,
    description: "Uptime, secrets, dépendances, backups.",
    agents: [
      {
        name: "UptimeMonitor",
        displayName: "UptimeMonitor",
        shortLabel: "SRE",
        description: "Ping les endpoints publics et alerte Discord si down plus de 60 secondes.",
        status: "active",
      },
      {
        name: "DependencyAuditor",
        displayName: "DependencyAuditor",
        shortLabel: "AppSec",
        description: "Scan les dépendances (uv) et alerte si une CVE HIGH/CRITICAL sort (OSV.dev).",
        status: "active",
      },
      {
        name: "LogAnomalyDetector",
        displayName: "LogAnomalyDetector",
        shortLabel: "SRE Observability",
        description: "Repère les pics d'erreurs dans les logs serveur.",
        status: "active",
      },
      {
        name: "BackupVerifier",
        displayName: "BackupVerifier",
        shortLabel: "DevOps",
        description: "Vérifie chaque jour qu'un backup Postgres récent (<24h) existe dans data/backups/.",
        status: "active",
      },
      {
        name: "SSLExpirer",
        displayName: "SSLExpirer",
        shortLabel: "IT Security",
        description: "Alerte si un certificat SSL expire dans moins de 30 jours.",
        status: "active",
      },
      {
        name: "DNSGuard",
        displayName: "DNSGuard",
        shortLabel: "IT Network",
        description: "Surveille les changements DNS suspects sur omnividens.fr.",
        status: "active",
      },
      {
        name: "SecretRotator",
        displayName: "SecretRotator",
        shortLabel: "Security Engineer",
        description: "Alerte sur les secrets de plus de 90 jours (Stripe, Zimbra, webhooks).",
        status: "active",
      },
      {
        name: "CIFlakeTracker",
        displayName: "CIFlakeTracker",
        shortLabel: "DevOps Lead",
        description: "Repère les tests CI flaky récurrents et ouvre une issue automatique.",
        status: "active",
      },
    ],
  },
  {
    id: "veille",
    title: "Veille & Threat Intelligence",
    icon: Eye,
    description: "Concurrence, breaches, régulation, CVE.",
    agents: [
      {
        name: "CompetitorWatcher",
        displayName: "CompetitorWatcher",
        shortLabel: "Competitive Intel",
        description: "Scrape chaque semaine les pages features et pricing des concurrents.",
        status: "active",
      },
      {
        name: "BreachWatcher",
        displayName: "BreachWatcher",
        shortLabel: "Threat Intel",
        description: "Monitore les breaches publics (HIBP, CERT-FR) pour détecter des leads chauds.",
        status: "active",
      },
      {
        name: "RegulatoryWatcher",
        displayName: "RegulatoryWatcher",
        shortLabel: "Compliance Watch",
        description: "Suit les évolutions RGPD, AI Act, NIS2 et DORA et alerte si impact produit.",
        status: "active",
      },
      {
        name: "CVEMonitor",
        displayName: "CVEMonitor",
        shortLabel: "Threat Intel",
        description: "Suit les CVE critiques qui touchent la stack déclarée par les clients.",
        status: "active",
      },
      {
        name: "DarkWebMonitor",
        displayName: "DarkWebMonitor",
        shortLabel: "Threat Intel Senior",
        description: "Cherche les mentions des domaines clients sur le dark web (sell point ICP, MVP HIBP).",
        status: "active",
      },
      {
        name: "BountyRadar",
        displayName: "BountyRadar",
        shortLabel: "Bug Bounty Manager",
        description: "Repère les programmes bug bounty pertinents pour positionner Argos.",
        status: "active",
      },
    ],
  },
  {
    id: "compliance",
    title: "Juridique & Compliance",
    icon: Scale,
    description: "RGPD, AI Act, Bloctel, contrats clients.",
    agents: [
      {
        name: "RGPDAuditor",
        displayName: "RGPDAuditor",
        shortLabel: "DPO",
        description: "Vérifie le registre des traitements et alerte sur les nouveaux non documentés.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "AIActComplianceBot",
        displayName: "AIActComplianceBot",
        shortLabel: "AI Compliance Officer",
        description: "Vérifie chaque agent IA contre sa catégorie de risque AI Act.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "BloctelGuard",
        displayName: "BloctelGuard",
        shortLabel: "Compliance Bloctel",
        description: "Check chaque lead outbound BtoC contre la liste d'opposition Bloctel.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "ContractDeadlineBot",
        displayName: "ContractDeadlineBot",
        shortLabel: "Legal Ops",
        description: "Alerte 60 jours avant chaque renouvellement de contrat client.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
      {
        name: "IncidentLogger",
        displayName: "IncidentLogger",
        shortLabel: "RSSI",
        description: "Log chaque incident sécurité interne et drafte le post-mortem template.",
        status: "active",
        roadmapRef: "P22.E livré 2026-05-23",
      },
    ],
  },
  {
    id: "communication",
    title: "Communication",
    icon: Megaphone,
    description: "RP, presse, comms de crise, brand consistency.",
    agents: [
      {
        name: "EmailBot",
        displayName: "EmailBot",
        shortLabel: "Standardiste Inbox",
        description: "Pull IMAP toutes les 15 min, ingestion CRM et notif Discord.",
        status: "active",
      },
      {
        name: "ReplyBot",
        displayName: "ReplyBot",
        shortLabel: "Community Manager",
        description: "Drafte les réponses aux mentions LinkedIn / Mastodon (humain-validé).",
        status: "active",
      },
      {
        name: "PressMonitor",
        displayName: "PressMonitor",
        shortLabel: "Veille presse",
        description: "Alerte sur les mentions Argos / Omnividens / SecHunter sur le web public.",
        status: "active",
      },
      {
        name: "PressReleaseDrafter",
        displayName: "PressReleaseDrafter",
        shortLabel: "RP Manager",
        description: "Drafte un communiqué de presse pour chaque annonce produit ou finance.",
        status: "active",
      },
      {
        name: "MediaListBuilder",
        displayName: "MediaListBuilder",
        shortLabel: "Attaché de presse",
        description: "Maintient la base de journalistes et médias cyber pertinents.",
        status: "active",
      },
      {
        name: "CrisisCommBot",
        displayName: "CrisisCommBot",
        shortLabel: "Comm de crise",
        description: "Drafte une réponse type prête à dégainer en cas d'incident public.",
        status: "active",
      },
      {
        name: "SpokespersonPrep",
        displayName: "SpokespersonPrep",
        shortLabel: "Media Training",
        description: "Prépare un brief Q&A pour chaque interview du fondateur.",
        status: "active",
      },
      {
        name: "BrandGuardBot",
        displayName: "BrandGuardBot",
        shortLabel: "Brand Manager",
        description: "Check la cohérence du ton, tagline et signature sur tous les drafts sortants.",
        status: "active",
      },
    ],
  },
  {
    id: "documentation",
    title: "Documentation & Knowledge interne",
    icon: BookOpen,
    description: "Maintenance des docs techniques internes.",
    agents: [
      {
        name: null,
        displayName: "DocLinter",
        shortLabel: "Technical Writer",
        description: "Check les liens morts et la cohérence des fichiers dans docs/.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 13",
      },
      {
        name: null,
        displayName: "DiagramGenerator",
        shortLabel: "Tech Doc",
        description: "Génère des diagrammes Mermaid à partir des specs ou du code.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 13",
      },
      {
        name: null,
        displayName: "ADRWriter",
        shortLabel: "Tech Lead",
        description: "Drafte un ADR (Architecture Decision Record) depuis une discussion ou une PR.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 13",
      },
    ],
  },
  {
    id: "meta-ops",
    title: "Meta-Ops",
    icon: Cpu,
    description: "Bots qui gèrent les bots (orchestration, santé, mémoire).",
    agents: [
      {
        name: "DigestBuilder",
        displayName: "DigestBuilder",
        shortLabel: "Reporting Officer",
        description: "Récap quotidien Discord 8h Paris (KPIs J-1, escalades, breakers).",
        status: "active",
      },
      {
        name: null,
        displayName: "ClaudeJudge",
        shortLabel: "QA des bots",
        description: "Audite chaque output (factual / tone / legal) avant validation humaine.",
        status: "roadmap",
        roadmapRef: "P14 · skill livré",
      },
      {
        name: "OrchestratorBot",
        displayName: "OrchestratorBot",
        shortLabel: "Chef de fleet",
        description: "Décide quels bots doivent tourner maintenant (dry-run ou live, garde-fou parallélisme).",
        status: "active",
      },
      {
        name: "BotHealthBot",
        displayName: "BotHealthBot",
        shortLabel: "SRE de la flotte",
        description: "Surveille uptime + erreurs récentes des bots actifs, alerte Discord si stale ou échec.",
        status: "active",
      },
      {
        name: "BotPerfAnalyzer",
        displayName: "BotPerfAnalyzer",
        shortLabel: "Performance Engineer",
        description: "Mesure P50/P95 et taux d'erreur 7j vs baseline, alerte si dérive >= 1.5x.",
        status: "active",
      },
      {
        name: null,
        displayName: "CapabilityRouter",
        shortLabel: "Capability Manager",
        description: "Route chaque demande vers le bot qualifié (Capabilities P21).",
        status: "roadmap",
        roadmapRef: "P21 · spec en cours",
      },
      {
        name: null,
        displayName: "MemoryCurator",
        shortLabel: "Memory Steward",
        description: "Nettoie et déduplique la mémoire partagée Argos Memory (P20).",
        status: "roadmap",
        roadmapRef: "P20 · spec en cours",
      },
      {
        name: "ErrorTriageBot",
        displayName: "ErrorTriageBot",
        shortLabel: "Bot Ops",
        description: "Regroupe les erreurs runtime 24h par signature, alerte si >= 3 occurrences.",
        status: "active",
      },
      {
        name: "KillSwitchOperator",
        displayName: "KillSwitchOperator",
        shortLabel: "Safety Officer",
        description: "Alerte 1x/jour pour chaque breaker tripped > 4h, inclut guide reset.",
        status: "active",
      },
      {
        name: "BotConfigManager",
        displayName: "BotConfigManager",
        shortLabel: "Config Ops",
        description: "Diff agent_config DB vs data/agent_config/baseline.yaml, alerte sur drifts.",
        status: "active",
      },
    ],
  },
];

/** Liste plate des agents actifs avec leur catégorie (pour matcher /api/agents). */
export function flattenActiveAgents(): Array<{ name: string; categoryId: string }> {
  const out: Array<{ name: string; categoryId: string }> = [];
  for (const cat of AGENT_CATEGORIES) {
    for (const agent of cat.agents) {
      if (agent.status === "active" && agent.name) {
        out.push({ name: agent.name, categoryId: cat.id });
      }
    }
  }
  return out;
}

/** Count agents actifs vs roadmap par catégorie. */
export function categoryCounts(categoryId: string): { active: number; roadmap: number } {
  const cat = AGENT_CATEGORIES.find((c) => c.id === categoryId);
  if (!cat) return { active: 0, roadmap: 0 };
  return {
    active: cat.agents.filter((a) => a.status === "active").length,
    roadmap: cat.agents.filter((a) => a.status === "roadmap").length,
  };
}

/** Total cumulé sur tous les services. */
export function totalCounts(): { active: number; roadmap: number; total: number } {
  let active = 0;
  let roadmap = 0;
  for (const cat of AGENT_CATEGORIES) {
    for (const a of cat.agents) {
      if (a.status === "active") active += 1;
      else roadmap += 1;
    }
  }
  return { active, roadmap, total: active + roadmap };
}
