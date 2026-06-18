// Définitions des 8 pôles (archi v2) — miroir statique de data/poles/<pole>/pole.yaml.
//
// En S0, le cockpit n'a pas encore d'endpoint backend qui sert les pole.yaml :
// cette liste est la source d'affichage du shell. Une session ultérieure pourra
// la remplacer par un fetch /api/poles. Garder l'ordre = ordre des onglets.

export type FrontTool = "memory_table" | "alert_card" | "validation_queue";

export interface PoleDef {
  id: string;
  num: number;
  name: string;
  description: string;
  /** Nom de l'agent du pôle, ou null pour le SRE (aucun agent — cron pur). */
  agent: string | null;
  frontTools: FrontTool[];
}

export const POLES: PoleDef[] = [
  {
    id: "veille",
    num: 1,
    name: "Veille",
    description:
      "Veille marché, tech, concurrents et menaces. Alimente le contenu et la qualification.",
    agent: "VeilleAgent",
    frontTools: ["memory_table", "alert_card"],
  },
  {
    id: "marketing",
    num: 2,
    name: "Marketing & Comm",
    description: "Acquisition organique : contenu social/blog, RP, calendrier éditorial.",
    agent: "MarketingAgent",
    frontTools: ["memory_table", "validation_queue", "alert_card"],
  },
  {
    id: "pub",
    num: 3,
    name: "Pub",
    description: "Acquisition payante : créas, optimisation et garde-fous budget (shadow).",
    agent: "PubAgent",
    frontTools: ["memory_table", "validation_queue", "alert_card"],
  },
  {
    id: "vente",
    num: 4,
    name: "Vente & RC",
    description: "Conversion et relation client : leads, outbound, support, CRM, RDV.",
    agent: "VenteAgent",
    frontTools: ["memory_table", "validation_queue", "alert_card"],
  },
  {
    id: "finance",
    num: 5,
    name: "Finance & Conformité",
    description: "Stripe/MRR, relances, prévisions cash, TVA et conformité RGPD/AI Act.",
    agent: "FinanceAgent",
    frontTools: ["memory_table", "alert_card"],
  },
  {
    id: "direction",
    num: 6,
    name: "Direction",
    description: "Pilotage flotte : OKR, stratégie, board pack. Vision transversale.",
    agent: "DirectionAgent",
    frontTools: ["memory_table", "alert_card"],
  },
  {
    id: "memoire",
    num: 7,
    name: "Mémoire",
    description: "Concierge mémoire : protège l'important, archive le périmé. Déclenché par script.",
    agent: "MemoireAgent",
    frontTools: ["memory_table"],
  },
  {
    id: "sre",
    num: 8,
    name: "SRE & Meta-Ops",
    description: "Santé de la flotte : watchers, uptime, backups, secrets. Aucun agent — cron auto.",
    agent: null,
    frontTools: ["alert_card"],
  },
];
