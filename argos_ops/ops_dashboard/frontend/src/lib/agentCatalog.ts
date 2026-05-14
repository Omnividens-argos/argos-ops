import {
  BarChart3,
  DollarSign,
  Edit3,
  Eye,
  Inbox,
  Send,
  Shield,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// Catalogue des agents Argos Ops — groupé par catégorie pour la vue Agents.
// Source de vérité catégorisation : décision 2026-05-12 (option a).
// Les nouveaux agents proposés sont décrits dans ARGOS_OPS_PLAN.md (annexe D).

export type AgentStatusInCatalog = "active" | "roadmap";

export interface CatalogAgent {
  /** Nom canonique (clé pour matcher /api/agents). null = slot roadmap. */
  name: string | null;
  /** Slug affiché si pas d'API match (cas roadmap). */
  displayName: string;
  shortLabel: string;
  description: string;
  status: AgentStatusInCatalog;
  /** Référence dans le plan (P14, P9, etc.). */
  roadmapRef?: string;
  /**
   * Peut être déclenché manuellement via "Run now". Faux pour les agents
   * interactifs (SupportBot, SEOBot) qui s'invoquent via slash command.
   */
  runnable?: boolean;
  /**
   * Demande une confirmation modale avant le run manuel (agents qui envoient
   * du sortant : FinanceBot dunning Stripe, futurs OutboundBot/AdBot).
   */
  outboundConfirmation?: boolean;
  /** Sprint pressenti (affiché dans la page Roadmap). */
  sprint?: string;
  /** Dépendances (autres parties / agents) — affiché dans la page Roadmap. */
  dependencies?: string[];
}

export interface CatalogCategory {
  id: string;
  title: string;
  icon: LucideIcon;
  description: string;
  agents: CatalogAgent[];
}

// Ordre top-down = entonnoir d'acquisition + admin en bas (cf. recommandation
// ui-ux-pro-max § 3, 2026-05-12).
export const AGENT_CATEGORIES: CatalogCategory[] = [
  {
    id: "monitoring",
    title: "Monitoring & Intel",
    icon: BarChart3,
    description: "Observabilité système + veille externe.",
    agents: [
      {
        name: "DigestBuilder",
        displayName: "DigestBuilder",
        shortLabel: "Digest",
        description:
          "Récap quotidien Discord 8h Paris (KPIs J-1 + escalades + breakers).",
        status: "active",
        runnable: true,
      },
      {
        name: null,
        displayName: "CompetitorWatcher",
        shortLabel: "Concurrence",
        description:
          "Scrape hebdo features/pricing des concurrents — détecte changements.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 3+",
        sprint: "Sprint 3+",
        dependencies: ["aucune (HTTP fetch + structured extract)"],
      },
      {
        name: null,
        displayName: "PressMonitor",
        shortLabel: "Mentions presse",
        description:
          "Alerte mentions Argos / Omnividens / SecHunter sur le web public.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 3+",
        sprint: "Sprint 3+",
        dependencies: ["P11 (Reddit connecteur)"],
      },
      {
        name: null,
        displayName: "TrendSpotter",
        shortLabel: "Tendances",
        description:
          "Détecte tendances cybersec qui peuvent alimenter SEOBot/ContentBot.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 2+",
        sprint: "Sprint 2+",
        dependencies: ["P10 (SEOBot)", "P11 (Reddit connecteur)"],
      },
    ],
  },
  {
    id: "inbound",
    title: "Inbound & Support",
    icon: Inbox,
    description: "Captation des emails entrants + support Tier 1 RAG sur KB.",
    agents: [
      {
        name: "EmailBot",
        displayName: "EmailBot",
        shortLabel: "Inbox",
        description: "Pull IMAP toutes les 15 min, ingestion CRM, notif Discord.",
        status: "active",
        runnable: true,
      },
      {
        name: "SupportBot",
        displayName: "SupportBot",
        shortLabel: "Tier 1 RAG",
        description:
          "Répond aux questions techniques Tier 1 via RAG sur la KB Argos.",
        status: "active",
        runnable: false,
      },
    ],
  },
  {
    id: "outbound",
    title: "Comms sortante",
    icon: Send,
    description: "Réponses publiques + sollicitation avis + cold email.",
    agents: [
      {
        name: null,
        displayName: "OutboundBot",
        shortLabel: "Cold email",
        description: "Séquence 5-touch BtoB (P13, domaine secondaire).",
        status: "roadmap",
        roadmapRef: "P13 · Sprint 3",
        sprint: "Sprint 3",
        dependencies: ["P5 (EmailBot)", "P6 (kb-rag)", "domaine secondaire"],
      },
      {
        name: null,
        displayName: "ReplyBot",
        shortLabel: "Mentions sociales",
        description:
          "Réponse aux mentions LinkedIn / Reddit / Mastodon — humain-validé.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 3+",
        sprint: "Sprint 3+",
        dependencies: ["P11 (connecteurs sociaux)", "P14 (ClaudeJudge)"],
      },
      {
        name: null,
        displayName: "ReviewBot",
        shortLabel: "Avis clients",
        description:
          "Sollicite les vrais avis G2/Capterra/Google post-onboarding J+30.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 4+",
        sprint: "Sprint 4+",
        dependencies: ["P5 (EmailBot)", "P7 (FinanceBot)"],
      },
    ],
  },
  {
    id: "content",
    title: "Contenu & SEO",
    icon: Edit3,
    description: "Production éditoriale top funnel.",
    agents: [
      {
        name: "SEOBot",
        displayName: "SEOBot (briefs)",
        shortLabel: "Briefs SEO",
        description:
          "Briefs blog markdown depuis la KB — humain-in-the-loop (P10-MVP).",
        status: "active",
        runnable: false,
      },
      {
        name: null,
        displayName: "ContentBot",
        shortLabel: "Publication",
        description: "2-5 posts/jour LinkedIn / Mastodon / Reddit (P9).",
        status: "roadmap",
        roadmapRef: "P9 · Sprint 2",
        sprint: "Sprint 2",
        dependencies: ["P6 (kb-rag)", "P10 (SEOBot)", "P11 (connecteurs sociaux)"],
      },
    ],
  },
  {
    id: "acquisition",
    title: "Acquisition payante",
    icon: Eye,
    description: "Pilotage des campagnes ads + enrichissement leads.",
    agents: [
      {
        name: null,
        displayName: "AdBot",
        shortLabel: "Google/Meta/LinkedIn Ads",
        description: "Pilotage shadow mode → live à budget > 0 (P12).",
        status: "roadmap",
        roadmapRef: "P12 · Sprint 3",
        sprint: "Sprint 3",
        dependencies: [
          "breaker ad_spend_runaway",
          "Google Ads / Meta / LinkedIn Ads APIs",
        ],
      },
      {
        name: null,
        displayName: "LeadEnricher",
        shortLabel: "Lead intel",
        description: "Enrichit les leads inbound (LinkedIn intel auto).",
        status: "roadmap",
        roadmapRef: "P18 · skill réutilisé",
        sprint: "P18",
        dependencies: ["P5 (EmailBot)"],
      },
    ],
  },
  {
    id: "finance",
    title: "Finance & Admin",
    icon: DollarSign,
    description: "Stripe sync + dunning + forecast + signaux de churn.",
    agents: [
      {
        name: "FinanceBot",
        displayName: "FinanceBot",
        shortLabel: "Stripe sync",
        description:
          "Sync quotidienne Stripe (MRR + ARR + dunning J+3/J+7/J+15).",
        status: "active",
        runnable: true,
        outboundConfirmation: true,
      },
      {
        name: null,
        displayName: "ChurnPredictor",
        shortLabel: "Signaux churn",
        description:
          "Analyse signaux pré-churn depuis Stripe + interactions CRM.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 4+",
        sprint: "Sprint 4+",
        dependencies: ["P7 (FinanceBot)", "P5 (EmailBot)", "P6 (SupportBot)"],
      },
      {
        name: null,
        displayName: "InvoicePredictor",
        shortLabel: "Cash flow 90j",
        description: "Forecast cash flow basé sur les subs Stripe actives.",
        status: "roadmap",
        roadmapRef: "Annexe D · Sprint 4+",
        sprint: "Sprint 4+",
        dependencies: ["P7 (FinanceBot)"],
      },
    ],
  },
  {
    id: "supervision",
    title: "Supervision IA",
    icon: Shield,
    description: "Agent-juge — valide les décisions des autres agents.",
    agents: [
      {
        name: null,
        displayName: "ClaudeJudge",
        shortLabel: "Agent-juge",
        description:
          "Supervise les autres agents (Tier 1) — flag les drafts à risque humain-validé.",
        status: "roadmap",
        roadmapRef: "P14 · Sprint 4",
        sprint: "Sprint 4",
        dependencies: ["tous les agents producteurs", "breaker judge_disagreement"],
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

/** Cherche un agent dans le catalogue par son ``displayName`` (matche les
 * slots roadmap) ou son ``name`` canonique (matche les agents actifs).
 * Retourne aussi la catégorie pour le breadcrumb / le badge. */
export function findAgentInCatalog(
  key: string,
): { agent: CatalogAgent; category: CatalogCategory } | null {
  for (const category of AGENT_CATEGORIES) {
    for (const agent of category.agents) {
      if (agent.name === key || agent.displayName === key) {
        return { agent, category };
      }
    }
  }
  return null;
}
