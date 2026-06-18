// Configuration de l'activation de la curation par pôle (archi v2, S7).
// Toggle on/off par pôle (PUT /policy) + rappel des bornes de rétention.

import { useCallback, useState } from "react";
import { type MemoirePoleStat, type MemoirePolicy, updateMemoirePolicy } from "../api.ts";
import { Badge, Flash, Toggle } from "../../components/ui.tsx";

export function PolicyConfig({
  policy,
  poles,
  onChanged,
}: {
  policy: MemoirePolicy;
  poles: MemoirePoleStat[];
  onChanged?: () => void;
}) {
  const [active, setActive] = useState<Set<string>>(new Set(policy.active_for));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = useCallback(
    async (pole: string, next: boolean) => {
      setBusy(pole);
      setError(null);
      try {
        const updated = await updateMemoirePolicy(pole, next);
        setActive(new Set(updated.active_for));
        onChanged?.();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Échec de la mise à jour");
      } finally {
        setBusy(null);
      }
    },
    [onChanged],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2 font-mono text-[10px] text-argos-fg-tertiary">
        <Badge tone={policy.protect_important ? "healthy" : "danger"}>
          protect_important: {String(policy.protect_important)}
        </Badge>
        <span>TTL défaut {policy.default_ttl_days} j</span>
        <span>garde {policy.keep_recent_per_kind} récents/kind</span>
        <span>stale ≥ {policy.min_stale_days} j</span>
        {policy.protected_kinds.length > 0 && (
          <span>kinds protégés : {policy.protected_kinds.join(", ")}</span>
        )}
      </div>

      {error && <Flash variant="error" message={error} onDismiss={() => setError(null)} />}

      <div className="overflow-x-auto rounded-md border border-argos-border-subtle bg-argos-surface">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-argos-border-subtle text-argos-fg-tertiary">
              {["Pôle", "Faits", "Important", "Candidats", "Curation"].map((h) => (
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
            {poles.map((p) => (
              <tr
                key={p.pole}
                className="border-b border-argos-border-subtle/60 last:border-0 hover:bg-argos-surface-2"
              >
                <td className="px-3 py-2 font-mono text-[11px] text-argos-fg">{p.name}</td>
                <td className="px-3 py-2 font-mono text-[11px] text-argos-fg-tertiary">
                  {p.n_facts}
                </td>
                <td className="px-3 py-2 font-mono text-[11px] text-argos-warning">
                  {p.n_important}
                </td>
                <td className="px-3 py-2 font-mono text-[11px] text-argos-danger">
                  {p.n_candidates}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Toggle
                      enabled={active.has(p.pole)}
                      disabled={busy === p.pole}
                      onChange={(next) => toggle(p.pole, next)}
                      label={`curation ${p.pole}`}
                    />
                    <span className="font-mono text-[10px] text-argos-fg-tertiary">
                      {active.has(p.pole) ? "active" : "off"}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="font-mono text-[10px] leading-snug text-argos-fg-disabled">
        Un pôle inactif n'est jamais nettoyé. Un fait « important » (ou pattern protégé) reste
        non supprimable même quand la curation est active.
      </p>
    </div>
  );
}
