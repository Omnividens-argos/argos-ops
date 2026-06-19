import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "./queryClient.ts";

// Canal temps réel du cockpit (refonte SF, Phase 5). Ouvre un WebSocket vers
// /api/ws/changes ; le backend pousse { type:"changed", pole } quand la mémoire
// d'un pôle change sur disque (runs, inbox, breakers, handoffs…). On invalide
// alors les clés React Query concernées (Home se rafraîchit tout seul) et on
// redispatch un événement DOM `argos:changed` que les pages pôle peuvent écouter
// pour recharger leur overview. Reconnexion auto (backoff) ; si le WS est
// indisponible, le polling React Query sert de fallback.

export type ChangeStreamStatus = "connecting" | "open" | "closed";

interface ChangeEvent {
  type: string;
  pole?: string;
}

/** Nom de l'événement DOM redispatché (les pages pôle peuvent l'écouter). */
export const CHANGE_EVENT = "argos:changed";

export function useChangeStream(): ChangeStreamStatus {
  const qc = useQueryClient();
  const [status, setStatus] = useState<ChangeStreamStatus>("connecting");
  const retryRef = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let disposed = false;
    let timer: number | undefined;

    function connect() {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      setStatus("connecting");
      try {
        ws = new WebSocket(`${proto}://${window.location.host}/api/ws/changes`);
      } catch {
        scheduleRetry();
        return;
      }
      ws.onopen = () => {
        retryRef.current = 0;
        setStatus("open");
      };
      ws.onmessage = (ev: MessageEvent<string>) => {
        let msg: ChangeEvent;
        try {
          msg = JSON.parse(ev.data) as ChangeEvent;
        } catch {
          return;
        }
        if (msg.type !== "changed") return;
        void qc.invalidateQueries({ queryKey: qk.home });
        void qc.invalidateQueries({ queryKey: qk.handoffsIncoming });
        if (msg.pole) void qc.invalidateQueries({ queryKey: qk.pole(msg.pole) });
        window.dispatchEvent(new CustomEvent<ChangeEvent>(CHANGE_EVENT, { detail: msg }));
      };
      ws.onclose = () => {
        setStatus("closed");
        scheduleRetry();
      };
      ws.onerror = () => {
        ws?.close();
      };
    }

    function scheduleRetry() {
      if (disposed) return;
      const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
      retryRef.current += 1;
      timer = window.setTimeout(connect, delay);
    }

    connect();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
      ws?.close();
    };
  }, [qc]);

  return status;
}
