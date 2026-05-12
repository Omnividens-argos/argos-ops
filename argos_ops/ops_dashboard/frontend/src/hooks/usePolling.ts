import { useEffect, useState } from "react";

// Hook générique pour appeler un fetcher async périodiquement et exposer
// {data, error, loading, lastRefreshedAt}. Utilisé par toutes les vues
// du panel (Overview, Agents, Runs) avec une cadence /5s par défaut —
// largement assez pour un dashboard ops dont les agents tournent en cron
// /15min ou /jour. AbortController nettoie correctement à l'unmount et
// quand l'intervalle change.

export interface PollingState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  lastRefreshedAt: Date | null;
}

export function usePolling<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>,
  intervalMs = 5000,
): PollingState<T> {
  const [state, setState] = useState<PollingState<T>>({
    data: null,
    error: null,
    loading: true,
    lastRefreshedAt: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    const run = async () => {
      try {
        const data = await fetcher(controller.signal);
        if (!active) return;
        setState({ data, error: null, loading: false, lastRefreshedAt: new Date() });
      } catch (err) {
        if (!active || (err instanceof DOMException && err.name === "AbortError")) return;
        setState((prev) => ({ ...prev, error: err as Error, loading: false }));
      }
    };

    run();
    const id = window.setInterval(run, intervalMs);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(id);
    };
  }, [fetcher, intervalMs]);

  return state;
}
