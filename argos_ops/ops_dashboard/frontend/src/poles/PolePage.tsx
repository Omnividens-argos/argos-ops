// Page générique d'un pôle (archi v2). En S0 : page VIDE — elle compose les
// composants partagés déclarés dans `front_tools` (pole.yaml), tous en état
// vide. Chaque session pôle (S1-S8) remplacera le contenu par les vraies
// données de SON pôle, en réutilisant ces mêmes composants partagés.

import type { ReactNode } from "react";
import { Badge } from "../components/ui.tsx";
import { AlertCardEmpty, MemoryTable, ValidationQueue } from "./components/index.ts";
import type { FrontTool, PoleDef } from "./poles.ts";
import { FinancePage } from "./finance/FinancePage.tsx";
import { MarketingPage } from "./marketing/MarketingPage.tsx";
import { PubPage } from "./pub/PubPage.tsx";
import { VeillePage } from "./veille/VeillePage.tsx";
import { VentePage } from "./vente/VentePage.tsx";

const TOOL_LABEL: Record<FrontTool, string> = {
  memory_table: "Mémoire du pôle",
  alert_card: "Alertes",
  validation_queue: "File de validation",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
        {title}
      </h2>
      {children}
    </section>
  );
}

function renderTool(tool: FrontTool): ReactNode {
  switch (tool) {
    case "memory_table":
      return <MemoryTable rows={[]} />;
    case "alert_card":
      return <AlertCardEmpty />;
    case "validation_queue":
      return <ValidationQueue items={[]} />;
    default:
      return null;
  }
}

export function PolePage({ pole }: { pole: PoleDef }) {
  // Pôles livrés (archi v2) : page dédiée branchée sur le backend. Les pôles
  // pas encore traités retombent sur la page générique (composants en état vide).
  if (pole.id === "veille") {
    return <VeillePage />;
  }
  if (pole.id === "marketing") {
    return <MarketingPage />;
  }
  if (pole.id === "pub") {
    return <PubPage />;
  }
  if (pole.id === "vente") {
    return <VentePage />;
  }
  if (pole.id === "finance") {
    return <FinancePage />;
  }
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-argos-fg-tertiary">
            Pôle {pole.num}/8
          </span>
          {pole.agent ? (
            <Badge tone="info">{pole.agent}</Badge>
          ) : (
            <Badge tone="neutral">aucun agent — cron pur</Badge>
          )}
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">{pole.name}</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">
          {pole.description}
        </p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-disabled">
          page vide — socle S0, contenu à brancher dans la session de ce pôle
        </p>
      </header>

      {pole.frontTools.map((tool) => (
        <Section key={tool} title={TOOL_LABEL[tool]}>
          {renderTool(tool)}
        </Section>
      ))}
    </div>
  );
}
