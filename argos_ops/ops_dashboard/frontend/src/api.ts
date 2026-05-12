// Client API du Admin Control Panel (P16.A). Wrappers fetch minimalistes
// vers le backend FastAPI ; les types TS reflètent les Pydantic schemas
// définis dans argos_ops/ops_dashboard/models.py (source de vérité côté
// Python). Si un schema change côté backend, mettre à jour ici manuellement.

export interface AgentSummary {
  name: string;
  last_run_status: "success" | "failed" | "killed_by_breaker" | null;
  last_run_at: string | null;
  last_run_duration_seconds: number | null;
  last_run_output_summary: string | null;
  last_run_error: string | null;
  breaker_tripped: boolean;
  breaker_reason: string | null;
}

export interface AgentRunRow {
  id: number;
  agent_name: string;
  command: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  status: "success" | "failed" | "killed_by_breaker" | null;
  output_summary: string | null;
  error: string | null;
  cost_estimate_eur: number | null;
}

export type BreakerSeverity = "critical" | "warning" | "info" | "unknown";

export interface BreakerInfo {
  name: string;
  tripped: boolean;
  tripped_at: string | null;
  reason: string | null;
  reset_after: string | null;
  severity: BreakerSeverity;
}

export interface KPIsOverview {
  mrr_eur: number;
  arr_eur: number;
  active_subscriptions: number;
  leads_last_24h: number;
  open_tickets: number;
  tripped_breakers: number;
  last_refreshed_at: string;
}

export interface HealthCheck {
  ok: boolean;
  service: string;
  version: string;
  timestamp: string;
}

// =============================================================================
// fetch helper
// =============================================================================
async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${path} → HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

// =============================================================================
// API endpoints
// =============================================================================
export function fetchHealth(signal?: AbortSignal): Promise<HealthCheck> {
  return getJSON<HealthCheck>("/api/health", signal);
}

export function fetchAgents(signal?: AbortSignal): Promise<AgentSummary[]> {
  return getJSON<AgentSummary[]>("/api/agents", signal);
}

export function fetchAgentRuns(
  name: string,
  limit = 50,
  signal?: AbortSignal,
): Promise<AgentRunRow[]> {
  return getJSON<AgentRunRow[]>(`/api/agents/${encodeURIComponent(name)}/runs?limit=${limit}`, signal);
}

export function fetchRuns(limit = 50, signal?: AbortSignal): Promise<AgentRunRow[]> {
  return getJSON<AgentRunRow[]>(`/api/runs?limit=${limit}`, signal);
}

export function fetchBreakers(signal?: AbortSignal): Promise<BreakerInfo[]> {
  return getJSON<BreakerInfo[]>("/api/breakers", signal);
}

export function fetchKPIs(signal?: AbortSignal): Promise<KPIsOverview> {
  return getJSON<KPIsOverview>("/api/kpis/overview", signal);
}
