// Onglet Console (IN → OUT) du détail bot — LE cœur du Cockpit.
// Découple GÉNÉRER (réversible, gratuit) de AGIR (irréversible). Split :
//   IN composable (cases à cocher) | OUT (réponse + verdict + Approve/Queue/Kill)
// Badge SHADOW/LIVE inratable. Moteur générer = atelier headless (WS).

import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Play,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ConsoleInResponse,
  type ConsoleStatus,
  type ConsoleVerdict,
  consoleAct,
  fetchConsoleIn,
  fetchConsoleStatus,
} from "../../api";
import { MarkdownPreview } from "../../components/MarkdownPreview";
import { useToast } from "../../components/Toast";
import { Badge, Button } from "../../components/ui";
import type { BotMetadata } from "../../lib/botMetadata";
import { SectionHeader } from "./shared";

interface Scores {
  factual: number;
  tone: number;
  legal: number;
  global: number;
}
type GenPhase = "idle" | "generating" | "verdict" | "parse_error" | "error";

interface GenState {
  phase: GenPhase;
  streaming: string;
  draft: string;
  verdict: ConsoleVerdict | null;
  scores: Scores | null;
  rationale: string;
  message: string;
}

const EMPTY_GEN: GenState = {
  phase: "idle",
  streaming: "",
  draft: "",
  verdict: null,
  scores: null,
  rationale: "",
  message: "",
};

// Classes littérales (Tailwind ne génère pas les classes construites dynamiquement).
const VERDICT_META: Record<
  ConsoleVerdict,
  { label: string; icon: typeof CheckCircle2; border: string; bg: string; text: string }
> = {
  auto_send: {
    label: "AUTO",
    icon: CheckCircle2,
    border: "border-argos-healthy/40",
    bg: "bg-argos-healthy/5",
    text: "text-argos-healthy",
  },
  queued: {
    label: "FILE",
    icon: Clock,
    border: "border-argos-warning/40",
    bg: "bg-argos-warning/5",
    text: "text-argos-warning",
  },
  killed: {
    label: "KILL",
    icon: XCircle,
    border: "border-argos-danger/40",
    bg: "bg-argos-danger/5",
    text: "text-argos-danger",
  },
};

const AXIS_CLS = (value: number): { text: string; bar: string } => {
  if (value >= 80) return { text: "text-argos-healthy", bar: "bg-argos-healthy" };
  if (value >= 50) return { text: "text-argos-warning", bar: "bg-argos-warning" };
  return { text: "text-argos-danger", bar: "bg-argos-danger" };
};

