import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Cpu,
  Eye,
  History,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Send,
  Square,
  Terminal,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  type AtelierSessionMeta,
  fetchAtelierSessions,
  fetchAtelierStatus,
  fetchAtelierTranscript,
} from "../api";
import { EmptyState } from "../components/EmptyState";
import { MarkdownPreview } from "../components/MarkdownPreview";
import { Badge, Button } from "../components/ui";
import { formatRelativeTime } from "../lib/format";

// Atelier libre v2 — Claude Code piloté depuis le panel via WebSocket full-duplex
// (cf. argos_ops/ops_dashboard/atelier.py). Local-only, flag OPS_ATELIER_ENABLED.
// v2 : historique des conversations (rouvrir + reprendre), rendu markdown,
// cartes d'outils repliables, layout dev-tool soigné (tokens argos-*).

type SessionStatus =
  | "loading"
  | "disabled"
  | "connecting"
  | "ready"
  | "running"
  | "stopped"
  | "error";

type PermissionMode = "read" | "fleet";

interface TranscriptItem {
  id: number;
  role: "user" | "assistant" | "tool" | "tool_result" | "error" | "result";
  text: string;
  name?: string;
}

interface AtelierEvent {
  kind: string;
  text?: string;
  name?: string;
  message?: string;
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
  const [sessions, setSessions] = useState<AtelierSessionMeta[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const wsRef = useRef<WebSocket | null>(null);
  const idRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const pinnedRef = useRef(true);

  const nextId = () => {
    idRef.current += 1;
    return idRef.current;
  };

  const refreshSessions = useCallback(() => {
    fetchAtelierSessions()
      .then(setSessions)
      .catch(() => undefined);
  }, []);

  const pushEvent = useCallback((ev: AtelierEvent) => {
    setItems((prev) => {
      if (ev.kind === "text" && ev.text) {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant") {
          return [...prev.slice(0, -1), { ...last, text: last.text + ev.text }];
        }
        return [...prev, { id: nextId(), role: "assistant", text: ev.text }];
      }
      if (ev.kind === "tool_use") {
        return [...prev, { id: nextId(), role: "tool", text: "", name: ev.name ?? "?" }];
      }
      if (ev.kind === "tool_result") {
        return [...prev, { id: nextId(), role: "tool_result", text: ev.text ?? "" }];
      }
      if (ev.kind === "error") {
        return [...prev, { id: nextId(), role: "error", text: ev.message ?? "Erreur" }];
      }
      if (ev.kind === "result" && ev.text) {
        return [...prev, { id: nextId(), role: "result", text: ev.text }];
      }
      return prev;
    });
  }, []);

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
      else if (msg.type === "turn_complete") {
        setStatus("ready");
        refreshSessions();
      } else if (msg.type === "event" && msg.event) pushEvent(msg.event);
    };
    ws.onclose = () => {
      wsRef.current = null;
      setStatus((s) => (s === "disabled" ? s : "stopped"));
    };
    ws.onerror = () => setStatus("error");
  }, [pushEvent, refreshSessions]);

  useEffect(() => {
    const controller = new AbortController();
    fetchAtelierStatus(controller.signal)
      .then((r) => {
        if (!r.enabled) {
          setStatus("disabled");
          return;
        }
        connect();
        refreshSessions();
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
  }, [connect, refreshSessions]);

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
    setActiveSession(null);
    connect();
  };

  const openSession = async (id: string) => {
    try {
      const { items: dto } = await fetchAtelierTranscript(id);
      setItems(dto.map((it) => ({ id: nextId(), role: it.role, text: it.text, name: it.name })));
      setActiveSession(id);
      // Reprend le contexte de cette conversation pour les prochains messages.
      wsRef.current?.send(JSON.stringify({ type: "resume", session_id: id }));
      pinnedRef.current = true;
    } catch {
      // silencieux : la session a pu être supprimée
    }
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
  if (status === "disabled") return <AtelierDisabled />;

  return (
    <div className="flex h-full">
      {sidebarOpen && (
        <SessionsSidebar
          sessions={sessions}
          activeSession={activeSession}
          onOpen={openSession}
          onNew={newSession}
          onCollapse={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex flex-col flex-1 min-w-0">
        <AtelierBar
          status={status}
          mode={mode}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onToggleMode={() => setMode((m) => (m === "read" ? "fleet" : "read"))}
          onNewSession={newSession}
          onInterrupt={interrupt}
        />

        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
        >
          {items.length === 0 && (
            <div className="text-argos-fg-tertiary text-center mt-10 font-mono text-[12px]">
              Session prête. Pose une question, ou demande une action à orchestrer sur la flotte.
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
            <div className="font-mono text-[12px] text-argos-fg-tertiary animate-pulse">
              ▍ Claude réfléchit…
            </div>
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
    </div>
  );
}

// =============================================================================
// Sidebar historique des conversations
// =============================================================================
function SessionsSidebar({
  sessions,
  activeSession,
  onOpen,
  onNew,
  onCollapse,
}: {
  sessions: AtelierSessionMeta[];
  activeSession: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  onCollapse: () => void;
}) {
  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-argos-border-subtle bg-argos-surface">
      <div className="flex items-center justify-between gap-1 px-3 py-2.5 border-b border-argos-border-subtle">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-widest text-argos-fg-tertiary min-w-0">
          <History size={12} strokeWidth={2} className="shrink-0" />
          Conversations
        </span>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onNew}
            title="Nouvelle conversation"
            className="inline-flex items-center gap-1 rounded-md border border-argos-border-subtle px-1.5 py-0.5 font-mono text-[10px] text-argos-fg-secondary hover:text-argos-fg hover:border-argos-border transition-colors"
          >
            <Plus size={10} strokeWidth={2} />
            neuve
          </button>
          <button
            type="button"
            onClick={onCollapse}
            title="Replier l'historique"
            className="inline-flex items-center justify-center rounded-md border border-argos-border-subtle p-1 text-argos-fg-tertiary hover:text-argos-fg hover:border-argos-border transition-colors"
          >
            <PanelLeftClose size={12} strokeWidth={2} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
        {sessions.length === 0 ? (
          <div className="font-mono text-[10px] text-argos-fg-tertiary p-2">
            Aucune conversation pour l'instant.
          </div>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onOpen(s.id)}
              className={`w-full text-left rounded-md px-2.5 py-1.5 transition-colors ${
                activeSession === s.id
                  ? "bg-argos-surface-2 text-argos-fg"
                  : "text-argos-fg-secondary hover:bg-argos-surface-2/60 hover:text-argos-fg"
              }`}
            >
              <div className="text-[12px] leading-snug line-clamp-2">{s.title}</div>
              <div className="font-mono text-[10px] text-argos-fg-tertiary mt-0.5">
                {formatRelativeTime(s.updated_at)}
              </div>
            </button>
          ))
        )}
      </div>
    </aside>
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
  sidebarOpen,
  onToggleSidebar,
  onToggleMode,
  onNewSession,
  onInterrupt,
}: {
  status: SessionStatus;
  mode: PermissionMode;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onToggleMode: () => void;
  onNewSession: () => void;
  onInterrupt: () => void;
}) {
  const meta = STATUS_META[status];
  return (
    <header className="flex items-center justify-between gap-3 border-b border-argos-border-subtle bg-argos-surface px-4 py-2.5 flex-wrap">
      <div className="flex items-center gap-2 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          title={sidebarOpen ? "Replier l'historique" : "Afficher l'historique"}
          className="hidden md:inline-flex items-center justify-center rounded-md border border-argos-border-subtle p-1 text-argos-fg-tertiary hover:text-argos-fg hover:border-argos-border transition-colors"
        >
          {sidebarOpen ? (
            <PanelLeftClose size={14} strokeWidth={2} />
          ) : (
            <PanelLeftOpen size={14} strokeWidth={2} />
          )}
        </button>
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
        <div className="text-[10px] font-mono uppercase tracking-widest text-argos-fg-tertiary mb-1">
          vous
        </div>
        <div className="text-[13px] text-argos-fg whitespace-pre-wrap break-words">{item.text}</div>
      </div>
    );
  }
  if (item.role === "assistant") {
    return (
      <div className="px-1 text-[13px] leading-relaxed">
        <MarkdownPreview content={item.text} />
      </div>
    );
  }
  if (item.role === "tool") {
    return (
      <div className="inline-flex items-center gap-1.5 rounded-md border border-argos-info/30 bg-argos-info/5 px-2.5 py-1 text-argos-info">
        <Wrench size={11} strokeWidth={2} />
        <span className="font-mono text-[11px]">{item.name ?? "outil"}</span>
      </div>
    );
  }
  if (item.role === "tool_result") {
    return <ToolResult text={item.text} />;
  }
  if (item.role === "error") {
    return (
      <div className="flex items-start gap-2 rounded-md border border-argos-danger/40 bg-argos-danger/5 px-3 py-2 text-argos-danger">
        <AlertTriangle size={13} strokeWidth={2} className="shrink-0 mt-0.5" />
        <div className="whitespace-pre-wrap break-words font-mono text-[11px]">{item.text}</div>
      </div>
    );
  }
  // result
  return (
    <div className="border-t border-argos-border-subtle pt-2 font-mono text-[10px] text-argos-fg-tertiary whitespace-pre-wrap break-words">
      {item.text}
    </div>
  );
}

function ToolResult({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  if (!text.trim()) return null;
  const chars = text.length;
  return (
    <div className="ml-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 font-mono text-[10px] text-argos-fg-tertiary hover:text-argos-fg transition-colors"
      >
        {open ? <ChevronDown size={11} strokeWidth={2} /> : <ChevronRight size={11} strokeWidth={2} />}
        résultat ({chars.toLocaleString("fr")} car.)
      </button>
      {open && (
        <pre className="mt-1 max-h-72 overflow-auto rounded-md border border-argos-border-subtle bg-argos-bg/60 p-2 font-mono text-[10px] text-argos-fg-secondary whitespace-pre-wrap break-words">
          {text}
        </pre>
      )}
    </div>
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
