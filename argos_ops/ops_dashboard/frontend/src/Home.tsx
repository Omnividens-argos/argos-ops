// Home — dashboard global cross-pôle (refonte SF). Landing du cockpit unifié :
// KPIs clés, santé de la flotte, breakers actifs, accès rapide aux 8 pôles.
// Données réelles via React Query (endpoints legacy KPIs/health/breakers).
// Enrichi en Phase 3 (signaux handoffs entrants, santé par pôle, file inbox).

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, ArrowRight, Banknote, Inbox as InboxIcon, Share2, Ticket, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { fetchBreakers, fetchHealthSnapshot, fetchInboxDrafts, fetchKPIs } from "./api";
import { fetchIncomingHandoffs } from "./poles/api.ts";
import { Badge } from "./components/ui.tsx";
import { EmptyState } from "./components/EmptyState.tsx";
import { SkeletonGrid } from "./components/Skeleton.tsx";
import { POLES } from "./poles/poles.ts";
import type { Route } from "./routes.ts";
import { qk } from "./lib/queryClient.ts";

function eur(n: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
}

function KpiCard({ label, value, sub, icon: Icon, tone }: {
  label: string;
  value: string;
  sub?: string;
  icon: LucideIcon;
  tone?: "healthy" | "warning" | "danger";
}) {
  const accent = tone === "danger" ? "text-argos-danger" : tone === "warning" ? "text-argos-warning" : tone === "healthy" ? "text-argos-healthy" : "text-argos-fg-tertiary";
  return (
    <div className="rounded-md border border-argos-border bg-argos-surface p-4 transition-colors hover:border-argos-border/70">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wider text-argos-fg-tertiary">{label}</span>
        <Icon size={14} className={accent} aria-hidden />
      </div>
      <div className="mt-1.5 font-mono text-2xl font-semibold tabular-nums text-argos-fg">{value}</div>
      {sub ? <div className="mt-0.5 text-[11px] text-argos-fg-tertiary">{sub}</div> : null}
    </div>
  );
}

