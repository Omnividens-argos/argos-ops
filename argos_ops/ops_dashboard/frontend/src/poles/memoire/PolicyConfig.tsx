// Configuration de l'activation de la curation par pôle (archi v2, S7).
// Toggle on/off par pôle (PUT /policy) + rappel des bornes de rétention.

import { useCallback, useState } from "react";
import {
  type MemoirePoleStat,
  type MemoirePolicy,
  updatePolicyRetention,
  updateMemoirePolicy,
} from "../api.ts";
import { Button, Flash, TextInput, Toggle } from "../../components/ui.tsx";

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

  // Champs de rétention GLOBAUX (pas par pôle) — éditables ici.
  const [protectImportant, setProtectImportant] = useState(policy.protect_important);
  const [defaultTtlDays, setDefaultTtlDays] = useState(String(policy.default_ttl_days));
  const [keepRecentPerKind, setKeepRecentPerKind] = useState(
    String(policy.keep_recent_per_kind),
  );
  const [minStaleDays, setMinStaleDays] = useState(String(policy.min_stale_days));
  const [retentionFlash, setRetentionFlash] = useState<string | null>(null);

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

  // Sauvegarde des champs de rétention globaux. Le PUT /policy exige `pole`+`active` :
  // on cible un pôle représentatif (1er actif, sinon 1er listé) en RELAYANT son état
  // d'activation courant pour ne PAS modifier la sémantique des toggles par pôle.
  const saveRetention = useCallback(async () => {
    const representativePole = active.size > 0 ? [...active][0] : (poles[0]?.pole ?? "");
    if (!representativePole) {
      setError("Aucun pôle disponible pour porter la configuration de rétention.");
      return;
    }
    setBusy("__retention__");
    setError(null);
    setRetentionFlash(null);
    try {
      const updated = await updatePolicyRetention({
        pole: representativePole,
        active: active.has(representativePole),
        protect_important: protectImportant,
        default_ttl_days: Number(defaultTtlDays),
        keep_recent_per_kind: Number(keepRecentPerKind),
        min_stale_days: Number(minStaleDays),
      });
      setActive(new Set(updated.active_for));
      setProtectImportant(updated.protect_important);
      setDefaultTtlDays(String(updated.default_ttl_days));
      setKeepRecentPerKind(String(updated.keep_recent_per_kind));
      setMinStaleDays(String(updated.min_stale_days));
      setRetentionFlash("Rétention enregistrée.");
      onChanged?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement");
    } finally {
      setBusy(null);
    }
  }, [
    active,
    poles,
    protectImportant,
    defaultTtlDays,
    keepRecentPerKind,
    minStaleDays,
    onChanged,
  ]);

  const retentionBusy = busy === "__retention__";

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-3 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          void saveRetention();
        }}
      >
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Rétention (global)
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
              protect_important
            </span>
            <div className="flex h-[30px] items-center gap-2">
              <Toggle
                enabled={protectImportant}
                disabled={retentionBusy}
                onChange={setProtectImportant}
                label="protect_important"
              />
              <span className="font-mono text-[10px] text-argos-fg-tertiary">
                {String(protectImportant)}
              </span>
            </div>
          </div>
          <TextInput
            label="TTL défaut (j)"
            type="number"
            min={0}
            inputMode="numeric"
            className="w-28"
            value={defaultTtlDays}
            disabled={retentionBusy}
            onChange={(e) => setDefaultTtlDays(e.target.value)}
          />
          <TextInput
            label="garde récents/kind"
            type="number"
            min={0}
            inputMode="numeric"
            className="w-28"
            value={keepRecentPerKind}
            disabled={retentionBusy}
            onChange={(e) => setKeepRecentPerKind(e.target.value)}
          />
          <TextInput
            label="stale ≥ (j)"
            type="number"
            min={0}
            inputMode="numeric"
            className="w-28"
            value={minStaleDays}
            disabled={retentionBusy}
            onChange={(e) => setMinStaleDays(e.target.value)}
          />
          <Button type="submit" variant="primary" size="sm" disabled={retentionBusy}>
            enregistrer
          </Button>
        </div>
        {policy.protected_kinds.length > 0 && (
          <p className="font-mono text-[10px] text-argos-fg-tertiary">
            kinds protégés : {policy.protected_kinds.join(", ")}
          </p>
        )}
        {retentionFlash && (
          <Flash
            variant="success"
            message={retentionFlash}
            onDismiss={() => setRetentionFlash(null)}
          />
        )}
      </form>

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
