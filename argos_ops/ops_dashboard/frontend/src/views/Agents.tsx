import { useCallback, useEffect, useState } from "react";
import type { AgentConfig, AgentRunRow, AgentSummary } from "../api";
import {
  fetchAgentConfig,
  fetchAgentRuns,
  fetchAgents,
  patchAgentConfig,
} from "../api";
import { Badge, Button, Flash, Slider, TextInput, Toggle } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import {
  formatAbsoluteTime,
  formatDuration,
  formatRelativeTime,
  statusBgColor,
  statusColor,
} from "../lib/format";

// Page Agents — table dense avec mutations P16.B inline :
// - Toggle ON/OFF (PATCH /api/agents/{name}/config { enabled })
// - Boutons Pause 1h / Pause 24h / Clear (PATCH paused_until)
// - Click row → drawer agent : section Config (slider intensity, daily_limit,
//   tier1_threshold, notes) + section Logs (50 derniers runs).

export function Agents() {
  const fetcher = useCallback((s?: AbortSignal) => fetchAgents(s), []);
  const { data: agents, error } = usePolling(fetcher);
  const [selected, setSelected] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ variant: "success" | "error"; msg: string } | null>(null);
  // Rerender trigger pour forcer un refresh après mutation.
  const [bumpKey, setBumpKey] = useState(0);

  const refetch = () => setBumpKey((k) => k + 1);

  return (
    <div className="p-6 space-y-4">
      {flash && (
        <Flash variant={flash.variant} message={flash.msg} onDismiss={() => setFlash(null)} />
      )}

      <div className="rounded-md border border-argos-border-subtle bg-argos-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-argos-surface-2/60 border-b border-argos-border-subtle">
              <Th>Agent</Th>
              <Th>Statut</Th>
              <Th>Dernière exécution</Th>
              <Th>Output</Th>
              <Th>Enabled</Th>
              <Th>Pause</Th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent) => (
              <AgentRow
                key={`${agent.name}-${bumpKey}`}
                agent={agent}
                onSelect={() => setSelected(agent.name)}
                selected={selected === agent.name}
                onFlash={setFlash}
                onMutated={refetch}
              />
            ))}
            {agents === null && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-argos-fg-tertiary">
                  Chargement…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {error && (
        <Flash variant="error" message={`Erreur API : ${error.message}`} />
      )}

      {selected && (
        <AgentDrawer
          agentName={selected}
          onClose={() => setSelected(null)}
          onFlash={setFlash}
          onMutated={refetch}
        />
      )}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left px-4 py-2.5 font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary font-medium">
      {children}
    </th>
  );
}