export function Home({ onNavigate }: { onNavigate: (route: Route) => void }) {
  const kpis = useQuery({ queryKey: [...qk.home, "kpis"], queryFn: ({ signal }) => fetchKPIs(signal) });
  const health = useQuery({ queryKey: [...qk.home, "health"], queryFn: ({ signal }) => fetchHealthSnapshot(signal) });
  const breakers = useQuery({ queryKey: [...qk.home, "breakers"], queryFn: ({ signal }) => fetchBreakers(signal) });
  const handoffs = useQuery({ queryKey: qk.handoffsIncoming, queryFn: ({ signal }) => fetchIncomingHandoffs(undefined, signal) });
  const inbox = useQuery({ queryKey: [...qk.home, "inbox"], queryFn: ({ signal }) => fetchInboxDrafts(signal) });

  const tripped = (breakers.data ?? []).filter((b) => b.tripped);
  const k = kpis.data;
  const h = health.data;

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-6 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-argos-fg">Vue d'ensemble</h1>
        <p className="text-sm text-argos-fg-secondary">
          État consolidé de la flotte Argos Ops — KPIs, santé et accès aux 8 pôles.
        </p>
      </header>

      {/* KPIs */}
      {kpis.isLoading ? (
        <SkeletonGrid count={4} />
      ) : kpis.isError ? (
        <EmptyState tone="error" title="Backend injoignable" body="Impossible de charger les KPIs (/api/kpis/overview)." />
      ) : k ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="MRR" value={eur(k.mrr_eur)} sub={`ARR ${eur(k.arr_eur)}`} icon={Banknote} tone="healthy" />
          <KpiCard label="Abonnements actifs" value={String(k.active_subscriptions)} icon={Users} />
          <KpiCard label="Leads 24h" value={String(k.leads_last_24h)} sub={`${k.open_tickets} tickets ouverts`} icon={Activity} />
          <KpiCard
            label="Breakers armés"
            value={String(k.tripped_breakers)}
            icon={AlertTriangle}
            tone={k.tripped_breakers > 0 ? "danger" : "healthy"}
          />
        </div>
      ) : null}

      {inbox.data && inbox.data.length > 0 ? (
        <button
          type="button"
          onClick={() => onNavigate({ kind: "tool", id: "inbox" })}
          className="flex items-center justify-between gap-3 rounded-md border border-argos-info/40 bg-argos-info/10 px-4 py-3 text-left transition-colors hover:bg-argos-info/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
        >
          <span className="flex items-center gap-2 text-sm text-argos-fg">
            <InboxIcon size={15} className="text-argos-info" aria-hidden />
            <span className="font-mono font-semibold tabular-nums">{inbox.data.length}</span>
            draft(s) à valider dans l'Inbox
          </span>
          <ArrowRight size={15} className="text-argos-info" aria-hidden />
        </button>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Santé flotte + breakers */}
        <section className="flex flex-col gap-3 lg:col-span-1">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-argos-fg-tertiary">Santé de la flotte</h2>
          <div className="rounded-md border border-argos-border bg-argos-surface p-4">
            {health.isLoading ? (
              <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
            ) : h ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-argos-fg-tertiary">Base</dt>
                  <dd className="mt-0.5">
                    <Badge tone={h.db_ok ? "healthy" : "danger"}>{h.db_ok ? "OK" : "KO"}</Badge>
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-argos-fg-tertiary">Runs 24h</dt>
                  <dd className="mt-0.5 font-mono tabular-nums text-argos-fg">{h.runs_last_24h}</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-argos-fg-tertiary">Échecs 24h</dt>
                  <dd className={`mt-0.5 font-mono tabular-nums ${h.failed_last_24h > 0 ? "text-argos-danger" : "text-argos-fg"}`}>
                    {h.failed_last_24h}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-argos-fg-tertiary">Agents actifs</dt>
                  <dd className="mt-0.5 font-mono tabular-nums text-argos-fg">{h.agents_breakdown.enabled}</dd>
                </div>
              </dl>
            ) : (
              <div className="text-sm text-argos-fg-tertiary">Indisponible.</div>
            )}
          </div>

          <h2 className="mt-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-argos-fg-tertiary">
            <Ticket size={12} aria-hidden /> Breakers armés
          </h2>
          {tripped.length === 0 ? (
            <div className="rounded-md border border-argos-border bg-argos-surface p-4 text-sm text-argos-fg-tertiary">
              Aucun breaker armé.
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {tripped.map((b) => (
                <li key={b.name} className="rounded-md border border-argos-danger/40 bg-argos-danger/10 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm text-argos-fg">{b.name}</span>
                    <Badge tone="danger">{b.severity}</Badge>
                  </div>
                  {b.reason ? <p className="mt-1 text-[11px] text-argos-fg-secondary">{b.reason}</p> : null}
                </li>
              ))}
            </ul>
          )}

          <h2 className="mt-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-argos-fg-tertiary">
            <Share2 size={12} aria-hidden /> Signaux reçus (handoffs)
          </h2>
          {(handoffs.data ?? []).length === 0 ? (
            <div className="rounded-md border border-argos-border bg-argos-surface p-4 text-sm text-argos-fg-tertiary">
              Aucun handoff entrant.
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {(handoffs.data ?? []).slice(0, 6).map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    onClick={() => onNavigate({ kind: "pole", id: h.target_pole })}
                    className="flex w-full items-center justify-between gap-2 rounded-md border border-argos-border bg-argos-surface p-3 text-left transition-colors hover:border-argos-info/50 hover:bg-argos-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
                  >
                    <span className="min-w-0">
                      <span className="font-mono text-[11px] text-argos-fg-tertiary">
                        {h.source_pole} → {h.target_pole}
                      </span>
                      {h.note ? (
                        <span className="block truncate text-[11px] text-argos-fg-secondary">{h.note}</span>
                      ) : null}
                    </span>
                    <ArrowRight size={13} className="shrink-0 text-argos-fg-disabled" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Accès aux pôles */}
        <section className="flex flex-col gap-3 lg:col-span-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-argos-fg-tertiary">Les 8 pôles</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {POLES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onNavigate({ kind: "pole", id: p.id })}
                className="group flex flex-col gap-1.5 rounded-md border border-argos-border bg-argos-surface p-4 text-left transition-colors hover:border-argos-info/50 hover:bg-argos-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg"
              >
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded bg-argos-surface-2 font-mono text-[10px] text-argos-fg-tertiary">
                      {p.num}
                    </span>
                    <span className="text-sm font-medium text-argos-fg">{p.name}</span>
                  </span>
                  <ArrowRight size={14} className="text-argos-fg-disabled transition-colors group-hover:text-argos-info" aria-hidden />
                </div>
                <p className="text-[11px] leading-snug text-argos-fg-tertiary">{p.description}</p>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
