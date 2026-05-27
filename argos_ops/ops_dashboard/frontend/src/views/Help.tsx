import { BookOpen, Compass, Keyboard, RotateCcw, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { resetOnboardingFlag } from "../components/OnboardingTour";
import { Badge, Button, Flash } from "../components/ui";
import { GLOSSARY } from "../lib/glossary";

// Vue Help & Glossary — page de référence pour le founder qui ne connaît pas
// le jargon technique. Trois sections empilées :
//   1. Glossaire searchable (toutes les entrées de lib/glossary.ts)
//   2. Cheatsheet raccourcis clavier (référence statique)
//   3. « Comment ça marche » — court topo sur la flotte
//
// Plus un bouton « Relancer le tour d'onboarding » qui efface le flag
// localStorage et recharge la page.

interface HelpProps {
  onReopenOnboarding: () => void;
  onOpenShortcuts: () => void;
}

interface GlossaryEntryDisplay {
  term: string;
  short: string;
  long: string;
}

export function Help({ onReopenOnboarding, onOpenShortcuts }: HelpProps) {
  const [query, setQuery] = useState("");
  const [flash, setFlash] = useState<{
    variant: "success" | "error";
    msg: string;
  } | null>(null);

  const entries: GlossaryEntryDisplay[] = useMemo(() => {
    const list = Object.entries(GLOSSARY).map(([term, entry]) => ({
      term,
      short: entry.short,
      long: entry.long,
    }));
    list.sort((a, b) => a.term.localeCompare(b.term, "fr"));
    return list;
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q === "") return entries;
    return entries.filter(
      (e) =>
        e.term.toLowerCase().includes(q) ||
        e.short.toLowerCase().includes(q) ||
        e.long.toLowerCase().includes(q),
    );
  }, [entries, query]);

  const handleReopen = () => {
    resetOnboardingFlag();
    onReopenOnboarding();
    setFlash({
      variant: "success",
      msg: "Tour d'onboarding relancé — la modale va s'afficher.",
    });
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-argos-fg flex items-center gap-2">
          <BookOpen size={20} strokeWidth={1.5} className="text-argos-info" />
          Aide & glossaire
        </h1>
        <p className="text-sm text-argos-fg-secondary leading-relaxed max-w-2xl">
          Tout le vocabulaire technique d'Argos Ops expliqué en français
          simple, plus les raccourcis clavier qui te font gagner du temps.
        </p>
      </header>

      {flash && (
        <Flash
          variant={flash.variant}
          message={flash.msg}
          onDismiss={() => setFlash(null)}
        />
      )}

      {/* Quick actions */}
      <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <ActionCard
          icon={Compass}
          title="Relancer le tour d'onboarding"
          body="La présentation guidée en 5 étapes qui s'affiche au premier lancement."
          cta="Lancer"
          onClick={handleReopen}
        />
        <ActionCard
          icon={Keyboard}
          title="Cheatsheet des raccourcis clavier"
          body="Tous les raccourcis pour naviguer plus vite (navigation, palette, éditeur YAML)."
          cta="Afficher"
          onClick={onOpenShortcuts}
        />
      </section>

      {/* Glossary */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between flex-wrap gap-2">
          <h2 className="text-base font-semibold text-argos-fg">Glossaire</h2>
          <Badge tone="neutral">{filtered.length} / {entries.length} termes</Badge>
        </div>

        {/* Search */}
        <div className="flex items-center gap-2 bg-argos-surface border border-argos-border-subtle rounded-md px-3 py-2">
          <Search size={14} strokeWidth={2} className="text-argos-fg-tertiary shrink-0" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Cherche un terme — ex. MRR, RAG, AI Act, breaker, dunning…"
            className="flex-1 bg-transparent text-sm text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none"
          />
          {query !== "" && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="font-mono text-[10px] text-argos-fg-tertiary hover:text-argos-fg"
            >
              effacer
            </button>
          )}
        </div>

        {filtered.length === 0 ? (
          <EmptyState
            tone="neutral"
            icon={Search}
            title="Rien ne match cette recherche"
            body="Essaie un terme plus court (ex. « MRR » plutôt que « MRR brutto annuel »)."
            compact
            action={
              <Button size="sm" variant="ghost" onClick={() => setQuery("")}>
                Effacer la recherche
              </Button>
            }
          />
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((entry) => (
              <GlossaryCard key={entry.term} entry={entry} highlight={query} />
            ))}
          </ul>
        )}
      </section>

      {/* How it works — short topo */}
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5 space-y-3">
        <h2 className="text-base font-semibold text-argos-fg">
          Comment Argos Ops fonctionne (en 30 secondes)
        </h2>
        <ul className="text-sm text-argos-fg-secondary space-y-2 leading-relaxed">
          <li>
            <span className="text-argos-fg">Une flotte de 79 bots</span> tourne en cron — chacun fait
            une tâche atomique (envoi email, scan uptime, sync Stripe, etc.).
          </li>
          <li>
            <span className="text-argos-fg">Tu pilotes</span> via ce cockpit : tu peux activer / désactiver / mettre en pause
            chaque bot, ou en déclencher un manuellement (Run now).
          </li>
          <li>
            <span className="text-argos-fg">Tu valides</span> les drafts produits par les bots (cold emails, posts
            LinkedIn, devis…) dans l'Inbox. C'est ton action quotidienne.
          </li>
          <li>
            <span className="text-argos-fg">Les disjoncteurs (breakers)</span> coupent automatiquement un bot qui
            déraille (chute MRR, burst d'erreurs). Tu reset manuellement après
            avoir corrigé.
          </li>
          <li>
            <span className="text-argos-fg">100 % local-first</span> — pas d'API LLM tierce. Tout passe par Claude Code Pro
            Max + embeddings open-source ({" "}
            <code className="font-mono text-[11px] text-argos-fg-tertiary">D-017</code>{" "}
            ).
          </li>
        </ul>
      </section>
    </div>
  );
}

