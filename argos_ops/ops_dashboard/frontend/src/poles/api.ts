// Client API du shell archi v2 (poles.html) — isolé du legacy src/api.ts (les
// sessions pôle n'éditent que src/poles/**). Types = miroir des Pydantic schemas
// de argos_ops/ops_dashboard/api/poles.py (source de vérité côté Python).

export type Severity = "info" | "warning" | "critical";

export interface MemoryFact {
  id: string;
  pole: string;
  script: string;
  kind: string;
  important: boolean;
  tags: string[];
  body: string;
  source: string | null;
  created_at: string; // ISO 8601
}

export interface InsightOut {
  kind: string;
  title: string;
  theme: string;
  severity: Severity;
  summary: string;
  suggested_poles: string[];
  record_ids: string[];
  count: number;
}

export interface FeedCounts {
  total: number;
  important: number;
  critical: number;
}

export interface PoleFeed {
  pole: string;
  generated_at: string;
  records: MemoryFact[];
  insights: InsightOut[];
  kinds: string[];
  themes: string[];
  scripts: string[];
  counts: FeedCounts;
}

export interface HandoffOut {
  id: string;
  pole: string;
  record_id: string;
  target_pole: string;
  note: string | null;
  created_at: string;
}

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

async function sendJSON<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${method} ${path} -> HTTP ${res.status} ${detail.slice(0, 160)}`);
  }
  return (await res.json()) as T;
}

function postJSON<T>(path: string, body: unknown): Promise<T> {
  return sendJSON<T>("POST", path, body);
}

function putJSON<T>(path: string, body: unknown): Promise<T> {
  return sendJSON<T>("PUT", path, body);
}

async function deleteReq(path: string): Promise<void> {
  const res = await fetch(path, { method: "DELETE", headers: { Accept: "application/json" } });
  if (!res.ok && res.status !== 204) {
    const detail = await res.text();
    throw new Error(`DELETE ${path} -> HTTP ${res.status} ${detail.slice(0, 160)}`);
  }
}

export function fetchPoleFeed(pole: string, signal?: AbortSignal): Promise<PoleFeed> {
  return getJSON<PoleFeed>(`/api/poles/${encodeURIComponent(pole)}/feed`, signal);
}

export function pushHandoff(
  pole: string,
  payload: { record_id: string; target_pole: string; note?: string },
): Promise<HandoffOut> {
  return postJSON<HandoffOut>(`/api/poles/${encodeURIComponent(pole)}/handoff`, payload);
}

// =============================================================================
// Pôle Marketing (S2) — miroir des schemas Pydantic de api/marketing.py.
// =============================================================================
export type DraftStatus = "draft" | "validated" | "rejected" | "published";

export interface MarketingChannel {
  id: string;
  label: string;
  writer_skill: string;
  max_chars: number;
  min_chars: number;
  social: boolean;
}

export interface MarketingRecommendation {
  kind: string;
  topic: string;
  angle: string;
  severity: Severity;
  channels: string[];
  rationale: string;
  record_ids: string[];
  count: number;
}

export interface MarketingDraft {
  id: string;
  channel: string;
  title: string;
  body: string;
  status: DraftStatus;
  writer: string | null;
  source: string | null;
  scheduled_for: string | null;
  created_at: string;
  updated_at: string;
  length: number;
  max_chars: number;
  length_ok: boolean;
}

export interface MarketingEngagement {
  channel: string;
  posts: number;
  impressions: number;
  engagements: number;
  clicks: number;
  ctr: number;
  engagement_rate: number;
  weak: boolean;
}

export interface MarketingKBEntry {
  slug: string;
  title: string;
  body: string;
  tags: string[];
  updated_at: string;
}

export interface MarketingCharter {
  tagline: string;
  domain: string;
  voice: string;
  principles: string[];
  avoid: string[];
  banned_terms: string[];
  ai_disclosure: string;
}

export interface MarketingCounts {
  drafts: number;
  pending: number;
  validated: number;
  scheduled: number;
  published: number;
  recommendations: number;
  critical: number;
}

export interface MarketingOverview {
  pole: string;
  generated_at: string;
  channels: MarketingChannel[];
  recommendations: MarketingRecommendation[];
  drafts: MarketingDraft[];
  engagement: MarketingEngagement[];
  kb: MarketingKBEntry[];
  charter: MarketingCharter;
  counts: MarketingCounts;
}

const M = "/api/poles/marketing";

export function fetchMarketingOverview(signal?: AbortSignal): Promise<MarketingOverview> {
  return getJSON<MarketingOverview>(`${M}/overview`, signal);
}

export function createDraft(payload: {
  channel: string;
  title: string;
  body: string;
  writer?: string;
  source?: string;
}): Promise<MarketingDraft> {
  return postJSON<MarketingDraft>(`${M}/drafts`, payload);
}

export function editDraft(
  id: string,
  payload: { title?: string; body?: string },
): Promise<MarketingDraft> {
  return putJSON<MarketingDraft>(`${M}/drafts/${encodeURIComponent(id)}`, payload);
}

export function validateDraft(id: string): Promise<MarketingDraft> {
  return postJSON<MarketingDraft>(`${M}/drafts/${encodeURIComponent(id)}/validate`, {});
}

export function rejectDraft(id: string): Promise<MarketingDraft> {
  return postJSON<MarketingDraft>(`${M}/drafts/${encodeURIComponent(id)}/reject`, {});
}

export function scheduleDraft(
  id: string,
  scheduledFor: string | null,
): Promise<MarketingDraft> {
  return postJSON<MarketingDraft>(`${M}/drafts/${encodeURIComponent(id)}/schedule`, {
    scheduled_for: scheduledFor,
  });
}

export function upsertKB(
  slug: string,
  payload: { title: string; body: string; tags: string[] },
): Promise<MarketingKBEntry> {
  return putJSON<MarketingKBEntry>(`${M}/kb/${encodeURIComponent(slug)}`, payload);
}

export function deleteKB(slug: string): Promise<void> {
  return deleteReq(`${M}/kb/${encodeURIComponent(slug)}`);
}

export function saveCharter(charter: MarketingCharter): Promise<MarketingCharter> {
  return putJSON<MarketingCharter>(`${M}/charter`, charter);
}

// =============================================================================
// Pôle Pub (S3) — miroir des schemas Pydantic de api/pub.py.
// =============================================================================
export type CreativeStatus = "draft" | "validated" | "live" | "rejected";

export interface AdPlatform {
  id: string;
  label: string;
  creative_skill: string;
  headline_max: number;
  headline_count: number;
  primary_max: number;
  keyword_targeted: boolean;
}

export interface PubBudget {
  daily_budget_eur: number;
  runaway_multiplier: number;
  window_days: number;
  spent_per_day_eur: number;
  spent_window_eur: number;
  utilization: number;
  runaway_threshold_eur: number;
  over_threshold: boolean;
  by_platform: Record<string, number>;
  breaker_tripped: boolean;
  breaker_reason: string | null;
  breaker_tripped_at: string | null;
}

export interface AdRecommendation {
  id: string;
  platform: string;
  campaign: string;
  action: string;
  severity: Severity;
  eur_delta_week: number;
  rationale: string;
  metrics: Record<string, number>;
  spend_increasing: boolean;
  applied: boolean;
  blocked_by_breaker: boolean;
}

export interface AdCampaign {
  platform: string;
  campaign: string;
  impressions: number;
  clicks: number;
  cost_eur: number;
  conversions: number;
  ctr: number;
  cpc: number;
  cpa: number;
  conv_rate: number;
}

export interface CreativeVariant {
  label: string;
  angle: string;
  headline: string;
  primary_text: string;
  description: string;
  headline_len: number;
  headline_ok: boolean;
  primary_len: number;
  primary_ok: boolean;
}

export interface AdCreative {
  id: string;
  platform: string;
  title: string;
  status: CreativeStatus;
  objective: string | null;
  persona: string | null;
  source: string | null;
  brief: string;
  created_at: string;
  updated_at: string;
  variants: CreativeVariant[];
}

export interface PubCounts {
  creatives: number;
  draft: number;
  validated: number;
  live: number;
  rejected: number;
  recommendations: number;
  critical: number;
  applied: number;
  potential_savings_week_eur: number;
  potential_scale_week_eur: number;
}

export interface PubOverview {
  pole: string;
  generated_at: string;
  platforms: AdPlatform[];
  budget: PubBudget;
  recommendations: AdRecommendation[];
  campaigns: AdCampaign[];
  creatives: AdCreative[];
  counts: PubCounts;
}

export interface AppliedRecommendation {
  id: string;
  platform: string;
  campaign: string;
  action: string;
  eur_delta_week: number;
  rationale: string;
  mode: string;
  applied_at: string;
}

export interface SimAllocation {
  platform: string;
  daily_eur: number;
  cpa_eur: number;
  weekly_spend_eur: number;
  weekly_leads: number;
}

export interface Simulation {
  total_daily_eur: number;
  weekly_spend_eur: number;
  weekly_leads: number;
  blended_cpa_eur: number;
  exceeds_budget: boolean;
  would_trip: boolean;
  allocations: SimAllocation[];
}

const P = "/api/poles/pub";

export function fetchPubOverview(signal?: AbortSignal): Promise<PubOverview> {
  return getJSON<PubOverview>(`${P}/overview`, signal);
}

export function validateCreative(id: string): Promise<AdCreative> {
  return postJSON<AdCreative>(`${P}/creatives/${encodeURIComponent(id)}/validate`, {});
}

export function rejectCreative(id: string): Promise<AdCreative> {
  return postJSON<AdCreative>(`${P}/creatives/${encodeURIComponent(id)}/reject`, {});
}

export function goliveCreative(id: string): Promise<AdCreative> {
  return postJSON<AdCreative>(`${P}/creatives/${encodeURIComponent(id)}/golive`, {});
}

export function setPubBudget(dailyBudgetEur: number): Promise<PubBudget> {
  return putJSON<PubBudget>(`${P}/budget`, { daily_budget_eur: dailyBudgetEur });
}

export function resetPubBreaker(): Promise<PubBudget> {
  return postJSON<PubBudget>(`${P}/breaker/reset`, {});
}

export function applyRecommendation(payload: {
  platform: string;
  campaign: string;
  action: string;
  eur_delta_week: number;
  rationale: string;
}): Promise<AppliedRecommendation> {
  return postJSON<AppliedRecommendation>(`${P}/recommendations/apply`, payload);
}

export function simulatePubBudget(payload: {
  per_platform_daily: Record<string, number>;
  daily_budget_eur?: number;
}): Promise<Simulation> {
  return postJSON<Simulation>(`${P}/simulate`, payload);
}
