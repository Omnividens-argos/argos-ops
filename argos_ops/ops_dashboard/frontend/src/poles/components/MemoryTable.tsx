// Composant partagé « table mémoire » — affiche les faits écrits par les scripts
// d'un pôle (cf. argos_ops/poles/memory.py). Réutilisé par chaque onglet pôle.
// En S0 : rendu + état vide ; les sessions pôle passent de vraies `rows`.

import { Badge } from "../../components/ui.tsx";

export interface MemoryRow {
  id: string;
  pole: string;
  script: string;
  kind: string;
  important: boolean;
  /** ISO 8601 (created_at du fait). */
  createdAt: string;
  body: string;
}

function shortDate(iso: string): string {
  // Affichage compact AAAA-MM-JJ HH:MM sans dépendance externe.
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function MemoryTable({ rows }: { rows: MemoryRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
        Aucun fait en mémoire pour ce pôle.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border border-argos-border-subtle bg-argos-surface">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-argos-border-subtle text-argos-fg-tertiary">
            {["Quand", "Script", "Kind", "Fait", ""].map((h) => (
              <th
                key={h || "flag"}
                className="px-3 py-2 font-mono text-[10px] uppercase tracking-widest font-medium"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              className="border-b border-argos-border-subtle/60 last:border-0 hover:bg-argos-surface-2"
            >
              <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-argos-fg-tertiary">
                {shortDate(r.createdAt)}
              </td>
              <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-argos-fg-secondary">
                {r.script}
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                <Badge tone="info">{r.kind}</Badge>
              </td>
              <td className="px-3 py-2 font-mono text-[11px] text-argos-fg">
                <span className="line-clamp-2">{r.body}</span>
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right">
                {r.important && <Badge tone="warning">important</Badge>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
