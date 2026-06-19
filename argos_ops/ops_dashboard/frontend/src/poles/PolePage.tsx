// Page générique d'un pôle (archi v2). Chaque pôle a sa page dédiée branchée
// sur le backend, chargée en lazy (code-split par pôle — recharts/dnd-kit ne
// sont tirés que pour le pôle ouvert). Fallback générique conservé par sûreté.

import { lazy, Suspense } from "react";
import type { ComponentType, LazyExoticComponent, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Badge } from "../components/ui.tsx";
import { AlertCardEmpty, MemoryTable, ValidationQueue } from "./components/index.ts";
import type { FrontTool, PoleDef } from "./poles.ts";

const PAGES: Record<string, LazyExoticComponent<ComponentType>> = {
  veille: lazy(() => import("./veille/VeillePage.tsx").then((m) => ({ default: m.VeillePage }))),
  marketing: lazy(() => import("./marketing/MarketingPage.tsx").then((m) => ({ default: m.MarketingPage }))),
  pub: lazy(() => import("./pub/PubPage.tsx").then((m) => ({ default: m.PubPage }))),
  vente: lazy(() => import("./vente/VentePage.tsx").then((m) => ({ default: m.VentePage }))),
  finance: lazy(() => import("./finance/FinancePage.tsx").then((m) => ({ default: m.FinancePage }))),
  direction: lazy(() => import("./direction/DirectionPage.tsx").then((m) => ({ default: m.DirectionPage }))),
  memoire: lazy(() => import("./memoire/MemoirePage.tsx").then((m) => ({ default: m.MemoirePage }))),
  sre: lazy(() => import("./sre/SrePage.tsx").then((m) => ({ default: m.SrePage }))),
};

function PoleLoading() {
  return (
    <div className="flex items-center justify-center py-20 text-argos-fg-tertiary" role="status" aria-live="polite">
      <Loader2 size={18} className="animate-spin motion-reduce:animate-none" aria-hidden />
      <span className="ml-2 text-sm">Chargement du pôle…</span>
    </div>
  );
}

const TOOL_LABEL: Record<FrontTool, string> = {
  memory_table: "Mémoire du pôle",
  alert_card: "Alertes",
  validation_queue: "File de validation",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">{title}</h2>
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
  const Page = PAGES[pole.id];
  if (Page) {
    return (
      <Suspense fallback={<PoleLoading />}>
        <Page />
      </Suspense>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2 border-b border-argos-border-subtle pb-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-argos-fg-tertiary">Pôle {pole.num}/8</span>
          {pole.agent ? (
            <Badge tone="info">{pole.agent}</Badge>
          ) : (
            <Badge tone="neutral">aucun agent — cron pur</Badge>
          )}
        </div>
        <h1 className="font-mono text-lg font-medium text-argos-fg">{pole.name}</h1>
        <p className="max-w-2xl font-mono text-[11px] leading-snug text-argos-fg-secondary">{pole.description}</p>
      </header>
      {pole.frontTools.map((tool) => (
        <Section key={tool} title={TOOL_LABEL[tool]}>
          {renderTool(tool)}
        </Section>
      ))}
    </div>
  );
}
