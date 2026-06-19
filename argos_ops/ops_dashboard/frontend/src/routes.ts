// Modèle de routing du cockpit unifié (refonte SF, Phase 2b). Routing par état
// (pas de react-router, cohérent avec l'existant). Une seule app : Home global
// + 8 pôles + outils globaux migrés du legacy (Inbox, Outputs, Atelier, Aide).

import type { LucideIcon } from "lucide-react";
import { Archive, BookOpen, Inbox, Sparkles } from "lucide-react";

export type ToolId = "inbox" | "outputs" | "atelier" | "help";

export type Route =
  | { kind: "home" }
  | { kind: "pole"; id: string }
  | { kind: "tool"; id: ToolId };

export interface ToolDef {
  id: ToolId;
  name: string;
  icon: LucideIcon;
  description: string;
}

// Outils globaux : aucun pôle ne les couvre (cf. audit Phase 0).
export const TOOLS: ToolDef[] = [
  {
    id: "inbox",
    name: "Inbox",
    icon: Inbox,
    description: "File cross-pôle des drafts en attente de validation humaine.",
  },
  {
    id: "outputs",
    name: "Outputs",
    icon: Archive,
    description: "Archive de toutes les productions de la flotte (recherche + preview).",
  },
  {
    id: "atelier",
    name: "Atelier",
    icon: Sparkles,
    description: "Claude Code piloté depuis le panel (local-only, D-029/D-032).",
  },
  {
    id: "help",
    name: "Aide",
    icon: BookOpen,
    description: "Glossaire, raccourcis clavier, relance de l'onboarding.",
  },
];

export function sameRoute(a: Route, b: Route): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "pole" && b.kind === "pole") return a.id === b.id;
  if (a.kind === "tool" && b.kind === "tool") return a.id === b.id;
  return a.kind === b.kind;
}