function consoleWsUrl(name: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/agents/${encodeURIComponent(name)}/console/generate`;
}

export function ConsoleTab({ botName, meta }: { botName: string; meta: BotMetadata }) {
  const toast = useToast();
  const [status, setStatus] = useState<ConsoleStatus | null>(null);
  const [inData, setInData] = useState<ConsoleInResponse | null>(null);

  // Cases du IN.
  const [ownMem, setOwnMem] = useState(true);
  const [accMem, setAccMem] = useState(true);
  const [useSkills, setUseSkills] = useState(true);
  const [useData, setUseData] = useState(true);

  const [task, setTask] = useState("");
  const [gen, setGen] = useState<GenState>(EMPTY_GEN);
  const [acting, setActing] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const c = new AbortController();
    fetchConsoleStatus(botName, c.signal).then(setStatus).catch(() => undefined);
    return () => c.abort();
  }, [botName]);

  // Compteurs du IN (mémoire) recomposés quand on coche/décoche.
  useEffect(() => {
    const c = new AbortController();
    fetchConsoleIn(botName, ownMem, accMem, c.signal).then(setInData).catch(() => undefined);
    return () => c.abort();
  }, [botName, ownMem, accMem]);

  useEffect(() => () => wsRef.current?.close(), []);

  const memSource = (key: string) => inData?.sources.find((s) => s.key === key);

  const generate = useCallback(() => {
    if (!task.trim() || !status?.engine_enabled) return;
    setGen({ ...EMPTY_GEN, phase: "generating" });
    const ws = new WebSocket(consoleWsUrl(botName));
    wsRef.current = ws;
    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "generate",
          task: task.trim(),
          own: ownMem,
          accessible: accMem,
          skills_on: useSkills,
          data_on: useData,
          skills: useSkills ? meta.skills ?? [] : [],
        }),
      );
    };
    ws.onmessage = (e) => {
      let m: {
        type?: string;
        text?: string;
        draft?: string;
        verdict?: ConsoleVerdict;
        scores?: Scores;
        rationale?: string;
        message?: string;
        raw?: string;
      };
      try {
        m = JSON.parse(e.data);
      } catch {
        return;
      }
      if (m.type === "disabled") {
        setGen({ ...EMPTY_GEN, phase: "error", message: "Moteur désactivé (OPS_ATELIER_ENABLED)." });
        ws.close();
      } else if (m.type === "delta") {
        setGen((g) => ({ ...g, streaming: g.streaming + (m.text ?? "") }));
      } else if (m.type === "verdict") {
        setGen((g) => ({
          ...g,
          phase: "verdict",
          draft: m.draft ?? "",
          verdict: m.verdict ?? null,
          scores: m.scores ?? null,
          rationale: m.rationale ?? "",
        }));
        ws.close();
      } else if (m.type === "parse_error") {
        setGen((g) => ({ ...g, phase: "parse_error", draft: m.raw ?? g.streaming, message: m.message ?? "" }));
        ws.close();
      } else if (m.type === "error") {
        setGen((g) => ({ ...g, phase: "error", message: m.message ?? "Erreur" }));
        ws.close();
      }
    };
    ws.onerror = () => setGen((g) => ({ ...g, phase: "error", message: "Connexion impossible." }));
  }, [botName, task, ownMem, accMem, useSkills, useData, meta.skills, status]);

  const act = async () => {
    if (!gen.verdict) return;
    if (status?.live) {
      const ok = window.confirm(
        "⚠️ Ce bot est en mode LIVE : « Agir » déclenche une action RÉELLE et irréversible. Continuer ?",
      );
      if (!ok) return;
    }
    setActing(true);
    try {
      const r = await consoleAct(botName, { verdict: gen.verdict, approved: true });
      if (r.acted) {
        toast.success(`Agi (${r.live ? "LIVE" : "shadow"}) — ${r.status ?? ""} ${r.output_summary ?? ""}`);
      } else {
        toast.error(`Refusé : ${r.reason ?? "gâchette"}`);
      }
    } catch (e) {
      toast.error(`Agir : ${(e as Error).message}`);
    } finally {
      setActing(false);
    }
  };

  const engineOff = status !== null && !status.engine_enabled;
  const canGenerate = !!status?.engine_enabled && task.trim().length > 0 && gen.phase !== "generating";

  return (
    <div className="space-y-4">
      {/* Bandeau : titre + SHADOW/LIVE */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <SectionHeader
          title="Console — générer puis agir"
          subtitle="générer = réversible · agir = irréversible (validation)"
          icon={Sparkles}
        />
        <ShadowLiveBadge live={!!status?.live} />
      </div>

      {engineOff && (
        <div className="rounded-md border border-argos-warning/40 bg-argos-warning/5 px-3 py-2 text-[12px] text-argos-warning flex items-start gap-2">
          <ShieldAlert size={14} strokeWidth={2} className="shrink-0 mt-0.5" />
          <div>
            Moteur de génération désactivé. Active <code className="font-mono">OPS_ATELIER_ENABLED=true</code> en
            local (même moteur que l'Atelier libre) pour générer.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-4 items-start">
        {/* ============ IN ============ */}
        <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4 space-y-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-argos-info">
            IN — ce qu'on donne à l'IA
          </div>
          <Check label="Mémoire du bot" count={memSource("own_memory")?.count} on={ownMem} set={setOwnMem} />
          <Check
            label="Mémoire accessible (graphe)"
            count={memSource("accessible_memory")?.count}
            detail={memSource("accessible_memory")?.detail}
            on={accMem}
            set={setAccMem}
          />
          <Check label="Skills" detail={(meta.skills ?? []).join(", ") || "aucun"} on={useSkills} set={setUseSkills} />
          <Check label="Données (config · KB · runs)" on={useData} set={setUseData} />

          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            placeholder="Consigne — ex. « Réponds au lead Acme qui demande un devis »"
            className="w-full resize-y bg-argos-bg border border-argos-border-subtle rounded-md px-3 py-2 font-mono text-[12px] text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60"
          />
          <Button variant="primary" onClick={generate} disabled={!canGenerate}>
            <span className="inline-flex items-center gap-1.5">
              <Cpu size={13} strokeWidth={2} />
              {gen.phase === "generating" ? "Génération…" : "Générer (réversible)"}
            </span>
          </Button>
          <p className="font-mono text-[10px] text-argos-fg-tertiary">
            Gratuit, ne déclenche rien. {inData ? `Contexte ≈ ${inData.context_chars} car.` : ""}
          </p>
        </section>

        {/* ============ OUT ============ */}
        <section className="rounded-md border border-argos-border-subtle bg-argos-surface p-4 space-y-3 min-h-[200px]">
          <div className="font-mono text-[10px] uppercase tracking-widest text-argos-healthy">
            OUT — ce que l'IA rend
          </div>

          {gen.phase === "idle" && (
            <div className="text-argos-fg-tertiary font-mono text-[12px] text-center py-10">
              Compose le IN, écris la consigne, puis « Générer ».
            </div>
          )}

          {gen.phase === "generating" && (
            <div className="font-mono text-[12px] text-argos-fg-secondary whitespace-pre-wrap break-words">
              {gen.streaming || "▍ génération en cours…"}
            </div>
          )}

          {gen.phase === "error" && (
            <div className="flex items-start gap-2 rounded-md border border-argos-danger/40 bg-argos-danger/5 px-3 py-2 text-argos-danger">
              <AlertTriangle size={14} strokeWidth={2} className="shrink-0 mt-0.5" />
              <span className="font-mono text-[11px] break-words">{gen.message}</span>
            </div>
          )}

          {(gen.phase === "verdict" || gen.phase === "parse_error") && (
            <>
              {gen.verdict && gen.scores && <VerdictCard verdict={gen.verdict} scores={gen.scores} rationale={gen.rationale} />}
              {gen.phase === "parse_error" && (
                <div className="font-mono text-[10px] text-argos-warning">
                  Verdict non parsable ({gen.message}) — brut affiché ci-dessous.
                </div>
              )}
              <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 p-3 text-[13px] leading-relaxed max-h-[420px] overflow-auto">
                <MarkdownPreview content={gen.draft} />
              </div>
              <ActionRow
                verdict={gen.verdict}
                live={!!status?.live}
                acting={acting}
                disabledAct={gen.verdict === "killed" || !gen.verdict}
                onAct={act}
                onReset={() => setGen(EMPTY_GEN)}
              />
            </>
          )}
        </section>
      </div>
    </div>
  );
}

// =============================================================================
function Check({
  label,
  count,
  detail,
  on,
  set,
}: {
  label: string;
  count?: number;
  detail?: string;
  on: boolean;
  set: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={on}
        onChange={(e) => set(e.target.checked)}
        className="mt-0.5 accent-argos-info"
      />
      <span className="min-w-0">
        <span className="text-[12px] text-argos-fg">{label}</span>
        {count !== undefined && <Badge tone="neutral">{count}</Badge>}
        {detail && <span className="block font-mono text-[10px] text-argos-fg-tertiary truncate">{detail}</span>}
      </span>
    </label>
  );
}

function ShadowLiveBadge({ live }: { live: boolean }) {
  return live ? (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-argos-danger bg-argos-danger/10 px-2.5 py-1 font-mono text-[11px] font-semibold text-argos-danger">
      <ShieldAlert size={12} strokeWidth={2} />
      LIVE — actions réelles
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-argos-warning/40 bg-argos-warning/10 px-2.5 py-1 font-mono text-[11px] text-argos-warning">
      ⬤ SHADOW — rien ne part
    </span>
  );
}

function VerdictCard({
  verdict,
  scores,
  rationale,
}: {
  verdict: ConsoleVerdict;
  scores: Scores;
  rationale: string;
}) {
  const m = VERDICT_META[verdict];
  const Icon = m.icon;
  return (
    <div className={`rounded-md border ${m.border} ${m.bg} p-3`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className={`inline-flex items-center gap-1.5 font-mono text-[12px] font-semibold ${m.text}`}>
          <Icon size={14} strokeWidth={2} />
          {m.label}
        </span>
        <span className="font-mono text-[12px] text-argos-fg">
          global <span className="font-semibold">{scores.global}</span>/100
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <Axis label="factual" value={scores.factual} />
        <Axis label="tone" value={scores.tone} />
        <Axis label="legal" value={scores.legal} />
      </div>
      {rationale && <p className="text-[11px] text-argos-fg-secondary leading-relaxed">{rationale}</p>}
    </div>
  );
}

function Axis({ label, value }: { label: string; value: number }) {
  const cls = AXIS_CLS(value);
  return (
    <div>
      <div className="flex items-center justify-between font-mono text-[10px] text-argos-fg-tertiary">
        <span>{label}</span>
        <span className={cls.text}>{value}</span>
      </div>
      <div className="h-1 rounded bg-argos-bg overflow-hidden">
        <div className={`h-full ${cls.bar}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function ActionRow({
  verdict,
  live,
  acting,
  disabledAct,
  onAct,
  onReset,
}: {
  verdict: ConsoleVerdict | null;
  live: boolean;
  acting: boolean;
  disabledAct: boolean;
  onAct: () => void;
  onReset: () => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap pt-1">
      <Button variant="primary" onClick={onAct} disabled={disabledAct || acting}>
        <span className="inline-flex items-center gap-1.5">
          <Play size={12} strokeWidth={2} />
          {acting ? "Action…" : `Approuver + Agir${live ? " (LIVE)" : ""}`}
        </span>
      </Button>
      <Button size="sm" onClick={onReset}>
        Nouvelle génération
      </Button>
      {verdict === "killed" && (
        <span className="font-mono text-[10px] text-argos-danger">
          bloqué par le juge (verdict killed)
        </span>
      )}
    </div>
  );
}
