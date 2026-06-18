// Audit du câblage inter-pôles (archi v2, S7) — CapabilityRouter v2. Liste les
// arêtes « qui lit la mémoire de qui » (reads_cross_pole) + les anomalies
// (orphelin / auto-référence / câblage à vide / producteur non lu).

import type { WiringAudit } from "../api.ts";
import { Badge } from "../../components/ui.tsx";
import { severityTone } from "./lib.ts";

export function WiringBoard({ wiring }: { wiring: WiringAudit }) {
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

      <section className="flex flex-col gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Câblage ({wiring.n_edges} arête(s))
        </h3>
        <div className="overflow-x-auto rounded-md border border-argos-border-subtle bg-argos-surface">
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
                  <td className="px-3 py-2 font-mono text-[11px] text-argos-fg-tertiary">
                    {e.target_facts}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
