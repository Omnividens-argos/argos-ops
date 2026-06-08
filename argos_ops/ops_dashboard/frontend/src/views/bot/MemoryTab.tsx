// Onglet Mémoire du détail bot — élève l'ancienne MemorySection.
// Organisation : graphe d'accès → OUT (mémoire propre, groupée par date,
// code couleur fraîcheur/TTL) → IN (mémoire accessible chez les autres bots).

import { ArrowDownToLine, ArrowUpRight, Brain } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { BotMemoryView, FactRow } from "../../api";
import { appendAgentFact, archiveAgentFact, fetchAgentMemory } from "../../api";
import { SkeletonList } from "../../components/Skeleton";
import { useToast } from "../../components/Toast";
import { Badge, Flash } from "../../components/ui";
import { AccessGraphRow, AddFactForm, FactCard, SectionHeader } from "./shared";

// Buckets temporels pour grouper la mémoire propre par date.
const BUCKETS = [
  { key: "today", label: "Aujourd'hui", maxDays: 1 },
  { key: "week", label: "7 derniers jours", maxDays: 7 },
  { key: "month", label: "Ce mois", maxDays: 31 },
  { key: "older", label: "Plus ancien", maxDays: Infinity },
] as const;

function bucketFor(iso: string): (typeof BUCKETS)[number]["key"] {
  const ageDays = (Date.now() - new Date(iso).getTime()) / 86_400_000;
  for (const b of BUCKETS) {
    if (ageDays < b.maxDays) return b.key;
  }
  return "older";
}

interface GroupedFacts {
  active: { key: string; label: string; facts: FactRow[] }[];
  archived: FactRow[];
}

function groupByDate(facts: FactRow[]): GroupedFacts {
  const archived = facts.filter((f) => f.status === "archived");
  const active = facts.filter((f) => f.status !== "archived");
  const groups = BUCKETS.map((b) => ({
    key: b.key,
    label: b.label,
    facts: active
      .filter((f) => bucketFor(f.created_at) === b.key)
      .sort((a, c) => +new Date(c.created_at) - +new Date(a.created_at)),
  })).filter((g) => g.facts.length > 0);
  return { active: groups, archived };
}

export function MemoryTab({ botName }: { botName: string }) {
  const [data, setData] = useState<BotMemoryView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const toast = useToast();

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    fetchAgentMemory(botName, controller.signal)
      .then(setData)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError((e as Error).message);
      });
    return () => controller.abort();
  }, [botName, reloadKey]);

  const reload = () => setReloadKey((k) => k + 1);

  const handleAdd = async (body: string, kind: string) => {
    try {
      await appendAgentFact(botName, { body, kind: kind || "note" });
      toast.success("Fait ajouté à la mémoire");
      reload();
    } catch (e) {
      toast.error(`Ajout : ${(e as Error).message}`);
      throw e;
    }
  };

  const handleArchive = async (factId: string) => {
    try {
      await archiveAgentFact(botName, factId);
      toast.success("Fait archivé");
      reload();
    } catch (e) {
      toast.error(`Archivage : ${(e as Error).message}`);
    }
  };

  const grouped = useMemo(
    () => (data ? groupByDate(data.own) : null),
    [data],
  );

  return (
    <div className="space-y-5">
      <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-5">
        <SectionHeader
          title="Mémoire de flotte"
          subtitle="Ce que le bot retient (OUT) + ce qu'il lit chez les autres (IN)"
          icon={Brain}
        />
        <FreshnessLegend />
        {error && <Flash variant="error" message={`Mémoire : ${error}`} />}
        {data === null && error === null && <SkeletonList count={3} />}
        {data && grouped && (
          <div className="space-y-6">
            <AccessGraphRow reads={data.reads} readBy={data.read_by} />

            {/* OUT — mémoire propre, groupée par date */}
            <div>
              <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2 flex items-center gap-1.5">
                <ArrowUpRight size={12} strokeWidth={2} className="text-argos-healthy" />
                OUT — mémoire propre · {data.own.length} fait
                {data.own.length > 1 ? "s" : ""}
              </h3>
              <AddFactForm onAdd={handleAdd} />
              {data.own.length === 0 ? (
                <div className="mt-3 font-mono text-[11px] text-argos-fg-tertiary">
                  Ce bot n'a encore rien extrait.
                </div>
              ) : (
                <div className="mt-3 space-y-4">
                  {grouped.active.map((g) => (
                    <DateGroup key={g.key} label={g.label} count={g.facts.length}>
                      {g.facts.map((f) => (
                        <FactCard
                          key={f.id}
                          fact={f}
                          onArchive={() => handleArchive(f.id)}
                        />
                      ))}
                    </DateGroup>
                  ))}
                  {grouped.archived.length > 0 && (
                    <DateGroup
                      label="Archivés"
                      count={grouped.archived.length}
                      muted
                    >
                      {grouped.archived.map((f) => (
                        <FactCard key={f.id} fact={f} />
                      ))}
                    </DateGroup>
                  )}
                </div>
              )}
            </div>

            {/* IN — mémoire accessible (lecture seule) */}
            {data.visible.length > 0 && (
              <div>
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-2 flex items-center gap-1.5">
                  <ArrowDownToLine size={12} strokeWidth={2} className="text-argos-info" />
                  IN — mémoire accessible (lecture seule) · {data.visible.length} bot
                  {data.visible.length > 1 ? "s" : ""}
                </h3>
                <div className="space-y-3">
                  {data.visible.map((vis) => (
                    <div key={vis.bot}>
                      <div className="font-mono text-[11px] text-argos-fg-secondary mb-1 flex items-center gap-1.5">
                        <ArrowUpRight
                          size={11}
                          strokeWidth={2}
                          className="text-argos-fg-tertiary"
                        />
                        {vis.bot}
                        <span className="text-argos-fg-tertiary">
                          · {vis.facts.length} fait{vis.facts.length > 1 ? "s" : ""}
                        </span>
                      </div>
                      {vis.facts.length === 0 ? (
                        <div className="font-mono text-[10px] text-argos-fg-tertiary pl-4">
                          (vide)
                        </div>
                      ) : (
                        <ul className="space-y-1.5">
                          {vis.facts.map((f) => (
                            <FactCard key={`${vis.bot}-${f.id}`} fact={f} />
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function DateGroup({
  label,
  count,
  muted,
  children,
}: {
  label: string;
  count: number;
  muted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        className={`font-mono text-[10px] uppercase tracking-widest mb-1.5 flex items-center gap-2 ${
          muted ? "text-argos-fg-disabled" : "text-argos-fg-secondary"
        }`}
      >
        <span>{label}</span>
        <span className="h-px flex-1 bg-argos-border-subtle" />
        <span>{count}</span>
      </div>
      <ul className="space-y-1.5">{children}</ul>
    </div>
  );
}

function FreshnessLegend() {
  const items: { dot: string; label: string }[] = [
    { dot: "bg-argos-healthy", label: "frais" },
    { dot: "bg-argos-warning", label: "proche TTL / vieillit" },
    { dot: "bg-argos-danger", label: "périmé" },
    { dot: "bg-argos-fg-disabled", label: "archivé" },
  ];
  return (
    <div className="mb-3 flex items-center gap-3 flex-wrap font-mono text-[10px] text-argos-fg-tertiary">
      <span className="uppercase tracking-widest">Fraîcheur</span>
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1">
          <span className={`size-1.5 rounded-full ${it.dot}`} />
          {it.label}
        </span>
      ))}
      <Badge tone="neutral">code couleur = âge vs TTL</Badge>
    </div>
  );
}
