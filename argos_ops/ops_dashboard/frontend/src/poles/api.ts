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

async function sendJSON<T>(method: "POST" | "PUT" | "PATCH", path: string, body: unknown): Promise<T> {
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

function patchJSON<T>(path: string, body: unknown): Promise<T> {
  return sendJSON<T>("PATCH", path, body);
}

async function deleteReq(path: string): Promise<void> {
  const res = await fetch(path, { method: "DELETE", headers: { Accept: "application/json" } });
  if (!res.ok && res.status !== 204) {
    const detail = await res.text();
    throw new Error(`DELETE ${path} -> HTTP ${res.status} ${detail.slice(0, 160)}`);
  }
}

async function deleteJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: "DELETE", headers: { Accept: "application/json" } });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`DELETE ${path} -> HTTP ${res.status} ${detail.slice(0, 160)}`);
  }
  return (await res.json()) as T;
}

// =============================================================================
// Handoffs entrants (cross-pôle) — GET /api/poles/handoffs/incoming (Phase 6)
// =============================================================================
export interface IncomingHandoff {
  id: string;
  source_pole: string;
  record_id: string;
  target_pole: string;
  note: string | null;
  created_at: string;
}

export function fetchIncomingHandoffs(
  pole?: string,
  signal?: AbortSignal,
): Promise<IncomingHandoff[]> {
  const q = pole ? `?pole=${encodeURIComponent(pole)}` : "";
  return getJSON<IncomingHandoff[]>(`/api/poles/handoffs/incoming${q}`, signal);
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

// =============================================================================
// Pôle Vente & RC (S4) — miroir des schemas Pydantic de api/vente.py.
// =============================================================================
export interface VenteDeal {
  deal_id: string;
  company: string;
  stage: string;
  amount_eur: number;
  days_since_activity: number;
  risk_score: number;
  is_stalled: boolean;
  reason: string;
}

export interface VenteMessage {
  id: string;
  from_name: string;
  from_email: string;
  subject: string;
  category: string;
  human_requested: boolean;
  status: string;
  received_at: string;
}

export interface VenteHealth {
  customer_id: string;
  score: number;
  band: string;
  drivers: string[];
}

export interface VenteChurn {
  customer_id: string;
  risk_score: number;
  urgent: boolean;
  signals: string[];
}

export interface VenteUpsell {
  customer_id: string;
  usage_ratio: number;
  suggested_plan: string;
  reason: string;
}

export interface VenteTicket {
  ticket_id: string;
  customer_id: string;
  subject: string;
  priority: string;
  sla_response_hours: number;
  sla_breached: boolean;
  reason: string;
}

export interface VenteLead {
  slug: string;
  full_name: string;
  domain: string;
  title_hint: string | null;
  persona: string;
  bant_total: number;
  qualified: boolean;
  best_email: string | null;
  eligible: boolean;
  eligibility_reason: string;
}

export interface VenteTouch {
  step: number;
  scheduled_date: string;
  status: string;
}

export interface VenteSequence {
  slug: string;
  full_name: string;
  domain: string;
  sequence_status: string;
  touches: VenteTouch[];
}

export interface VenteMeeting {
  request_id: string;
  attendee_name: string;
  attendee_email: string;
  company: string;
  starts_at: string;
  duration_minutes: number;
  location: string;
  status: string;
}

export interface VenteProposal {
  deal_id: string;
  company: string;
  plan: string;
  monthly_price_eur: number;
  proposal_status: string;
  has_proposal: boolean;
  has_contract: boolean;
}

export interface VenteBloctel {
  list_path: string | null;
  list_age_days: number | null;
  checked: number;
  matches: number;
  stale: boolean;
  should_alert: boolean;
  summary: string;
}

export interface VenteCounts {
  deals_active: number;
  pipeline_value_eur: number;
  stalled: number;
  inbox_total: number;
  inbox_new: number;
  leads: number;
  qualified_leads: number;
  eligible_leads: number;
  tickets_open: number;
  p0: number;
  sla_breached: number;
  accounts: number;
  health_red: number;
  churn_urgent: number;
  upsell: number;
  meetings_pending: number;
  proposals: number;
  contracts: number;
  outbound_frozen: boolean;
}

export interface VenteOverview {
  pole: string;
  generated_at: string;
  stage_order: string[];
  pipeline: VenteDeal[];
  inbox: VenteMessage[];
  health: VenteHealth[];
  churn: VenteChurn[];
  upsell: VenteUpsell[];
  tickets: VenteTicket[];
  leads: VenteLead[];
  sequences: VenteSequence[];
  meetings: VenteMeeting[];
  proposals: VenteProposal[];
  bloctel: VenteBloctel;
  counts: VenteCounts;
}

const VT = "/api/poles/vente";

export function fetchVenteOverview(signal?: AbortSignal): Promise<VenteOverview> {
  return getJSON<VenteOverview>(`${VT}/overview`, signal);
}

export function uploadLeads(rows: {
  full_name: string;
  domain: string;
  title_hint?: string;
  linkedin_url?: string;
}[]): Promise<{ added: number; skipped: number }> {
  return postJSON<{ added: number; skipped: number }>(`${VT}/leads/upload`, { rows });
}

export function draftInboxReply(
  id: string,
): Promise<{ id: string; status: string; draft_path: string }> {
  return postJSON(`${VT}/inbox/${encodeURIComponent(id)}/draft`, {});
}

export function bookMeeting(id: string): Promise<VenteMeeting> {
  return postJSON<VenteMeeting>(`${VT}/meetings/${encodeURIComponent(id)}/book`, {});
}

export function scaffoldSequence(slug: string): Promise<{ slug: string; status: string }> {
  return postJSON<{ slug: string; status: string }>(`${VT}/sequences`, { slug });
}

export function draftProposal(dealId: string): Promise<VenteProposal> {
  return postJSON<VenteProposal>(`${VT}/proposals/${encodeURIComponent(dealId)}/draft`, {});
}

export function moveDealStage(dealId: string, stage: string): Promise<VenteDeal> {
  return patchJSON<VenteDeal>(`${VT}/deals/${encodeURIComponent(dealId)}/stage`, { stage });
}

export interface MeetingIcs {
  request_id: string;
  filename: string;
  ics: string;
}

export function fetchMeetingIcs(id: string, signal?: AbortSignal): Promise<MeetingIcs> {
  return getJSON<MeetingIcs>(`${VT}/meetings/${encodeURIComponent(id)}/ics`, signal);
}

// =============================================================================
// Pôle Finance & Conformité (S5) — miroir des schemas Pydantic de api/finance.py.
// =============================================================================
export interface FinanceDunning {
  invoice_id: string;
  customer: string;
  amount_due_eur: number;
  due_date: string | null;
  level: string; // J+3 | J+7 | J+15 | none
  drafted: boolean;
}

export interface FinanceBilling {
  mrr_eur: number;
  arr_eur: number;
  n_subs: number;
  n_active_subs: number;
  n_open_invoices: number;
  open_amount_eur: number;
  dunning: FinanceDunning[];
}

export interface FinanceForecast {
  expected_30d_eur: number;
  expected_60d_eur: number;
  expected_90d_eur: number;
  n_subs_considered: number;
}

export interface FinanceTreasury {
  present: boolean;
  cash_balance_eur: number | null;
  monthly_burn_eur: number | null;
  monthly_revenue_eur: number | null;
  net_burn_eur: number;
  runway_months: number | null;
  severity: string; // ok | warn | alert
  summary: string;
}

export interface FinanceFlow {
  id: string;
  flow_date: string;
  label: string;
  category: string;
  direction: string; // in | out
  amount_eur: number;
  balance_eur: number;
}

export interface FinanceLedger {
  flows: FinanceFlow[];
  total_in_eur: number;
  total_out_eur: number;
  net_eur: number;
  by_month: { month: string; net_eur: number }[];
  by_category: { category: string; net_eur: number }[];
}

export interface FinanceAnomaly {
  vendor: string;
  kind: string;
  amount_eur: number;
  settled_on: string;
  reason: string;
}

export interface FinanceExpenses {
  source_csv: string | null;
  severity: string;
  summary: string;
  anomalies: FinanceAnomaly[];
}

export interface FinanceReconcile {
  matched: number;
  orphan_payouts: number;
  orphan_credits: number;
  summary: string;
}

export interface FinanceVendorContract {
  vendor: string;
  renewal_date: string;
  deadline_date: string;
  days_until: number;
  status: string;
  monthly_cost_eur: number;
}

export interface FinanceClientContract {
  client: string;
  next_renewal: string;
  days_left: number;
  status: string;
}

export interface FinanceContracts {
  vendors: FinanceVendorContract[];
  clients: FinanceClientContract[];
}

export interface FinanceFiscalDeadline {
  kind: string;
  label: string;
  due_date: string;
  days_until: number;
}

export interface FinanceTreatment {
  nom: string;
  base_legale: string;
  finalite: string;
  donnees: string[];
  review_date: string | null;
  conforme: boolean;
  issues: string[];
}

export interface FinanceRgpd {
  present: boolean;
  should_alert: boolean;
  summary: string;
  treatments: FinanceTreatment[];
}

export interface FinanceAiActSystem {
  nom: string;
  role: string;
  risk: string;
}

export interface FinanceAiAct {
  present: boolean;
  should_alert: boolean;
  summary: string;
  counts: Record<string, number>;
  systems: FinanceAiActSystem[];
}

export interface FinanceIncident {
  slug: string;
  title: string;
  date: string;
  category: string;
  severity: string;
  status: string;
}

export interface FinanceDoc {
  name: string;
  kind: string;
  has_pdf: boolean;
}

export interface FinanceCounts {
  mrr_eur: number;
  open_invoices: number;
  dunning_due: number;
  runway_months: number | null;
  rgpd_gaps: number;
  ai_act_prohibited: number;
  ai_act_unclassified: number;
  contracts_urgent: number;
  expense_anomalies: number;
  reconcile_orphans: number;
  incidents_open: number;
  fiscal_next_days: number | null;
  compliance_blocking: boolean;
}

export interface FinanceOverview {
  pole: string;
  generated_at: string;
  billing: FinanceBilling;
  forecast: FinanceForecast;
  treasury: FinanceTreasury;
  ledger: FinanceLedger;
  expenses: FinanceExpenses;
  reconcile: FinanceReconcile;
  contracts: FinanceContracts;
  fiscal: FinanceFiscalDeadline[];
  rgpd: FinanceRgpd;
  ai_act: FinanceAiAct;
  incidents: FinanceIncident[];
  docs: FinanceDoc[];
  uploads: string[];
  contexts: string[];
  compliance_blocking: boolean;
  compliance_reason: string;
  counts: FinanceCounts;
}

const FN = "/api/poles/finance";

export function fetchFinanceOverview(signal?: AbortSignal): Promise<FinanceOverview> {
  return getJSON<FinanceOverview>(`${FN}/overview`, signal);
}

export function addFlow(payload: {
  flow_date: string;
  label: string;
  category: string;
  direction: string;
  amount_eur: number;
}): Promise<FinanceFlow> {
  return postJSON<FinanceFlow>(`${FN}/ledger/flows`, payload);
}

export function deleteFlow(flowId: string): Promise<{ deleted: boolean }> {
  return deleteJSON<{ deleted: boolean }>(`${FN}/ledger/flows/${encodeURIComponent(flowId)}`);
}

export function updateFlow(
  flowId: string,
  payload: { flow_date: string; label: string; category: string; direction: string; amount_eur: number },
): Promise<FinanceFlow> {
  return putJSON<FinanceFlow>(`${FN}/ledger/flows/${encodeURIComponent(flowId)}`, payload);
}

/** URL de téléchargement du PDF d'un doc finance (CA3/devis/contrat). */
export function financeDocPdfUrl(name: string): string {
  return `${FN}/docs/${encodeURIComponent(name)}/pdf`;
}

/** Upload binaire (multipart) d'un doc à remplir — versionné côté backend. */
export async function uploadDocFile(
  file: File,
): Promise<{ name: string; kind: string; has_pdf: boolean }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${FN}/docs/upload/file`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`POST ${FN}/docs/upload/file -> HTTP ${res.status} ${detail.slice(0, 160)}`);
  }
  return (await res.json()) as { name: string; kind: string; has_pdf: boolean };
}

export function generateDoc(
  kind: string,
  dealId?: string,
): Promise<{ name: string; kind: string; has_pdf: boolean }> {
  return postJSON(`${FN}/docs/generate`, { kind, deal_id: dealId ?? null });
}

export function uploadDoc(
  filename: string,
  content: string,
): Promise<{ name: string; kind: string; has_pdf: boolean }> {
  return postJSON(`${FN}/docs/upload`, { filename, content });
}

export function fetchDoc(name: string): Promise<{ name: string; content: string }> {
  return getJSON<{ name: string; content: string }>(`${FN}/docs/${encodeURIComponent(name)}`);
}

export function draftDunning(
  invoiceId: string,
): Promise<{ invoice_id: string; status: string; draft_path: string }> {
  return postJSON(`${FN}/invoices/${encodeURIComponent(invoiceId)}/dunning`, {});
}

export function exportAccounting(): Promise<{ path: string; csv: string }> {
  return postJSON<{ path: string; csv: string }>(`${FN}/export/accounting`, {});
}

// =============================================================================
// Pôle Direction (S6) — miroir des schemas Pydantic de api/direction.py.
// =============================================================================
export interface PoleHealthOut {
  pole: string;
  name: string;
  n_facts: number;
  n_important: number;
  n_critical: number;
  n_warning: number;
  last_activity: string | null;
  health: string; // critical | warning | healthy | idle
  headline: string | null;
  scripts: string[];
}

export interface FleetOut {
  generated_at: string;
  poles: PoleHealthOut[];
  total_facts: number;
  total_important: number;
  total_critical: number;
  poles_red: number;
  poles_yellow: number;
  poles_active: number;
  worst_health: string;
}

export interface SynthesisOut {
  headline: string;
  narrative: string;
  highlights: string[];
  risks: string[];
}

export interface KeyResultOut {
  objective: string;
  name: string;
  target: number;
  actual: number;
  unit: string;
  status: string; // off_track | at_risk | on_track | completed
  progress_pct: number;
  expected_pct: number;
}

export interface OkrOut {
  quarter: string;
  summary: string;
  should_alert: boolean;
  key_results: KeyResultOut[];
}

export interface BoardOut {
  period: string;
  mrr_eur: number;
  arr_eur: number;
  burn_eur: number | null;
  runway_months: number | null;
  nrr_pct: number | null;
  runs_month: number;
  breakers_tripped: number;
  incidents_month: number;
}

export interface PlanOut {
  severity: string; // info | warning | critical
  kind: string;
  action: string;
  detail: string;
  pole: string;
  suppressed_by_release: boolean;
}

export interface DecisionOut {
  decision_id: string;
  title: string;
  decision_date: string;
  partie: string;
  decision: string;
}

export interface SectionCount {
  type: string;
  count: number;
}

export interface ChangelogOut {
  period_label: string;
  n_commits: number;
  n_sections: number;
  section_counts: SectionCount[];
  markdown: string;
}

export interface RoadmapOut {
  entries_total: number;
  done: number;
  partial: number;
  roadmap: number;
  services: number;
  markdown: string;
}

export interface FeedbackThemeOut {
  topic: string;
  count: number;
  sources: string[];
  customers: string[];
}

export interface FeedbackOut {
  items_total: number;
  themes: FeedbackThemeOut[];
}

export interface TriagedIssueOut {
  number: number;
  title: string;
  severity: string; // P0 | P1 | P2
  suggested_label: string;
  reason: string;
}

export interface BugsOut {
  issues_total: number;
  p0: number;
  p1: number;
  p2: number;
  triaged: TriagedIssueOut[];
}

export interface DocOut {
  name: string;
  kind: string;
  has_pdf: boolean;
}

export interface DirectionCounts {
  poles_active: number;
  poles_red: number;
  fleet_critical: number;
  okr_off_track: number;
  okr_at_risk: number;
  bugs_p0: number;
  feedback_recurring: number;
  decisions: number;
  actions_planned: number;
  actions_critical: number;
  release_blocking: boolean;
}

export interface DirectionOverview {
  pole: string;
  generated_at: string;
  fleet: FleetOut;
  synthesis: SynthesisOut;
  okr: OkrOut;
  board: BoardOut;
  plan: PlanOut[];
  decisions: DecisionOut[];
  changelog: ChangelogOut;
  roadmap: RoadmapOut;
  feedback: FeedbackOut;
  bugs: BugsOut;
  docs: DocOut[];
  release_blocking: boolean;
  release_reason: string;
  counts: DirectionCounts;
}

const D = "/api/poles/direction";

export function fetchDirectionOverview(signal?: AbortSignal): Promise<DirectionOverview> {
  return getJSON<DirectionOverview>(`${D}/overview`, signal);
}

export function generateDirectionDoc(
  kind: string, // board | roadmap | changelog | release_notes
): Promise<{ name: string; kind: string; has_pdf: boolean }> {
  return postJSON(`${D}/docs/generate`, { kind });
}

export function exportBoard(): Promise<{ path: string; markdown: string }> {
  return postJSON<{ path: string; markdown: string }>(`${D}/board/export`, {});
}

export function addDecision(payload: {
  title: string;
  partie?: string;
  decision: string;
  pourquoi: string;
  implication_technique?: string | null;
  annule?: string | null;
  action_de_suivi?: string | null;
}): Promise<DecisionOut> {
  return postJSON<DecisionOut>(`${D}/decisions`, payload);
}

export function updateOkr(
  objective: string,
  name: string,
  actual: number,
): Promise<OkrOut> {
  return putJSON<OkrOut>(`${D}/okr`, { objective, name, actual });
}

export function fetchDirectionDoc(name: string): Promise<{ name: string; content: string }> {
  return getJSON<{ name: string; content: string }>(`${D}/docs/${encodeURIComponent(name)}`);
}

/** URL de téléchargement du PDF du board pack (et autres docs direction). */
export function directionDocPdfUrl(name: string): string {
  return `${D}/docs/${encodeURIComponent(name)}/pdf`;
}

// =============================================================================
// Phase 4c — détail lead, brouillon inbox, fait mémoire, statut décisions
// =============================================================================
export interface BantBreakdown {
  budget: number;
  authority: number;
  need: number;
  timing: number;
  total: number;
}

export interface EmailGuess {
  email: string;
  pattern: string;
  confidence: number;
}

export interface LeadDetail {
  slug: string;
  full_name: string;
  domain: string;
  title_hint: string | null;
  persona: string;
  bant_total: number;
  qualified: boolean;
  best_email: string | null;
  eligible: boolean;
  eligibility_reason: string;
  persona_score: number;
  persona_signals: string[];
  bant: BantBreakdown;
  email_guesses: EmailGuess[];
  markdown_body: string;
}

export function fetchLeadDetail(slug: string, signal?: AbortSignal): Promise<LeadDetail> {
  return getJSON<LeadDetail>(`${VT}/leads/${encodeURIComponent(slug)}`, signal);
}

export interface DraftBody {
  id: string;
  body: string;
  exists: boolean;
}

export function fetchInboxDraft(id: string, signal?: AbortSignal): Promise<DraftBody> {
  return getJSON<DraftBody>(`${VT}/inbox/${encodeURIComponent(id)}/draft`, signal);
}

export function saveInboxDraft(id: string, body: string): Promise<DraftBody> {
  return putJSON<DraftBody>(`${VT}/inbox/${encodeURIComponent(id)}/draft`, { body });
}

export interface FactDetail {
  id: string;
  pole: string;
  script: string;
  kind: string;
  important: boolean;
  tags: string[];
  body: string;
  source: string | null;
  created_at: string;
}

export function fetchMemoireFact(
  pole: string,
  script: string,
  recordId: string,
  signal?: AbortSignal,
): Promise<FactDetail> {
  const q = `?pole=${encodeURIComponent(pole)}&script=${encodeURIComponent(script)}&record_id=${encodeURIComponent(recordId)}`;
  return getJSON<FactDetail>(`${MEM}/fact${q}`, signal);
}

export type DecisionStatus = "open" | "closed";

export interface DecisionWithStatus {
  decision_id: string;
  title: string;
  decision_date: string;
  partie: string;
  decision: string;
  status: DecisionStatus;
}

export function fetchDecisions(signal?: AbortSignal): Promise<DecisionWithStatus[]> {
  return getJSON<DecisionWithStatus[]>(`${D}/decisions`, signal);
}

export function setDecisionStatus(id: string, status: DecisionStatus): Promise<DecisionWithStatus> {
  return patchJSON<DecisionWithStatus>(`${D}/decisions/${encodeURIComponent(id)}`, { status });
}

// =============================================================================
// Pôle Mémoire (S7) — miroir des schemas Pydantic de api/memoire.py.
// =============================================================================
export interface MemoirePoleStat {
  pole: string;
  name: string;
  active: boolean;
  n_facts: number;
  n_important: number;
  n_scripts: number;
  scripts: string[];
  last_activity: string | null;
  n_candidates: number;
}

export interface MemoirePolicy {
  protect_important: boolean;
  active_for: string[];
  protected_kinds: string[];
  protected_tags: string[];
  protected_sources: string[];
  default_ttl_days: number;
  keep_recent_per_kind: number;
  min_stale_days: number;
}

export interface WiringEdge {
  source: string;
  target: string;
  via_wildcard: boolean;
  target_facts: number;
}

export interface WiringAnomaly {
  kind: string; // orphan | self_reference | empty_target | unread_producer
  pole: string;
  detail: string;
  severity: string; // info | warning
}

export interface WiringAudit {
  generated_at: string;
  poles: string[];
  edges: WiringEdge[];
  anomalies: WiringAnomaly[];
  should_alert: boolean;
  summary: string;
  n_edges: number;
  n_warning: number;
}

export interface MemoireHistoryItem {
  script: string;
  record_id: string;
  kind: string;
  reason: string;
}

export interface MemoireHistoryEntry {
  at: string;
  pole: string;
  actor: string;
  deleted: MemoireHistoryItem[];
  refused: MemoireHistoryItem[];
  n_deleted: number;
  n_refused: number;
}

export interface MemoireCounts {
  poles_total: number;
  poles_active: number;
  facts_total: number;
  important_total: number;
  candidates_total: number;
  wiring_warnings: number;
}

export interface MemoireOverview {
  pole: string;
  generated_at: string;
  policy: MemoirePolicy;
  poles: MemoirePoleStat[];
  wiring: WiringAudit;
  history: MemoireHistoryEntry[];
  counts: MemoireCounts;
}

export interface MemoireBrowse {
  pole: string | null;
  records: MemoryFact[];
  poles: string[];
  scripts: string[];
  kinds: string[];
  total: number;
  important: number;
}

export interface DeletionCandidate {
  pole: string;
  script: string;
  record_id: string;
  kind: string;
  created_at: string;
  age_days: number;
  reason: string; // expired | stale
  detail: string;
  body_preview: string;
}

export interface ProtectedFact {
  pole: string;
  script: string;
  record_id: string;
  kind: string;
  created_at: string;
  age_days: number;
  reason: string; // important | pattern
  would_delete: boolean;
  would_delete_reason: string | null;
  detail: string;
  body_preview: string;
}

export interface CurationPlan {
  pole: string;
  active: boolean;
  generated_at: string;
  scanned: number;
  kept: number;
  n_delete: number;
  n_protected: number;
  n_important: number;
  n_saved_from_delete: number;
  to_delete: DeletionCandidate[];
  protected: ProtectedFact[];
}

export interface CleanupResult {
  pole: string;
  requested: number;
  n_deleted: number;
  n_refused: number;
  skipped: number;
  deleted: MemoireHistoryItem[];
  refused: MemoireHistoryItem[];
}

const MEM = "/api/poles/memoire";

export function fetchMemoireOverview(signal?: AbortSignal): Promise<MemoireOverview> {
  return getJSON<MemoireOverview>(`${MEM}/overview`, signal);
}

export function browseMemoire(
  params: { pole?: string; script?: string; q?: string; important?: boolean },
  signal?: AbortSignal,
): Promise<MemoireBrowse> {
  const qs = new URLSearchParams();
  if (params.pole) qs.set("pole", params.pole);
  if (params.script) qs.set("script", params.script);
  if (params.q) qs.set("q", params.q);
  if (params.important !== undefined) qs.set("important", String(params.important));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return getJSON<MemoireBrowse>(`${MEM}/browse${suffix}`, signal);
}

export function fetchMemoirePlan(pole: string, signal?: AbortSignal): Promise<CurationPlan> {
  return getJSON<CurationPlan>(`${MEM}/plan?pole=${encodeURIComponent(pole)}`, signal);
}

export function flagMemoireFact(payload: {
  pole: string;
  script: string;
  record_id: string;
  important: boolean;
}): Promise<MemoryFact> {
  return postJSON<MemoryFact>(`${MEM}/flag`, payload);
}

export function cleanMemoire(payload: {
  pole: string;
  targets: { script: string; record_id: string }[];
}): Promise<CleanupResult> {
  return postJSON<CleanupResult>(`${MEM}/clean`, payload);
}

export function updateMemoirePolicy(pole: string, active: boolean): Promise<MemoirePolicy> {
  return putJSON<MemoirePolicy>(`${MEM}/policy`, { pole, active });
}

export function fetchMemoireWiring(signal?: AbortSignal): Promise<WiringAudit> {
  return getJSON<WiringAudit>(`${MEM}/wiring`, signal);
}

// =============================================================================
// Pôle SRE & Meta-Ops (S8) — miroir des schemas Pydantic de api/sre.py.
// =============================================================================
export type SreSeverity = "green" | "yellow" | "red";

export interface SreScriptStatus {
  script: string;
  description: string;
  schedule: string | null;
  health: SreSeverity;
  last_status: string | null; // success | failed | skipped
  last_severity: SreSeverity | null;
  last_summary: string | null;
  last_run_at: string | null;
  age_hours: number | null;
  next_run_at: string | null;
  due: boolean;
  stale: boolean;
  frozen: boolean;
  breaker_tripped: boolean;
  p50_ms: number | null;
  p95_ms: number | null;
  n_runs: number;
  runnable: boolean;
}

export interface SreRun {
  at: string;
  script: string;
  status: string; // success | failed | skipped
  severity: SreSeverity;
  duration_ms: number;
  summary: string;
  error: string | null;
}

export interface SreBreaker {
  name: string;
  tripped: boolean;
  reason: string | null;
  tripped_at: string | null;
  age_hours: number | null;
}

export interface SreKillSwitch {
  frozen: boolean;
  reason: string | null;
  frozen_scripts: string[];
  updated_at: string | null;
}

export interface SreScheduleEntry {
  pole: string;
  script: string;
  schedule: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  due: boolean;
  missed: number;
}

export interface SreDecision {
  script: string;
  verdict: string; // launch | skipped_*
  reason: string;
  schedule: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  runs_today: number;
  daily_limit: number | null;
  runnable: boolean;
}

export interface SrePlan {
  generated_at: string;
  dry_run: boolean;
  max_concurrent: number;
  summary: string;
  to_launch: number;
  decisions: SreDecision[];
}

export interface SreCounts {
  scripts_total: number;
  green: number;
  yellow: number;
  red: number;
  frozen: number;
  breakers_tripped: number;
  due_now: number;
  runs_24h: number;
}

export interface SreOverview {
  pole: string;
  generated_at: string;
  health: SreSeverity;
  counts: SreCounts;
  scripts: SreScriptStatus[];
  breakers: SreBreaker[];
  killswitch: SreKillSwitch;
  schedule: SreScheduleEntry[];
  plan: SrePlan;
  recent_runs: SreRun[];
}

export interface SreRunResult {
  script: string;
  status: string;
  summary: string | null;
  error: string | null;
}

const SRE = "/api/poles/sre";

export function fetchSreOverview(signal?: AbortSignal): Promise<SreOverview> {
  return getJSON<SreOverview>(`${SRE}/overview`, signal);
}

export function fetchSreRuns(
  params: { script?: string; limit?: number },
  signal?: AbortSignal,
): Promise<SreRun[]> {
  const qs = new URLSearchParams();
  if (params.script) qs.set("script", params.script);
  if (params.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return getJSON<SreRun[]>(`${SRE}/runs${suffix}`, signal);
}

export function runSreScript(script: string): Promise<SreRunResult> {
  return postJSON<SreRunResult>(`${SRE}/run/${encodeURIComponent(script)}`, {});
}

export function resetSreBreaker(name: string): Promise<SreBreaker> {
  return postJSON<SreBreaker>(`${SRE}/breakers/${encodeURIComponent(name)}/reset`, {});
}

export function tripSreBreaker(name: string, reason: string): Promise<SreBreaker> {
  return postJSON<SreBreaker>(`${SRE}/breakers/${encodeURIComponent(name)}/trip`, { reason });
}

export function setSreKillswitch(frozen: boolean, reason?: string): Promise<SreKillSwitch> {
  return postJSON<SreKillSwitch>(`${SRE}/killswitch`, { frozen, reason: reason ?? null });
}

export function setSreKillswitchScript(script: string, frozen: boolean): Promise<SreKillSwitch> {
  return postJSON<SreKillSwitch>(`${SRE}/killswitch/script`, { script, frozen });
}
