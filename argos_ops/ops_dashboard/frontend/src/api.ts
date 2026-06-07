// Client API du Admin Control Panel (P16.A). Wrappers fetch minimalistes
// vers le backend FastAPI ; les types TS reflètent les Pydantic schemas
// définis dans argos_ops/ops_dashboard/models.py (source de vérité côté
// Python). Si un schema change côté backend, mettre à jour ici manuellement.

export type RunStatus =
  | "success"
  | "failed"
  | "killed_by_breaker"
  | "skipped_disabled"
  | "skipped_paused"
  | "skipped_daily_limit";

export interface AgentSummary {
  name: string;
  last_run_status: RunStatus | null;
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
  status: RunStatus | null;
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
// Mutations P16.B
// =============================================================================
export interface AgentConfig {
  agent_name: string;
  enabled: boolean;
  intensity_level: number;
  schedule_cron: string | null;
  daily_limit: number | null;
  max_tokens_per_day: number | null;
  tier1_threshold: number;
  paused_until: string | null;
  notes: string | null;
  updated_at: string;
  updated_by: string | null;
}

export interface AgentConfigPatch {
  enabled?: boolean;
  intensity_level?: number;
  schedule_cron?: string | null;
  daily_limit?: number | null;
  max_tokens_per_day?: number | null;
  tier1_threshold?: number;
  paused_until?: string | null;
  notes?: string | null;
  clear_paused?: boolean;
}

export interface TripBreakerPayload {
  reason: string;
  severity?: "critical" | "warning" | "info";
}

export interface ManualRunResponse {
  agent_name: string;
  triggered_at: string;
  status: string;
  output_summary: string | null;
  error: string | null;
}

// =============================================================================
// Inbox (Phase 1) — drafts en attente de validation humaine
// =============================================================================
export type InboxKind =
  | "email"
  | "social"
  | "proposal"
  | "seo"
  | "press"
  | "doc"
  | "other";

export interface InboxDraft {
  id: string;
  kind: InboxKind;
  title: string;
  summary: string | null;
  status: string;
  created_at: string;
  file_path: string;
  agent_name: string | null;
}

export interface InboxActionPayload {
  note?: string | null;
  reason?: string | null;
}

export interface InboxActionResponse {
  id: string;
  status: string;
  file_path: string;
  timestamp: string;
}

export interface YamlConfigResponse {
  agent_name: string;
  relative_path: string;
  exists: boolean;
  content: string;
  last_modified: string | null;
}

export interface CashSubBreakdown {
  active: number;
  trialing: number;
  past_due: number;
  canceled: number;
  other: number;
}

export interface CashTicketBreakdown {
  p0: number;
  p1: number;
  p2: number;
  other: number;
}

export interface CashSnapshot {
  mrr_eur: number;
  arr_eur: number;
  active_subscriptions: number;
  subs_breakdown: CashSubBreakdown;
  leads_last_24h: number;
  leads_last_7d: number;
  leads_last_30d: number;
  open_tickets: number;
  tickets_breakdown: CashTicketBreakdown;
  last_refreshed_at: string;
}

export interface HealthAgentBreakdown {
  enabled: number;
  disabled: number;
  paused: number;
}

export interface PipelineDeal {
  deal_id: string;
  company: string;
  stage: string;
  amount_eur: number | null;
  last_activity_at: string | null;
  days_since_activity: number | null;
  owner: string | null;
  notes: string | null;
  risk_level: "healthy" | "stalled" | "at_risk";
}

export interface PipelineSnapshot {
  has_data: boolean;
  file_path: string;
  total_deals: number;
  total_amount_eur: number;
  deals: PipelineDeal[];
  last_refreshed_at: string;
}

export interface CohortRow {
  signup_month: string;
  cohort_size: number;
  retained_by_month: number[];
}

export interface CohortsResponse {
  has_data: boolean;
  months_tracked: number;
  rows: CohortRow[];
  last_refreshed_at: string;
}

export interface HealthSnapshot {
  db_ok: boolean;
  runs_last_24h: number;
  runs_last_7d: number;
  failed_last_24h: number;
  failed_last_7d: number;
  agents_breakdown: HealthAgentBreakdown;
  tripped_breakers: number;
  tripped_breaker_names: string[];
  last_refreshed_at: string;
}

export interface AgentPerfStats {
  agent_name: string;
  window_days: number;
  total_runs: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  error_rate: number;
  avg_duration_seconds: number | null;
  p50_duration_seconds: number | null;
  p95_duration_seconds: number | null;
}

// =============================================================================
// Mémoire de flotte — Cockpit Console (LOT 2)
// =============================================================================
export interface FactRow {
  id: string;
  bot: string;
  kind: string;
  body: string;
  source: string | null;
  confidence: string;
  status: string;
  ttl_days: number | null;
  created_at: string;
  archived_at: string | null;
  tags: string[];
}

export interface VisibleBotMemory {
  bot: string;
  facts: FactRow[];
}

export interface BotMemoryView {
  bot: string;
  own: FactRow[];
  visible: VisibleBotMemory[];
  reads: string[];
  read_by: string[];
}

export interface FactCreatePayload {
  body: string;
  kind?: string;
  source?: string | null;
  confidence?: "low" | "medium" | "high";
  tags?: string[];
  ttl_days?: number | null;
}

// =============================================================================
// fetch helpers
// =============================================================================
async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${path} → HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

async function sendJSON<T>(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${method} ${path} → HTTP ${response.status} ${detail.slice(0, 200)}`);
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

// =============================================================================
// Mutations P16.B
// =============================================================================
export function fetchAgentConfig(name: string, signal?: AbortSignal): Promise<AgentConfig> {
  return getJSON<AgentConfig>(`/api/agents/${encodeURIComponent(name)}/config`, signal);
}

export function patchAgentConfig(name: string, patch: AgentConfigPatch): Promise<AgentConfig> {
  return sendJSON<AgentConfig>("PATCH", `/api/agents/${encodeURIComponent(name)}/config`, patch);
}

export function tripBreaker(name: string, payload: TripBreakerPayload): Promise<BreakerInfo> {
  return sendJSON<BreakerInfo>("POST", `/api/breakers/${encodeURIComponent(name)}/trip`, payload);
}

export function resetBreaker(name: string): Promise<BreakerInfo> {
  return sendJSON<BreakerInfo>("POST", `/api/breakers/${encodeURIComponent(name)}/reset`);
}

export function runAgentNow(name: string): Promise<ManualRunResponse> {
  return sendJSON<ManualRunResponse>("POST", `/api/agents/${encodeURIComponent(name)}/runs`);
}

// =============================================================================
// Atelier libre embarqué (Cockpit)
// =============================================================================
export function fetchAtelierStatus(signal?: AbortSignal): Promise<{ enabled: boolean }> {
  return getJSON<{ enabled: boolean }>("/api/atelier/status", signal);
}

// =============================================================================
// Mémoire de flotte — Cockpit Console (LOT 2)
// =============================================================================
export function fetchAgentMemory(
  name: string,
  signal?: AbortSignal,
): Promise<BotMemoryView> {
  return getJSON<BotMemoryView>(`/api/agents/${encodeURIComponent(name)}/memory`, signal);
}

export function appendAgentFact(name: string, payload: FactCreatePayload): Promise<FactRow> {
  return sendJSON<FactRow>("POST", `/api/agents/${encodeURIComponent(name)}/memory`, payload);
}

export function archiveAgentFact(name: string, factId: string): Promise<FactRow> {
  return sendJSON<FactRow>(
    "POST",
    `/api/agents/${encodeURIComponent(name)}/memory/${encodeURIComponent(factId)}/archive`,
  );
}

export function fetchInboxDrafts(signal?: AbortSignal): Promise<InboxDraft[]> {
  return getJSON<InboxDraft[]>("/api/inbox/drafts", signal);
}

export interface OutputContentResponse {
  file_path: string;
  content: string;
}

export function fetchAllOutputs(signal?: AbortSignal): Promise<InboxDraft[]> {
  return getJSON<InboxDraft[]>("/api/outputs/index", signal);
}

export function fetchOutputContent(
  path: string,
  signal?: AbortSignal,
): Promise<OutputContentResponse> {
  return getJSON<OutputContentResponse>(
    `/api/outputs/content?path=${encodeURIComponent(path)}`,
    signal,
  );
}

export function validateInboxDraft(
  draftId: string,
  payload: InboxActionPayload = {},
): Promise<InboxActionResponse> {
  return sendJSON<InboxActionResponse>(
    "POST",
    `/api/inbox/drafts/validate?draft_id=${encodeURIComponent(draftId)}`,
    payload,
  );
}

export function rejectInboxDraft(
  draftId: string,
  payload: InboxActionPayload = {},
): Promise<InboxActionResponse> {
  return sendJSON<InboxActionResponse>(
    "POST",
    `/api/inbox/drafts/reject?draft_id=${encodeURIComponent(draftId)}`,
    payload,
  );
}

export function fetchAgentYamlConfig(
  name: string,
  signal?: AbortSignal,
): Promise<YamlConfigResponse> {
  return getJSON<YamlConfigResponse>(
    `/api/agents/${encodeURIComponent(name)}/config-yaml`,
    signal,
  );
}

export function patchAgentYamlConfig(
  name: string,
  content: string,
): Promise<YamlConfigResponse> {
  return sendJSON<YamlConfigResponse>(
    "PATCH",
    `/api/agents/${encodeURIComponent(name)}/config-yaml`,
    { content },
  );
}

export function fetchAgentPerf(
  name: string,
  windowDays = 7,
  signal?: AbortSignal,
): Promise<AgentPerfStats> {
  return getJSON<AgentPerfStats>(
    `/api/agents/${encodeURIComponent(name)}/perf?window_days=${windowDays}`,
    signal,
  );
}

export function fetchCashSnapshot(signal?: AbortSignal): Promise<CashSnapshot> {
  return getJSON<CashSnapshot>("/api/cash/snapshot", signal);
}

export function fetchHealthSnapshot(signal?: AbortSignal): Promise<HealthSnapshot> {
  return getJSON<HealthSnapshot>("/api/health/snapshot", signal);
}

export function fetchPipeline(signal?: AbortSignal): Promise<PipelineSnapshot> {
  return getJSON<PipelineSnapshot>("/api/sales/pipeline", signal);
}

export function fetchCohorts(months = 6, signal?: AbortSignal): Promise<CohortsResponse> {
  return getJSON<CohortsResponse>(`/api/cash/cohorts?months=${months}`, signal);
}
