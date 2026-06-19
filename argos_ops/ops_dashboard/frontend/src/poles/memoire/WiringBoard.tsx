// Audit du câblage inter-pôles (archi v2, S7) — CapabilityRouter v2. Diagramme
// node-link (pôles = nœuds sur un cercle, arêtes « qui lit la mémoire de qui »
// = reads_cross_pole) + anomalies (orphelin / auto-référence / câblage à vide /
// producteur non lu). SVG pur, aucune dépendance graphe externe.

import type { WiringAudit, WiringEdge } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { severityTone } from "./lib.ts";
import type { Tone } from "../../components/tones.ts";

// --- Constantes de mise en page du graphe -----------------------------------
const VIEW = 520; // viewBox carré (coordonnées internes, mises à l'échelle)
const CENTER = VIEW / 2;
const RADIUS = 200; // rayon du cercle des nœuds
const NODE_R = 26; // rayon d'un nœud

// Couleurs thème-aware (CSS vars => clair/sombre, cf. Chart.tsx).
const C_FG_TERTIARY = "rgb(var(--color-fg-tertiary))";
const C_BORDER = "rgb(var(--color-border))";
const C_SURFACE = "rgb(var(--color-bg-surface-2))";

const TONE_VAR: Record<Tone, string> = {
  neutral: "rgb(var(--color-fg-tertiary))",
  healthy: "rgb(var(--color-healthy))",
  info: "rgb(var(--color-info))",
  warning: "rgb(var(--color-warning))",
  danger: "rgb(var(--color-danger))",
};

// Ordre de gravité pour retenir la pire anomalie par pôle.
const TONE_RANK: Record<Tone, number> = {
  neutral: 0,
  healthy: 0,
  info: 1,
  warning: 2,
  danger: 3,
};

interface NodePos {
  id: string;
  x: number;
  y: number;
  tone: Tone;
}

/** Coordonnée d'un nœud i sur le cercle (départ en haut, sens horaire). */
function nodePosition(i: number, total: number): { x: number; y: number } {
  if (total <= 0) return { x: CENTER, y: CENTER };
  const angle = (i / total) * 2 * Math.PI - Math.PI / 2;
  return {
    x: CENTER + RADIUS * Math.cos(angle),
    y: CENTER + RADIUS * Math.sin(angle),
  };
}

/** Largeur de trait d'une arête selon le nombre de faits cible. */
function edgeStrokeWidth(targetFacts: number): number {
  if (targetFacts <= 0) return 1;
  // 1 → 3.5px en compressant l'échelle (log) pour rester lisible.
  return Math.min(1 + Math.log1p(targetFacts) * 0.9, 4);
}

/**
 * Chemin SVG d'une arête source → cible : on raccourcit aux bords des nœuds et
 * on courbe légèrement (offset perpendiculaire) pour distinguer les arêtes
 * réciproques A→B / B→A.
 */
function edgePath(a: NodePos, b: NodePos): string {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  // Décalage perpendiculaire pour la courbure (sens stable A<B vs A>B).
  const sign = a.id < b.id ? 1 : -1;
  const bow = Math.min(len * 0.18, 46) * sign;
  const px = -uy * bow;
  const py = ux * bow;
  // Points de départ / arrivée raccourcis au bord des nœuds.
  const sx = a.x + ux * NODE_R;
  const sy = a.y + uy * NODE_R;
  const ex = b.x - ux * (NODE_R + 7);
  const ey = b.y - uy * (NODE_R + 7);
  const mx = (sx + ex) / 2 + px;
  const my = (sy + ey) / 2 + py;
  return `M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${mx.toFixed(1)} ${my.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`;
}

