import { QueryClient } from "@tanstack/react-query";

// Client React Query partagé du cockpit (refonte SF, D-017 local-first).
// Defaults orientés opérateur : stale-while-revalidate court (les /overview
// changent surtout à la mutation, qu'on invalide explicitement), pas de refetch
// au focus (le cockpit reste ouvert longtemps), 1 retry. Le temps réel
// (WS /api/ws/changes, Phase 5) invalidera les clés ; le polling React Query
// sert de fallback quand le WS est déconnecté.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Clés de cache centralisées — une racine par pôle/outil, pour invalider
// proprement après mutation (queryClient.invalidateQueries({ queryKey: qk.pole(id) })).
export const qk = {
  poles: ["poles"] as const,
  pole: (id: string) => ["pole", id] as const,
  home: ["home"] as const,
  handoffsIncoming: ["handoffs", "incoming"] as const,
};
