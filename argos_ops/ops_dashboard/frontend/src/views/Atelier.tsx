import {
  AlertTriangle,
  Cpu,
  Eye,
  Plus,
  Send,
  Square,
  Terminal,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAtelierStatus } from "../api";
import { EmptyState } from "../components/EmptyState";
import { Badge, Button } from "../components/ui";

// Atelier libre embarqué — Claude Code piloté depuis le panel via WebSocket
// full-duplex (cf. argos_ops/ops_dashboard/atelier.py). Local-only, derrière
// le flag OPS_ATELIER_ENABLED. Aesthétique dev-tool / terminal (tokens argos-*).

type SessionStatus =
  | "loading" // appel /status en cours
  | "disabled" // OPS_ATELIER_ENABLED=false
  | "connecting" // WS en cours d'ouverture
  | "ready" // prêt à recevoir un message
  | "running" // un tour Claude est en cours
  | "stopped" // WS fermé / erreur transport
  | "error";

type PermissionMode = "read" | "fleet";

interface TranscriptItem {
  id: number;
  role: "user" | "assistant" | "tool" | "result" | "error";
  text: string;
}

// Event normalisé venant du backend (cf. atelier.normalize_event).
interface AtelierEvent {
  kind: string;
  text?: string;
  name?: string;
  message?: string;
  session_id?: string | null;
}

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/atelier/ws`;
}

export function Atelier() {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [items, setItems] = useState<TranscriptItem[]>([]);
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<PermissionMode>("read");

  const wsRef = useRef<WebSocket | null>(null);
  const idRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const pinnedRef = useRef(true); // autoscroll seulement si l'user est en bas

  const nextId = () => {
    idRef.current += 1;
    return idRef.current;
  };

  // — Réducteur d'items : les deltas de texte s'accumulent dans le dernier
  //   item assistant ; tout autre kind ouvre un nouvel item.
  const pushEvent = useCallback((ev: AtelierEvent) => {
    setItems((prev) => {
      if (ev.kind === "text" && ev.text) {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant") {
          const copy = prev.slice(0, -1);
          return [...copy, { ...last, text: last.text + ev.text }];
        }
        return [...prev, { id: nextId(), role: "assistant", text: ev.text }];
      }
      if (ev.kind === "tool_use") {
        return [...prev, { id: nextId(), role: "tool", text: ev.name ?? "?" }];
      }
      if (ev.kind === "error") {
        return [...prev, { id: nextId(), role: "error", text: ev.message ?? "Erreur" }];
      }
      if (ev.kind === "result" && ev.text) {
        return [...prev, { id: nextId(), role: "result", text: ev.text }];
      }
      return prev; // system / raw / turn_done : non rendus
    });
  }, []);

  // — Connexion WS (après confirmation que l'atelier est activé).
  const connect = useCallback(() => {
    setStatus("connecting");
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;
    ws.onmessage = (e) => {
      let msg: { type?: string; event?: AtelierEvent };
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg.type === "disabled") setStatus("disabled");
      else if (msg.type === "ready") setStatus("ready");
      else if (msg.type === "turn_complete") setStatus("ready");
      else if (msg.type === "event" && msg.event) pushEvent(msg.event);
    };
    ws.onclose = () => {
      wsRef.current = null;
      setStatus((s) => (s === "disabled" ? s : "stopped"));
    };
    ws.onerror = () => setStatus("error");
  }, [pushEvent]);

  useEffect(() => {
    const controller = new AbortController();
    fetchAtelierStatus(controller.signal)
      .then((r) => {
        if (!r.enabled) {
          setStatus("disabled");
          return;
        }
        connect();
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setStatus("error");
      });
    return () => {
      controller.abort();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  // — Autoscroll si l'utilisateur est resté en bas.
  useEffect(() => {
    if (pinnedRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [items]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  };

  const send = () => {
    const text = draft.trim();
    if (!text || status !== "ready" || !wsRef.current) return;
    setItems((prev) => [...prev, { id: nextId(), role: "user", text }]);
    wsRef.current.send(JSON.stringify({ type: "user", text, permission_mode: mode }));
    setDraft("");
    setStatus("running");
    pinnedRef.current = true;
  };

  const interrupt = () => {
    wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
    setStatus("ready");
  };

  const newSession = () => {
    wsRef.current?.close();
    setItems([]);
    connect();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  if (status === "loading") {
    return (
      <div className="p-6">
        <EmptyState tone="loading" title="Connexion à l'atelier…" />
      </div>
    );
  }

  if (status === "disabled") {
    return <AtelierDisabled />;
  }

  return (
    <div className="flex flex-col h-full">
      <AtelierBar
        status={status}
        mode={mode}
        onToggleMode={() => setMode((m) => (m === "read" ? "fleet" : "read"))}
        onNewSession={newSession}
        onInterrupt={interrupt}
      />

      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-3 font-mono text-[12px] leading-relaxed"
      >
        {items.length === 0 && (
          <div className="text-argos-fg-tertiary text-center mt-10">
            Session prête. Pose une question, ou demande une action à orchestrer
            sur la flotte.
            <br />
            <span className="text-[11px]">
              Mode {mode === "read" ? "lecture seule" : "pilotage flotte (lancer des bots)"} actif.
            </span>
          </div>
        )}
        {items.map((it) => (
          <TranscriptRow key={it.id} item={it} />
        ))}
        {status === "running" && (
          <div className="text-argos-fg-tertiary animate-pulse">▍ Claude réfléchit…</div>
        )}
      </div>

      <AtelierComposer
        draft={draft}
        setDraft={setDraft}
        onKeyDown={onKeyDown}
        onSend={send}
        onInterrupt={interrupt}
        status={status}
      />
    </div>
  );
}

// =============================================================================
// Barre de contrôle
// =============================================================================
const STATUS_META: Record<SessionStatus, { label: string; dot: string }> = {
  loading: { label: "chargement", dot: "bg-argos-fg-tertiary" },
  disabled: { label: "désactivé", dot: "bg-argos-fg-tertiary" },
  connecting: { label: "connexion", dot: "bg-argos-warning" },
  ready: { label: "prêt", dot: "bg-argos-healthy" },
  running: { label: "en cours", dot: "bg-argos-info animate-pulse" },
  stopped: { label: "fermé", dot: "bg-argos-fg-tertiary" },
  error: { label: "erreur", dot: "bg-argos-danger" },
};

function AtelierBar({
  status,
  mode,
  onToggleMode,
  onNewSession,
  onInterrupt,
}: {
  status: SessionStatus;
  mode: PermissionMode;
  onToggleMode: () => void;
  onNewSession: () => void;
  onInterrupt: () => void;
}) {
  const meta = STATUS_META[status];
  return (
    <header className="flex items-center justify-between gap-3 border-b border-argos-border-subtle bg-argos-surface px-4 py-2.5 flex-wrap">
      <div className="flex items-center gap-2 min-w-0">
        <Terminal size={15} strokeWidth={2} className="text-argos-fg-tertiary shrink-0" />
        <h1 className="text-sm font-semibold text-argos-fg">Atelier libre</h1>
        <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-argos-fg-tertiary">
          <span className={`size-2 rounded-full ${meta.dot}`} />
          {meta.label}
        </span>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={onToggleMode}
          disabled={status === "running"}
          title="Bascule lecture seule ↔ pilotage flotte (lancer des bots, lire leur mémoire)"
          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors disabled:opacity-50 ${
            mode === "fleet"
              ? "border-argos-warning/40 bg-argos-warning/10 text-argos-warning"
              : "border-argos-border-subtle bg-argos-surface text-argos-fg-secondary"
          }`}
        >
          {mode === "fleet" ? <Cpu size={11} strokeWidth={2} /> : <Eye size={11} strokeWidth={2} />}
          {mode === "fleet" ? "pilotage flotte" : "lecture seule"}
        </button>
        {status === "running" && (
          <Button size="sm" onClick={onInterrupt}>
            <span className="inline-flex items-center gap-1.5">
              <Square size={11} strokeWidth={2} />
              Stop
            </span>
          </Button>
        )}
        <Button size="sm" onClick={onNewSession} disabled={status === "running"}>
          <span className="inline-flex items-center gap-1.5">
            <Plus size={11} strokeWidth={2} />
            Nouvelle session
          </span>
        </Button>
      </div>
    </header>
  );
}

