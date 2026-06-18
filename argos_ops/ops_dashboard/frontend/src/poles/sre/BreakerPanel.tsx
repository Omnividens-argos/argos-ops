// Panneau des circuit breakers SRE (archi v2, S8) — liste l'état latch de chaque
// breaker, permet le reset (désarmement humain) et l'armement manuel pour test.

import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { type SreBreaker, resetSreBreaker, tripSreBreaker } from "../api.ts";
import { Badge, Button, Flash, TextInput } from "../../components/ui.tsx";
import { fmtAge, fmtDateTime } from "./lib.ts";

export function BreakerPanel({
  breakers,
  onChanged,
}: {
  breakers: SreBreaker[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newReason, setNewReason] = useState("");

  async function act(fn: () => Promise<unknown>, key: string) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "échec");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Flash variant="error" message={error} onDismiss={() => setError(null)} />}

      {breakers.length === 0 ? (
        <div className="rounded-md border border-dashed border-argos-border-subtle bg-argos-surface px-4 py-6 text-center font-mono text-[11px] text-argos-fg-tertiary">
          Aucun breaker enregistré.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {breakers.map((b) => (
            <li
              key={b.name}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-2.5"
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-argos-fg">{b.name}</span>
                  <Badge tone={b.tripped ? "danger" : "healthy"}>
                    {b.tripped ? "armé" : "désarmé"}
                  </Badge>
                  {b.tripped && b.age_hours !== null && (
                    <span className="font-mono text-[10px] text-argos-fg-tertiary">
                      depuis {fmtAge(b.age_hours)}
                    </span>
                  )}
                </div>
                {b.reason && (
                  <span className="font-mono text-[10px] text-argos-fg-disabled">
                    {b.reason} · {fmtDateTime(b.tripped_at)}
                  </span>
                )}
              </div>
              {b.tripped && (
                <Button
                  size="sm"
                  variant="danger"
                  disabled={busy !== null}
                  onClick={() => act(() => resetSreBreaker(b.name), b.name)}
                >
                  <RotateCcw className="mr-1 inline h-3 w-3" aria-hidden /> reset
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Armement manuel (test / simulation d'incident). */}
      <div className="flex flex-wrap items-end gap-2 rounded-md border border-argos-border-subtle bg-argos-surface px-3 py-3">
        <TextInput
          label="Armer un breaker"
          placeholder="nom"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <TextInput
          label="Raison"
          placeholder="raison"
          value={newReason}
          onChange={(e) => setNewReason(e.target.value)}
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={busy !== null || !newName.trim()}
          onClick={() =>
            act(async () => {
              await tripSreBreaker(newName.trim(), newReason.trim() || "armé via cockpit");
              setNewName("");
              setNewReason("");
            }, "trip")
          }
        >
          armer
        </Button>
      </div>
    </div>
  );
}
