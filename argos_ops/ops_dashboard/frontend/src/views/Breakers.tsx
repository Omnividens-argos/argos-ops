import { useCallback, useState } from "react";
import type { BreakerInfo } from "../api";
import { fetchBreakers, resetBreaker, tripBreaker } from "../api";
import { Badge, Button, Flash, TextInput } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatAbsoluteTime, formatRelativeTime } from "../lib/format";

// Page Breakers — liste des breakers tripped + actions trip/reset depuis le panel.
// Cf. ARGOS_OPS_PLAN.md § 16.2.3.

const SEVERITY_TONE: Record<BreakerInfo["severity"], "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  warning: "warning",
  info: "info",
  unknown: "neutral",
};

export function Breakers() {
  const fetcher = useCallback((s?: AbortSignal) => fetchBreakers(s), []);
  const { data, error, lastRefreshedAt } = usePolling(fetcher);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; msg: string } | null>(null);
  const [bumpKey, setBumpKey] = useState(0);
  const refetch = () => setBumpKey((k) => k + 1);

  return (
    <div className="p-6 space-y-4">
      {flash && (
        <Flash variant={flash.variant} message={flash.msg} onDismiss={() => setFlash(null)} />
      )}

      <TripBreakerForm
        onFlash={setFlash}
        onMutated={refetch}
      />

      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
          Breakers actuellement tripped {data && `(${data.length})`}
        </h2>
        {data === null && (
          <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
        )}
        {data?.length === 0 && (
          <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-6 text-center font-mono text-xs text-argos-fg-tertiary">
            Aucun breaker tripped. Système nominal.
          </div>
        )}
        <div className="space-y-2">
          {data?.map((breaker) => (
            <BreakerCard
              key={`${breaker.name}-${bumpKey}`}
              breaker={breaker}
              onFlash={setFlash}
              onMutated={refetch}
            />
          ))}
        </div>
      </section>

      {error && <Flash variant="error" message={`Erreur API : ${error.message}`} />}

      {lastRefreshedAt && (
        <div className="font-mono text-[10px] text-argos-fg-tertiary text-right">
          Refreshed {formatAbsoluteTime(lastRefreshedAt.toISOString())}
        </div>
      )}
    </div>
  );
}

interface TripFormProps {
  onFlash: (flash: { variant: "success" | "error"; msg: string }) => void;
  onMutated: () => void;
}

function TripBreakerForm({ onFlash, onMutated }: TripFormProps) {
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [severity, setSeverity] = useState<"critical" | "warning" | "info">("warning");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!name || !reason) {
      onFlash({ variant: "error", msg: "Name et reason requis pour trip" });
      return;
    }
    setSubmitting(true);
    try {
      await tripBreaker(name, { reason, severity });
      onFlash({ variant: "success", msg: `Breaker '${name}' tripped` });
      setName("");
      setReason("");
      setSeverity("warning");
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `Trip : ${(e as Error).message}` });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4">
      <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
        Trip manuel
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr_auto_auto] gap-3 items-end">
        <TextInput
          label="Breaker name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="ex. FinanceBot, weekend_kill"
        />
        <TextInput
          label="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="contexte (audité dans breakers.notes)"
        />
        <div className="flex flex-col gap-1">
          <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Severity
          </label>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as "critical" | "warning" | "info")}
            className="bg-argos-bg border border-argos-border-subtle rounded-md px-2.5 py-1.5 font-mono text-xs text-argos-fg focus:outline-none focus:border-argos-info/60"
          >
            <option value="warning">warning</option>
            <option value="critical">critical</option>
            <option value="info">info</option>
          </select>
        </div>
        <Button variant="danger" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "…" : "Trip"}
        </Button>
      </div>
      <p className="mt-2 font-mono text-[10px] text-argos-fg-tertiary">
        Le trip manuel passé ici n'envoie pas de notif Discord (le fondateur agit
        consciemment). Les agents trippent automatiquement via `breakers.trip_with_notification`.
      </p>
    </section>
  );
}

interface CardProps {
  breaker: BreakerInfo;
  onFlash: (flash: { variant: "success" | "error"; msg: string }) => void;
  onMutated: () => void;
}

function BreakerCard({ breaker, onFlash, onMutated }: CardProps) {
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    if (!window.confirm(`Reset le breaker '${breaker.name}' ?\n\nMotif initial : ${breaker.reason ?? "—"}`)) {
      return;
    }
    setResetting(true);
    try {
      await resetBreaker(breaker.name);
      onFlash({ variant: "success", msg: `Breaker '${breaker.name}' reseté` });
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `Reset : ${(e as Error).message}` });
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="rounded-md border border-argos-danger/30 bg-argos-surface p-4 flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-sm font-semibold text-argos-fg">{breaker.name}</span>
          <Badge tone={SEVERITY_TONE[breaker.severity]}>{breaker.severity}</Badge>
        </div>
        {breaker.reason && (
          <div className="font-mono text-xs text-argos-fg-secondary break-words">
            {breaker.reason}
          </div>
        )}
        <div className="mt-1.5 font-mono text-[10px] text-argos-fg-tertiary">
          Tripped {formatRelativeTime(breaker.tripped_at)}
          {breaker.reset_after && (
            <>
              {" · "}auto-reset à {formatAbsoluteTime(breaker.reset_after)}
            </>
          )}
        </div>
      </div>
      <Button variant="primary" onClick={handleReset} disabled={resetting}>
        {resetting ? "…" : "Reset"}
      </Button>
    </div>
  );
}
