// Kill-switch de la flotte (archi v2, S8) — gel global (toute la flotte) +
// gels ciblés par script. Un script gelé n'est jamais exécuté (run journalisé
// skipped) et est sauté par l'orchestrateur (verdict skipped_frozen).

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  type SreKillSwitch,
  type SreScriptStatus,
  setSreKillswitch,
  setSreKillswitchScript,
} from "../api.ts";
import { Badge, Flash, TextInput, Toggle } from "../../components/ui.tsx";
import { fmtDateTime } from "./lib.ts";

export function KillSwitchPanel({
  killswitch,
  scripts,
  onChanged,
}: {
  killswitch: SreKillSwitch;
  scripts: SreScriptStatus[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState(killswitch.reason ?? "");

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "échec");
    } finally {
      setBusy(false);
    }
  }

  const frozenSet = new Set(killswitch.frozen_scripts);

  return (
    <div className="flex flex-col gap-4">
      {error && <Flash variant="error" message={error} onDismiss={() => setError(null)} />}

      {/* Gel global */}
      <div
        className={`flex flex-col gap-3 rounded-md border px-4 py-3 ${
          killswitch.frozen
            ? "border-argos-danger/40 bg-argos-danger/5"
            : "border-argos-border-subtle bg-argos-surface"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle
              className={`h-4 w-4 ${killswitch.frozen ? "text-argos-danger" : "text-argos-fg-tertiary"}`}
              aria-hidden
            />
            <span className="font-mono text-xs text-argos-fg">Gel global de la flotte</span>
            <Badge tone={killswitch.frozen ? "danger" : "healthy"}>
              {killswitch.frozen ? "GELÉ" : "actif"}
            </Badge>
          </div>
          <Toggle
            enabled={killswitch.frozen}
            disabled={busy}
            onChange={(next) => act(() => setSreKillswitch(next, reason || undefined))}
            label="gel global"
          />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <TextInput
            label="Raison du gel"
            placeholder="ex. maintenance serveur"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {killswitch.updated_at && (
            <span className="font-mono text-[10px] text-argos-fg-disabled">
              maj {fmtDateTime(killswitch.updated_at)}
            </span>
          )}
        </div>
        <p className="font-mono text-[10px] text-argos-fg-disabled">
          Gel global ⇒ aucun script SRE ne tourne (cron + lancements manuels suspendus) jusqu'au
          dégel. À utiliser en cas d'incident ou de maintenance.
        </p>
      </div>

      {/* Gels ciblés par script */}
      <section className="flex flex-col gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
          Gels ciblés par script
        </h3>
        <ul className="flex flex-col gap-1.5">
          {scripts.map((s) => {
            const targeted = frozenSet.has(s.script);
            return (
              <li
                key={s.script}
                className="flex items-center justify-between gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-argos-fg">{s.script}</span>
                  {(targeted || killswitch.frozen) && (
                    <Badge tone="neutral">{killswitch.frozen ? "gel global" : "gelé"}</Badge>
                  )}
                </div>
                <Toggle
                  enabled={targeted}
                  disabled={busy || killswitch.frozen}
                  onChange={(next) => act(() => setSreKillswitchScript(s.script, next))}
                  label={`gel ${s.script}`}
                />
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