// =============================================================================
// Lignes du transcript
// =============================================================================
function TranscriptRow({ item }: { item: TranscriptItem }) {
  if (item.role === "user") {
    return (
      <div className="rounded-md border border-argos-border-subtle bg-argos-surface-2 px-3 py-2">
        <div className="text-[10px] uppercase tracking-widest text-argos-fg-tertiary mb-1">vous</div>
        <div className="text-argos-fg whitespace-pre-wrap break-words">{item.text}</div>
      </div>
    );
  }
  if (item.role === "tool") {
    return (
      <div className="inline-flex items-center gap-1.5 rounded-md border border-argos-info/30 bg-argos-info/5 px-2.5 py-1 text-argos-info">
        <Wrench size={11} strokeWidth={2} />
        <span className="text-[11px]">{item.text}</span>
      </div>
    );
  }
  if (item.role === "error") {
    return (
      <div className="flex items-start gap-2 rounded-md border border-argos-danger/40 bg-argos-danger/5 px-3 py-2 text-argos-danger">
        <AlertTriangle size={13} strokeWidth={2} className="shrink-0 mt-0.5" />
        <div className="whitespace-pre-wrap break-words text-[11px]">{item.text}</div>
      </div>
    );
  }
  if (item.role === "result") {
    return (
      <div className="border-t border-argos-border-subtle pt-2 text-[10px] text-argos-fg-tertiary whitespace-pre-wrap break-words">
        {item.text}
      </div>
    );
  }
  // assistant
  return (
    <div className="text-argos-fg whitespace-pre-wrap break-words">{item.text}</div>
  );
}