interface AgentRowProps {
  agent: AgentSummary;
  onSelect: () => void;
  selected: boolean;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function AgentRow({ agent, onSelect, selected, onFlash, onMutated }: AgentRowProps) {
  // Etat enabled local optimiste — re-synchronisé par le polling au cycle suivant.
  const [pending, setPending] = useState(false);
  // L'état `enabled` n'est pas dans AgentSummary du backend → on l'inférera à
  // partir d'un fetchAgentConfig séparé pour cette ligne. Pour éviter N+1 requêtes
  // dans la table on charge la config à la demande via le drawer ; ici on se
  // contente d'un toggle "trigger PATCH puis refetch" sans connaître l'état initial.
  // Cf. note dans App.tsx pour la roadmap (P16.B session 3 = embarquer enabled
  // directement dans /api/agents pour éviter ce shortcut).

  const handleToggle = async () => {
    setPending(true);
    try {
      const current = await fetchAgentConfig(agent.name);
      await patchAgentConfig(agent.name, { enabled: !current.enabled });
      onFlash({
        variant: "success",
        msg: `${agent.name} : ${current.enabled ? "désactivé" : "réactivé"}`,
      });
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `${agent.name} toggle : ${(e as Error).message}` });
    } finally {
      setPending(false);
    }
  };

  const handlePause = async (minutes: number | "clear") => {
    setPending(true);
    try {
      if (minutes === "clear") {
        await patchAgentConfig(agent.name, { clear_paused: true });
        onFlash({ variant: "success", msg: `${agent.name} : pause levée` });
      } else {
        const until = new Date(Date.now() + minutes * 60 * 1000).toISOString();
        await patchAgentConfig(agent.name, { paused_until: until });
        onFlash({
          variant: "success",
          msg: `${agent.name} : pause ${minutes === 60 ? "1h" : "24h"} active`,
        });
      }
      onMutated();
    } catch (e) {
      onFlash({ variant: "error", msg: `${agent.name} pause : ${(e as Error).message}` });
    } finally {
      setPending(false);
    }
  };

  return (
    <tr
      className={`border-b border-argos-border-subtle/60 hover:bg-argos-surface-2/40 transition-colors ${
        selected ? "bg-argos-surface-2/60" : ""
      }`}
    >
      <td className="px-4 py-3 font-medium text-argos-fg cursor-pointer" onClick={onSelect}>
        {agent.name}
      </td>
      <td className="px-4 py-3 cursor-pointer" onClick={onSelect}>
        <span
          className={`inline-flex items-center gap-1.5 font-mono text-xs ${statusColor(agent.last_run_status)}`}
        >
          <span
            className={`size-1.5 rounded-full ${
              agent.last_run_status === "success"
                ? "bg-argos-healthy"
                : agent.last_run_status === "failed"
                  ? "bg-argos-danger"
                  : agent.last_run_status === "killed_by_breaker"
                    ? "bg-argos-warning"
                    : agent.last_run_status?.startsWith("skipped_")
                      ? "bg-argos-info"
                      : "bg-argos-fg-disabled"
            }`}
          />
          {agent.last_run_status ?? "jamais"}
        </span>
        {agent.breaker_tripped && (
          <div className="mt-0.5">
            <Badge tone="danger">breaker</Badge>
          </div>
        )}
      </td>
      <td
        className="px-4 py-3 font-mono text-xs text-argos-fg-secondary cursor-pointer"
        onClick={onSelect}
      >
        {formatRelativeTime(agent.last_run_at)}
        <div className="text-argos-fg-tertiary">
          {formatDuration(agent.last_run_duration_seconds)}
        </div>
      </td>
      <td
        className="px-4 py-3 font-mono text-[11px] text-argos-fg-tertiary cursor-pointer truncate max-w-[320px]"
        onClick={onSelect}
      >
        {agent.last_run_output_summary ?? "—"}
      </td>
      <td className="px-4 py-3">
        <Toggle
          enabled={!agent.last_run_status?.startsWith("skipped_disabled")}
          onChange={handleToggle}
          disabled={pending}
          label={`Toggle ${agent.name}`}
        />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <Button size="sm" disabled={pending} onClick={() => handlePause(60)}>
            1h
          </Button>
          <Button size="sm" disabled={pending} onClick={() => handlePause(24 * 60)}>
            24h
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={pending}
            onClick={() => handlePause("clear")}
          >
            clear
          </Button>
        </div>
      </td>
    </tr>
  );
}

// =============================================================================
// Drawer : Config + Logs côte à côte
// =============================================================================
interface DrawerProps {
  agentName: string;
  onClose: () => void;
  onFlash: (flash: { variant: "success" | "error"; msg: string } | null) => void;
  onMutated: () => void;
}

function AgentDrawer({ agentName, onClose, onFlash, onMutated }: DrawerProps) {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [runs, setRuns] = useState<AgentRunRow[] | null>(null);
  const [configError, setConfigError] = useState<Error | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchAgentConfig(agentName, controller.signal).then(setConfig).catch((e) => {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setConfigError(e);
    });
    fetchAgentRuns(agentName, 50, controller.signal).then(setRuns).catch((e) => {
      if (e instanceof DOMException && e.name === "AbortError") return;
      // Erreur logs n'est pas critique, on l'ignore silencieusement (le user verra runs=null).
      console.warn(e);
    });
    return () => controller.abort();
  }, [agentName]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-20 flex">
      <div className="flex-1 bg-argos-bg/60" onClick={onClose} />
      <aside className="w-[720px] max-w-full bg-argos-surface border-l border-argos-border-subtle flex flex-col">
        <div className="px-5 py-4 border-b border-argos-border-subtle flex items-center justify-between">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary">
              Détails agent
            </div>
            <div className="text-base font-semibold text-argos-fg">{agentName}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs text-argos-fg-secondary hover:text-argos-fg px-2 py-1 rounded border border-argos-border-subtle hover:bg-argos-surface-2"
          >
            Esc
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <section>
            <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
              Config runtime
            </h3>
            {configError && (
              <Flash variant="error" message={`Config : ${configError.message}`} />
            )}
            {config === null && !configError && (
              <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
            )}
            {config && (
              <ConfigForm
                config={config}
                onSaved={(next) => {
                  setConfig(next);
                  onMutated();
                  onFlash({ variant: "success", msg: `${agentName} : config sauvegardée` });
                }}
                onError={(e) =>
                  onFlash({ variant: "error", msg: `${agentName} config : ${e.message}` })
                }
              />
            )}
          </section>

          <section>
            <h3 className="font-mono text-[11px] uppercase tracking-widest text-argos-fg-tertiary mb-3">
              50 derniers runs
            </h3>
            {runs === null && (
              <div className="text-sm text-argos-fg-tertiary">Chargement…</div>
            )}
            {runs?.length === 0 && (
              <div className="text-sm text-argos-fg-tertiary">Aucun run enregistré.</div>
            )}
            <div className="space-y-2">
              {runs?.map((run) => <RunCard key={run.id} run={run} />)}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