export function WiringBoard({ wiring }: { wiring: WiringAudit }) {
  // Pire tonalité d'anomalie par pôle (pour colorer les nœuds).
  const toneByPole = new Map<string, Tone>();
  for (const a of wiring.anomalies) {
    const tone = severityTone(a.severity);
    const prev = toneByPole.get(a.pole);
    if (prev === undefined || TONE_RANK[tone] > TONE_RANK[prev]) {
      toneByPole.set(a.pole, tone);
    }
  }

  // Pôles à placer : ceux déclarés + tout pôle apparaissant dans une arête.
  const poleSet = new Set<string>(wiring.poles);
  for (const e of wiring.edges) {
    poleSet.add(e.source);
    poleSet.add(e.target);
  }
  const poles = [...poleSet];

  const nodes: NodePos[] = poles.map((id, i) => {
    const { x, y } = nodePosition(i, poles.length);
    return { id, x, y, tone: toneByPole.get(id) ?? "neutral" };
  });
  const nodeById = new Map(nodes.map((n) => [n.id, n] as const));

  const graphSummary =
    `Diagramme du câblage inter-pôles : ${poles.length} pôle(s), ` +
    `${wiring.edges.length} arête(s) « lit la mémoire de ». ${wiring.summary}`;

  // Arêtes résolues (les deux extrémités connues).
  const resolvedEdges = wiring.edges
    .map((e) => {
      const a = nodeById.get(e.source);
      const b = nodeById.get(e.target);
      if (!a || !b) return null;
      return { edge: e, a, b };
    })
    .filter((x): x is { edge: WiringEdge; a: NodePos; b: NodePos } => x !== null);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 font-mono text-[11px]">
        <Badge tone={wiring.should_alert ? "warning" : "healthy"}>
          {wiring.should_alert ? `${wiring.n_warning} warning(s)` : "câblage sain"}
        </Badge>
        <span className="text-argos-fg-tertiary">{wiring.summary}</span>
      </div>

      <section className="flex flex-col gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Graphe du câblage ({wiring.n_edges} arête(s))
        </h3>

        {/* Légende */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[10px] text-argos-fg-tertiary">
          <span className="inline-flex items-center gap-1.5">
            <svg width="26" height="8" aria-hidden="true">
              <line x1="1" y1="4" x2="25" y2="4" stroke={C_FG_TERTIARY} strokeWidth="2" />
            </svg>
            règle explicite
          </span>
          <span className="inline-flex items-center gap-1.5">
            <svg width="26" height="8" aria-hidden="true">
              <line
                x1="1"
                y1="4"
                x2="25"
                y2="4"
                stroke="rgb(var(--color-info))"
                strokeWidth="2"
                strokeDasharray="4 3"
              />
            </svg>
            via wildcard (*)
          </span>
          <span>épaisseur ∝ faits cible</span>
        </div>

        {poles.length === 0 ? (
          <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
            Aucun pôle à afficher.
          </div>
        ) : (
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-2">
            <svg
              viewBox={`0 0 ${VIEW} ${VIEW}`}
              className="h-auto w-full max-w-2xl mx-auto"
              role="img"
              aria-label={graphSummary}
              aria-describedby="wiring-graph-fallback"
            >
              <title>{graphSummary}</title>
              <defs>
                <marker
                  id="wiring-arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={C_FG_TERTIARY} />
                </marker>
                <marker
                  id="wiring-arrow-wild"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--color-info))" />
                </marker>
              </defs>

              {/* Arêtes (dessinées sous les nœuds) */}
              <g aria-hidden="true">
                {resolvedEdges.map(({ edge, a, b }) => {
                  const d = edgePath(a, b);
                  const stroke = edge.via_wildcard
                    ? "rgb(var(--color-info))"
                    : C_FG_TERTIARY;
                  return (
                    <path
                      key={`${edge.source}->${edge.target}`}
                      d={d}
                      fill="none"
                      stroke={stroke}
                      strokeWidth={edgeStrokeWidth(edge.target_facts)}
                      strokeDasharray={edge.via_wildcard ? "5 4" : undefined}
                      strokeOpacity={0.75}
                      markerEnd={`url(#${edge.via_wildcard ? "wiring-arrow-wild" : "wiring-arrow"})`}
                    >
                      <title>
                        {`${edge.source} → ${edge.target} · ${edge.via_wildcard ? "wildcard" : "explicite"} · ${edge.target_facts} fait(s)`}
                      </title>
                    </path>
                  );
                })}
              </g>

              {/* Nœuds (pôles) */}
              <g aria-hidden="true">
                {nodes.map((n) => {
                  const color = TONE_VAR[n.tone];
                  const isAnomalous = n.tone !== "neutral";
                  return (
                    <g key={n.id}>
                      <circle
                        cx={n.x}
                        cy={n.y}
                        r={NODE_R}
                        fill={C_SURFACE}
                        stroke={isAnomalous ? color : C_BORDER}
                        strokeWidth={isAnomalous ? 2.5 : 1.5}
                      />
                      <text
                        x={n.x}
                        y={n.y}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontFamily="ui-monospace, monospace"
                        fontSize="11"
                        fontWeight={isAnomalous ? 600 : 500}
                        fill={isAnomalous ? color : "rgb(var(--color-fg))"}
                      >
                        {n.id}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
        )}

        {/* Repli accessible (lecteurs d'écran) : table équivalente des arêtes. */}
        <details
          id="wiring-graph-fallback"
          className="rounded-md border border-argos-border-subtle bg-argos-surface"
        >
          <summary className="cursor-pointer px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg">
            Table des arêtes (équivalent texte)
          </summary>
          <div className="overflow-x-auto border-t border-argos-border-subtle">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-argos-border-subtle text-argos-fg-tertiary">
                  {["Lecteur", "→ lit", "Via", "Faits cible"].map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2 font-mono text-[10px] uppercase tracking-widest font-medium"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {wiring.edges.map((e) => (
                  <tr
                    key={`${e.source}->${e.target}`}
                    className="border-b border-argos-border-subtle/60 last:border-0"
                  >
                    <td className="px-3 py-2 font-mono text-[11px] text-argos-fg">{e.source}</td>
                    <td className="px-3 py-2 font-mono text-[11px] text-argos-fg-secondary">
                      {e.target}
                    </td>
                    <td className="px-3 py-2">
                      {e.via_wildcard ? (
                        <Badge tone="info">*</Badge>
                      ) : (
                        <Badge tone="neutral">explicite</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-argos-fg-tertiary tabular-nums">
                      {e.target_facts}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Anomalies
        </h3>
        {wiring.anomalies.length === 0 ? (
          <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-4 text-center font-mono text-[11px] text-argos-fg-tertiary">
            Aucune anomalie de câblage.
          </div>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {wiring.anomalies.map((a, i) => (
              <li
                key={`${a.kind}-${a.pole}-${i}`}
                className="flex items-center gap-2.5 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2"
              >
                <Badge tone={severityTone(a.severity)}>{a.kind}</Badge>
                <span className="font-mono text-[11px] text-argos-fg-secondary">{a.pole}</span>
                <span className="font-mono text-[11px] text-argos-fg-tertiary">{a.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
