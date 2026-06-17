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

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`POST ${path} -> HTTP ${res.status} ${detail.slice(0, 160)}`);
  }
  return (await res.json()) as T;
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