interface ConfigFormProps {
  config: AgentConfig;
  onSaved: (next: AgentConfig) => void;
  onError: (err: Error) => void;
}

function ConfigForm({ config, onSaved, onError }: ConfigFormProps) {
  const [intensity, setIntensity] = useState(config.intensity_level);
  const [dailyLimit, setDailyLimit] = useState(
    config.daily_limit === null ? "" : String(config.daily_limit),
  );
  const [tier1, setTier1] = useState(config.tier1_threshold);
  const [notes, setNotes] = useState(config.notes ?? "");
  const [saving, setSaving] = useState(false);

  const dirty =
    intensity !== config.intensity_level ||
    String(config.daily_limit ?? "") !== dailyLimit ||
    tier1 !== config.tier1_threshold ||
    (config.notes ?? "") !== notes;

  const handleSave = async () => {
    setSaving(true);
    try {
      const patched = await patchAgentConfig(config.agent_name, {
        intensity_level: intensity,
        daily_limit: dailyLimit === "" ? null : Number(dailyLimit),
        tier1_threshold: tier1,
        notes: notes || null,
      });
      onSaved(patched);
    } catch (e) {
      onError(e as Error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="font-mono text-[10px] uppercase tracking-widest text-argos-fg-tertiary">
            Intensity level
          </label>
          <span className="font-mono text-xs text-argos-fg">{intensity} / 10</span>
        </div>
        <Slider value={intensity} onValueChange={setIntensity} />
        <p className="mt-1 font-mono text-[10px] text-argos-fg-tertiary">
          1 = éco · 5 = défaut · 10 = max gourmand (scale interne aux agents)
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <TextInput
          label="Daily limit (vide = illimité)"
          type="number"
          min="0"
          value={dailyLimit}
          onChange={(e) => setDailyLimit(e.target.value)}
          placeholder="ex. 50"
        />
        <TextInput
          label="Tier 1 threshold (0-100)"
          type="number"
          min="0"
          max="100"
          value={String(tier1)}
          onChange={(e) => setTier1(Number(e.target.value))}
        />
      </div>

      <TextInput
        label="Notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="raison d'un état exceptionnel, contexte…"
      />

      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          {saving ? "Sauvegarde…" : "Sauvegarder"}
        </Button>
        {config.paused_until && (
          <Badge tone="warning">
            Paused until {formatAbsoluteTime(config.paused_until)}
          </Badge>
        )}
        <Badge tone={config.enabled ? "healthy" : "danger"}>
          {config.enabled ? "enabled" : "disabled"}
        </Badge>
      </div>
    </div>
  );
}

function RunCard({ run }: { run: AgentRunRow }) {
  return (
    <div className={`rounded-md border px-3 py-2.5 ${statusBgColor(run.status)}`}>
      <div className="flex items-center justify-between text-xs">
        <div className={`font-mono ${statusColor(run.status)}`}>
          #{run.id} · {run.status ?? "?"}
        </div>
        <div className="font-mono text-argos-fg-tertiary">
          {formatAbsoluteTime(run.started_at)} · {formatDuration(run.duration_seconds)}
        </div>
      </div>
      {run.output_summary && (
        <div className="mt-1.5 font-mono text-[11px] text-argos-fg-secondary break-words">
          {run.output_summary}
        </div>
      )}
      {run.error && (
        <div className="mt-1.5 font-mono text-[11px] text-argos-danger break-words">
          {run.error}
        </div>
      )}
    </div>
  );
}