// =============================================================================
// Action card
// =============================================================================
function ActionCard({
  icon: Icon,
  title,
  body,
  cta,
  onClick,
}: {
  icon: typeof Compass;
  title: string;
  body: string;
  cta: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left rounded-md border border-argos-border-subtle bg-argos-surface p-4 hover:border-argos-border transition-colors group"
    >
      <div className="flex items-start gap-3">
        <Icon
          size={18}
          strokeWidth={1.5}
          className="text-argos-info shrink-0 mt-0.5"
        />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-argos-fg mb-1">{title}</div>
          <p className="text-xs text-argos-fg-secondary leading-relaxed">{body}</p>
          <span className="mt-2 inline-flex items-center gap-1 font-mono text-[11px] text-argos-info">
            {cta} →
          </span>
        </div>
      </div>
    </button>
  );
}

// =============================================================================
// Glossary card — highlight matched substring
// =============================================================================
function GlossaryCard({
  entry,
  highlight,
}: {
  entry: GlossaryEntryDisplay;
  highlight: string;
}) {
  return (
    <li className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
      <div className="flex items-baseline gap-2 mb-1 flex-wrap">
        <span className="font-mono text-sm font-semibold text-argos-fg">
          {highlightText(entry.term, highlight)}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          {highlightText(entry.short, highlight)}
        </span>
      </div>
      <p className="text-xs text-argos-fg-secondary leading-relaxed">
        {highlightText(entry.long, highlight)}
      </p>
    </li>
  );
}

function highlightText(text: string, query: string): React.ReactNode {
  const q = query.trim();
  if (q === "") return text;
  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  const parts: React.ReactNode[] = [];
  let from = 0;
  let idx = lower.indexOf(needle, from);
  let key = 0;
  while (idx !== -1) {
    if (idx > from) parts.push(text.slice(from, idx));
    parts.push(
      <mark
        key={key++}
        className="bg-argos-info/20 text-argos-fg rounded px-0.5"
      >
        {text.slice(idx, idx + needle.length)}
      </mark>,
    );
    from = idx + needle.length;
    idx = lower.indexOf(needle, from);
  }
  if (from < text.length) parts.push(text.slice(from));
  return parts;
}

// Silence unused-import for RotateCcw (kept as alternative icon for future).
void RotateCcw;
