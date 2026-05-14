import { ArrowLeft, Construction } from "lucide-react";
import type { CatalogAgent, CatalogCategory } from "../lib/agentCatalog";
import { Badge, Button } from "../components/ui";

// Page preview pour les agents pas encore implémentés (slots roadmap).
// Pas de fetch backend — tout est dérivé du catalogue. Sert à :
// 1. Donner une vue claire du scope prévu (description, dépendances, sprint)
// 2. Éviter de créer 13 stubs backend morts (YAGNI strict — Annexe D du plan)
// 3. Préparer le terrain pour brancher l'agent en plug-and-play quand son sprint arrive

interface Props {
  agent: CatalogAgent;
  category: CatalogCategory;
  onBack: () => void;
}

export function AgentRoadmapDetail({ agent, category, onBack }: Props) {
  return (
    <div className="p-6 space-y-5">
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={onBack}>
              <span className="inline-flex items-center gap-1.5">
                <ArrowLeft size={12} /> Retour
              </span>
            </Button>
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
                {category.title}
              </div>
              <h1 className="text-xl font-semibold text-argos-fg-secondary">
                {agent.displayName}
              </h1>
            </div>
          </div>
          <Badge tone="neutral">
            <span className="inline-flex items-center gap-1.5">
              <Construction size={11} /> Roadmap
            </span>
          </Badge>
        </div>
        <p className="text-sm text-argos-fg-secondary max-w-3xl">{agent.description}</p>
        <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {agent.shortLabel}
        </div>
      </header>

      <section className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface/50 p-5">
        <div className="flex items-start gap-3">
          <Construction
            size={18}
            className="text-argos-warning shrink-0 mt-0.5"
            strokeWidth={2}
          />
          <div className="space-y-2 text-sm text-argos-fg-secondary leading-relaxed">
            <p>
              <span className="font-semibold text-argos-fg">Pas encore implémenté.</span>{" "}
              Cet agent est au plan mais reste un slot roadmap — pas de code backend,
              pas de cron, pas de runs.
            </p>
            <p className="text-xs text-argos-fg-tertiary">
              Règle YAGNI (Annexe D du plan) : on n'écrit pas le code par anticipation.
              L'UI est prête (cette page existe) ; le jour où l'agent est priorisé, on
              instancie sa classe <span className="font-mono">BaseAgent</span> et la
              page se branche automatiquement sur les vraies données.
            </p>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <InfoCard
          label="Sprint pressenti"
          value={agent.sprint ?? agent.roadmapRef ?? "—"}
        />
        <InfoCard label="Catégorie" value={category.title} />
        <InfoCard
          label="Référence plan"
          value={agent.roadmapRef ?? "—"}
          mono
        />
      </section>

      {agent.dependencies && agent.dependencies.length > 0 && (
        <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
          <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
            Dépendances
          </h2>
          <ul className="space-y-1.5">
            {agent.dependencies.map((dep) => (
              <li
                key={dep}
                className="font-mono text-xs text-argos-fg-secondary flex items-start gap-2"
              >
                <span className="text-argos-fg-tertiary">→</span>
                {dep}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          Quand cet agent passera-t-il actif ?
        </h2>
        <p className="text-xs text-argos-fg-secondary leading-relaxed">
          Quand un signal business le justifie : besoin opérationnel concret, partie
          du plan ouverte, ou critère de priorisation déclenché (cf. Annexe D —
          ex. ReviewBot quand 20+ clients actifs ; ChurnPredictor au-delà de 50+
          clients ; AdBot quand le budget pub dépasse 0 €).
        </p>
      </section>
    </div>
  );
}

function InfoCard({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-1.5">
        {label}
      </div>
      <div className={`text-sm text-argos-fg ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </div>
    </div>
  );
}