// =============================================================================
// Composer
// =============================================================================
function AtelierComposer({
  draft,
  setDraft,
  onKeyDown,
  onSend,
  onInterrupt,
  status,
}: {
  draft: string;
  setDraft: (v: string) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
  onInterrupt: () => void;
  status: SessionStatus;
}) {
  const running = status === "running";
  const canSend = status === "ready" && draft.trim().length > 0;
  return (
    <div className="border-t border-argos-border-subtle bg-argos-surface px-4 py-3">
      <div className="flex items-end gap-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          disabled={status !== "ready" && status !== "running"}
          placeholder={
            running
              ? "Claude travaille… (Stop pour interrompre)"
              : "Message à Claude — Entrée pour envoyer, Maj+Entrée pour un retour à la ligne"
          }
          className="flex-1 resize-y bg-argos-bg border border-argos-border-subtle rounded-md px-3 py-2 font-mono text-[12px] text-argos-fg placeholder:text-argos-fg-disabled focus:outline-none focus:border-argos-info/60 disabled:opacity-50"
        />
        {running ? (
          <Button variant="primary" size="sm" onClick={onInterrupt}>
            <span className="inline-flex items-center gap-1.5">
              <Square size={12} strokeWidth={2} />
              Stop
            </span>
          </Button>
        ) : (
          <Button variant="primary" size="sm" onClick={onSend} disabled={!canSend}>
            <span className="inline-flex items-center gap-1.5">
              <Send size={12} strokeWidth={2} />
              Envoyer
            </span>
          </Button>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// État désactivé (OPS_ATELIER_ENABLED=false)
// =============================================================================
function AtelierDisabled() {
  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="rounded-md border border-argos-border-subtle bg-argos-surface p-6">
        <div className="flex items-center gap-2 mb-3">
          <Terminal size={16} strokeWidth={2} className="text-argos-fg-tertiary" />
          <h1 className="text-base font-semibold text-argos-fg">Atelier libre — désactivé</h1>
          <Badge tone="neutral">local-only</Badge>
        </div>
        <p className="text-sm text-argos-fg-secondary leading-relaxed">
          L'atelier embarque un vrai Claude Code avec accès au repo : c'est de
          l'exécution de code par conception. Il est donc <strong>désactivé par
          défaut</strong> et ne doit tourner qu'en local, jamais exposé à distance.
        </p>
        <div className="mt-4 rounded-md bg-argos-bg border border-argos-border-subtle p-3 font-mono text-[11px] text-argos-fg-secondary">
          <div className="text-argos-fg-tertiary mb-1"># .env.local (poste du fondateur)</div>
          OPS_ATELIER_ENABLED=true
          <br />
          <span className="text-argos-fg-tertiary"># Claude Code doit être installé + loggué (abonnement Pro/Max)</span>
        </div>
        <p className="mt-3 font-mono text-[10px] text-argos-fg-tertiary">
          Relance ensuite le panel localement. Le moteur = CLI claude headless,
          aucune API tierce (D-017).
        </p>
      </div>
    </div>
  );
}
