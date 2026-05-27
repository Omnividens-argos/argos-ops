import { CheckCircle2, Info, TriangleAlert, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

// Toast non-modal — stacké en bas à droite, auto-dismiss après ~3.5 s.
// Pattern : useToast() retourne { push } qu'on appelle depuis n'importe quel
// composant pour notifier sans pousser le layout (vs Flash qui prend de la
// place dans le flux).

type ToastTone = "success" | "error" | "warning" | "info";

interface ToastEntry {
  id: number;
  tone: ToastTone;
  message: string;
  /** Si défini, l'utilisateur peut click une action (ex. « Annuler »). */
  action?: { label: string; onClick: () => void };
}

interface ToastApi {
  push: (entry: Omit<ToastEntry, "id">) => void;
  success: (message: string, action?: ToastEntry["action"]) => void;
  error: (message: string, action?: ToastEntry["action"]) => void;
  warning: (message: string, action?: ToastEntry["action"]) => void;
  info: (message: string, action?: ToastEntry["action"]) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

// Durée d'affichage par tone : les erreurs restent plus longtemps pour être lues.
const TIMEOUT_MS: Record<ToastTone, number> = {
  success: 3500,
  info: 3500,
  warning: 5000,
  error: 7000,
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const counterRef = useRef(0);
  const timersRef = useRef<Map<number, number>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const handle = timersRef.current.get(id);
    if (handle !== undefined) {
      window.clearTimeout(handle);
      timersRef.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (entry: Omit<ToastEntry, "id">) => {
      counterRef.current += 1;
      const id = counterRef.current;
      const full: ToastEntry = { ...entry, id };
      setToasts((prev) => [...prev, full]);
      const handle = window.setTimeout(() => dismiss(id), TIMEOUT_MS[entry.tone]);
      timersRef.current.set(id, handle);
    },
    [dismiss],
  );

  const api: ToastApi = {
    push,
    success: (message, action) => push({ tone: "success", message, action }),
    error: (message, action) => push({ tone: "error", message, action }),
    warning: (message, action) => push({ tone: "warning", message, action }),
    info: (message, action) => push({ tone: "info", message, action }),
  };

  // Cleanup timers à l'unmount.
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const handle of timers.values()) window.clearTimeout(handle);
      timers.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast doit être utilisé à l'intérieur d'un <ToastProvider>");
  }
  return ctx;
}

// =============================================================================
// Viewport — stack en bas à droite, fixed, z-50 (au-dessus de palette + modals).
// =============================================================================
function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastEntry[];
  onDismiss: (id: number) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div
      className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm w-[calc(100%-2rem)] sm:w-96 pointer-events-none"
      role="region"
      aria-label="Notifications"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastEntry;
  onDismiss: () => void;
}) {
  const palette: Record<
    ToastTone,
    { border: string; bg: string; iconColor: string; icon: typeof CheckCircle2 }
  > = {
    success: {
      border: "border-argos-healthy/40",
      bg: "bg-argos-healthy/10",
      iconColor: "text-argos-healthy",
      icon: CheckCircle2,
    },
    error: {
      border: "border-argos-danger/40",
      bg: "bg-argos-danger/10",
      iconColor: "text-argos-danger",
      icon: XCircle,
    },
    warning: {
      border: "border-argos-warning/40",
      bg: "bg-argos-warning/10",
      iconColor: "text-argos-warning",
      icon: TriangleAlert,
    },
    info: {
      border: "border-argos-info/40",
      bg: "bg-argos-info/10",
      iconColor: "text-argos-info",
      icon: Info,
    },
  };
  const p = palette[toast.tone];
  const Icon = p.icon;
  return (
    <div
      className={`argos-toast-enter pointer-events-auto rounded-md border ${p.border} ${p.bg} bg-argos-surface shadow-lg px-3 py-2.5 flex items-start gap-2`}
      role="status"
    >
      <Icon size={14} strokeWidth={2} className={`shrink-0 mt-0.5 ${p.iconColor}`} />
      <div className="flex-1 min-w-0 text-xs text-argos-fg leading-relaxed">
        {toast.message}
      </div>
      {toast.action && (
        <button
          type="button"
          onClick={() => {
            toast.action!.onClick();
            onDismiss();
          }}
          className="shrink-0 font-mono text-[10px] text-argos-info hover:underline"
        >
          {toast.action.label}
        </button>
      )}
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 text-argos-fg-tertiary hover:text-argos-fg"
        aria-label="Fermer"
      >
        <X size={12} strokeWidth={2} />
      </button>
    </div>
  );
}
