// Glossaire central des acronymes / concepts Argos Ops.
// Consommé par <Tooltip term="..."/> pour expliquer chaque libellé technique
// au fondateur non-tech. UN seul endroit à mettre à jour pour toute l'UI.

export interface GlossaryEntry {
  /** Libellé court affiché dans le tooltip (1-3 mots). */
  short: string;
  /** Explication longue (1-2 phrases, ton naturel, pas de jargon). */
  long: string;
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  MRR: {
    short: "Monthly Recurring Revenue",
    long: "Revenu mensuel récurrent — somme des abonnements actifs ramenée au mois. C'est la métrique cœur de tout SaaS.",
  },
  ARR: {
    short: "Annual Recurring Revenue",
    long: "Revenu annuel récurrent — MRR × 12. Ce que rapporterait la base actuelle sur un an si rien ne bougeait.",
  },
  NRR: {
    short: "Net Revenue Retention",
    long: "Net Revenue Retention — combien il reste de revenu sur la base existante 12 mois plus tard (churn − expansions). Objectif > 100 %.",
  },
  P95: {
    short: "95e percentile",
    long: "Durée sous laquelle se finissent 95 % des runs. Mieux que la moyenne pour spotter les ralentissements anormaux.",
  },
  P50: {
    short: "Médiane",
    long: "Durée sous laquelle se finissent 50 % des runs (la médiane). Représente le run \"typique\".",
  },
  Tier1: {
    short: "Tier 1 — auto-validé",
    long: "Niveau de confiance d'un draft : Tier 1 = score juge ≥ seuil, peut être envoyé sans relecture. Tier 2-4 = escalade humaine progressive.",
  },
  "Tier 1": {
    short: "Tier 1 — auto-validé",
    long: "Niveau de confiance d'un draft : Tier 1 = score juge ≥ seuil, peut être envoyé sans relecture. Tier 2-4 = escalade humaine progressive.",
  },
  RAG: {
    short: "Retrieval-Augmented Generation",
    long: "Avant de répondre, l'agent va chercher dans la KB Argos les 5 morceaux les plus pertinents, puis répond en citant. Évite les hallucinations.",
  },
  KB: {
    short: "Knowledge Base",
    long: "Base de connaissances interne d'Argos — pricing, FAQ, doc produit, témoignages. Indexée vectoriellement (pgvector) pour le RAG.",
  },
  BANT: {
    short: "Budget / Authority / Need / Timing",
    long: "Score de qualification BtoB classique (0-100). Combien le lead a de budget, s'il décide, s'il a un besoin réel, et s'il achète bientôt.",
  },
  ICP: {
    short: "Ideal Customer Profile",
    long: "Profil-cible Argos. Marc (RSSI mid-market), Sarah (DAF scale-up), Thomas (CTO PME tech). Voir docs/ICP.md.",
  },
  "AI Act": {
    short: "Règlement IA UE",
    long: "Règlement européen sur l'IA (2024). Impose disclosure quand un contenu est généré par IA et droit à demander une réponse humaine.",
  },
  RGPD: {
    short: "Règlement européen vie privée",
    long: "RGPD/GDPR. Toute donnée personnelle (email, nom) doit avoir une base légale, un opt-out, et une durée de rétention.",
  },
  Bloctel: {
    short: "Opposition démarchage FR",
    long: "Registre français d'opposition au démarchage téléphonique. Tout numéro à appeler doit d'abord être vérifié (sinon amende).",
  },
  CTR: {
    short: "Click-Through Rate",
    long: "Taux de clic — clics / impressions. Sur LinkedIn organique, > 2 % est bon. Sur Google Ads cyber B2B, > 4 % est bon.",
  },
  CPC: {
    short: "Cost Per Click",
    long: "Coût par clic moyen sur une campagne Ads. Sur Google search cyber B2B FR, attendu 2-6 € selon kw.",
  },
  CPA: {
    short: "Cost Per Acquisition",
    long: "Coût d'acquisition d'un lead qualifié. Objectif Argos : < 80 € sur Google Ads, < 150 € sur LinkedIn Ads.",
  },
  SDR: {
    short: "Sales Development Rep",
    long: "Le rôle qui prospecte à froid pour générer des RDV. Chez Argos, c'est OutboundBot (séquence 5 touches D+0/D+3/D+7/D+14/D+30).",
  },
  Breaker: {
    short: "Disjoncteur",
    long: "Comme dans un tableau électrique : si quelque chose d'anormal arrive (chute MRR, burst d'erreurs), un breaker \"saute\" et coupe l'agent pour éviter des dégâts.",
  },
  Tripped: {
    short: "Breaker déclenché",
    long: "Un breaker tripped = l'agent est coupé jusqu'à reset manuel. Cause racine à corriger AVANT le reset.",
  },
  Dunning: {
    short: "Relances impayés",
    long: "Cycle de relance des factures impayées (J+3 amical, J+7 ferme, J+15 final). Chez Argos via FinanceBot + zimbra-ops.",
  },
  NPS: {
    short: "Net Promoter Score",
    long: "« Recommanderiez-vous Argos ? » noté 0-10. Promoteurs (9-10) − Détracteurs (0-6) = NPS. Argos vise > 30.",
  },
  Churn: {
    short: "Désabonnement",
    long: "Taux de clients qui annulent leur abonnement. Le churn cumulé sur 12 mois est le poison silencieux du SaaS.",
  },
  Shadow: {
    short: "Mode dry-run",
    long: "L'agent fait tout — analyse, draft, recommandations — SAUF la dernière étape (envoi, publication). Garde-fou tant qu'on n'a pas confiance.",
  },
  Tagline: {
    short: "Tagline Argos",
    long: "« Argos — on scanne, vous corrigez. » Doit apparaître dans toute communication outbound (cohérence brand).",
  },
  Slug: {
    short: "Identifiant court",
    long: "Version url-safe d'un titre (ex : \"refonte-ui-dashboard\"). Utilisé comme clé de fichier et dans les URLs.",
  },
  KPI: {
    short: "Key Performance Indicator",
    long: "Indicateur métier suivi en temps réel. Chez Argos : MRR, leads 24h, tickets ouverts, breakers tripped.",
  },
  Watcher: {
    short: "Agent surveillance silence-si-vert",
    long: "Agent qui audite quelque chose en arrière-plan et N'ALERTE QUE si problème (anti-spam). Ex : UptimeMonitor, SecretRotator.",
  },
  Cron: {
    short: "Planification temporelle",
    long: "Format Unix \"* * * * *\" qui dit \"toutes les 15min\" ou \"chaque jour à 8h\". Chez Argos via Task Scheduler Windows.",
  },
  IMAP: {
    short: "Protocole lecture email",
    long: "Protocole pour lire des emails depuis un serveur (boîte de réception). Argos lit ovh Zimbra via IMAP ssl0.ovh.net:993.",
  },
  SMTP: {
    short: "Protocole envoi email",
    long: "Protocole pour envoyer des emails. Argos envoie via OVH Zimbra SMTP ssl0.ovh.net:465.",
  },
  CVE: {
    short: "Vulnérabilité connue",
    long: "Common Vulnerabilities and Exposures — base mondiale des failles de sécurité publiées. Argos monitore les CVE des stacks clients via osv.dev.",
  },
  SERP: {
    short: "Page résultats Google",
    long: "Search Engine Results Page — la page de résultats Google. Argos suit ses positions sur les keywords cyber stratégiques.",
  },
  Runway: {
    short: "Mois de trésorerie restants",
    long: "Trésorerie ÷ burn mensuel. Combien de mois Argos peut tenir sans revenus. Alerte si runway < 9 mois.",
  },
  Burn: {
    short: "Burn rate",
    long: "Consommation de cash mensuelle nette (sorties − entrées). Tant qu'on n'est pas rentable, le burn dévore le runway.",
  },
};

export function lookupTerm(term: string): GlossaryEntry | null {
  return GLOSSARY[term] ?? null;
}
