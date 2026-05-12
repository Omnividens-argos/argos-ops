-- Argos Ops — Migration initiale (P3.1)
-- Cible : DB `argos_ops` sur cluster Postgres existant (D-002).
-- Idempotente : peut être ré-appliquée sans casser un schéma déjà créé.

BEGIN;

-- =============================================================================
-- Extensions
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- Identités
-- =============================================================================
CREATE TABLE IF NOT EXISTS companies (
  id BIGSERIAL PRIMARY KEY,
  domain TEXT UNIQUE,
  name TEXT,
  industry TEXT,
  size_band TEXT,
  source TEXT,                    -- 'inbound_chat' | 'outbound' | 'ad_lead'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL,
  email TEXT UNIQUE,
  full_name TEXT,
  job_title TEXT,
  linkedin_url TEXT,
  phone TEXT,
  status TEXT,                    -- 'new' | 'qualified' | 'demo_booked' | 'customer' | 'lost'
  bant_score INT,                 -- 0-100
  consent_email BOOLEAN NOT NULL DEFAULT false,
  consent_phone BOOLEAN NOT NULL DEFAULT false,
  bloctel_checked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leads_company_id ON leads(company_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

CREATE TABLE IF NOT EXISTS interactions (
  id BIGSERIAL PRIMARY KEY,
  lead_id BIGINT REFERENCES leads(id) ON DELETE CASCADE,
  channel TEXT,                   -- 'email' | 'phone' | 'linkedin' | 'mastodon'
  direction TEXT,                 -- 'in' | 'out'
  agent_name TEXT,                -- 'EmailBot' | 'SupportBot' | 'FinanceBot' | ...
  subject TEXT,
  body TEXT,
  judge_score INT,                -- 0-100, NULL si non jugé
  judge_verdict TEXT,             -- 'auto_send' | 'queued' | 'killed'
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_interactions_lead_id ON interactions(lead_id);
CREATE INDEX IF NOT EXISTS idx_interactions_occurred_at ON interactions(occurred_at DESC);

CREATE TABLE IF NOT EXISTS tickets (
  id BIGSERIAL PRIMARY KEY,
  lead_id BIGINT REFERENCES leads(id) ON DELETE CASCADE,
  status TEXT,                    -- 'open' | 'pending_human' | 'closed'
  priority TEXT,                  -- 'P0' | 'P1' | 'P2'
  summary TEXT,
  resolution TEXT,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tickets_lead_id ON tickets(lead_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

-- =============================================================================
-- Observabilité agents
-- =============================================================================
CREATE TABLE IF NOT EXISTS agent_runs (
  id BIGSERIAL PRIMARY KEY,
  agent_name TEXT NOT NULL,
  command TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ,
  status TEXT,                    -- 'success' | 'failed' | 'killed_by_breaker'
  output_summary TEXT,
  error TEXT,
  cost_estimate_eur NUMERIC(10,4)
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at DESC);

-- =============================================================================
-- Knowledge Base vectorielle
-- =============================================================================
CREATE TABLE IF NOT EXISTS kb_chunks (
  id BIGSERIAL PRIMARY KEY,
  doc_path TEXT NOT NULL,         -- 'data/knowledge_base/pricing.md'
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,     -- sha256(content), pour idempotence du seed
  embedding vector(768),          -- paraphrase-multilingual-mpnet-base-v2 = 768 dims natif (D-017)
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (doc_path, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
  ON kb_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- =============================================================================
-- Circuit breakers state
-- =============================================================================
CREATE TABLE IF NOT EXISTS breakers (
  name TEXT PRIMARY KEY,
  tripped BOOLEAN NOT NULL DEFAULT false,
  tripped_at TIMESTAMPTZ,
  reason TEXT,
  reset_after TIMESTAMPTZ
);

-- =============================================================================
-- Configuration runtime des agents (pilotée par Admin Control Panel, P16)
-- =============================================================================
CREATE TABLE IF NOT EXISTS agent_config (
  agent_name TEXT PRIMARY KEY,        -- 'ContentBot', 'EmailBot', 'AdBot', ...
  enabled BOOLEAN NOT NULL DEFAULT true,
  intensity_level INT NOT NULL DEFAULT 5,  -- 1 (très éco) à 10 (à fond)
  schedule_cron TEXT,                 -- '*/15 * * * *' éditable depuis le dashboard
  daily_limit INT,                    -- volume max d'actions par jour (NULL = pas de limite)
  max_tokens_per_day INT,             -- quota LLM par jour (NULL = pas de limite)
  tier1_threshold INT NOT NULL DEFAULT 80,  -- seuil agent-juge pour auto-send (50-100)
  paused_until TIMESTAMPTZ,           -- pause temporaire (1h, 24h, manuelle)
  notes TEXT,                         -- raison d'un état exceptionnel
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by TEXT                     -- 'system' | 'admin' | nom du breaker
);

-- =============================================================================
-- Sessions d'authentification du Admin Control Panel
-- =============================================================================
CREATE TABLE IF NOT EXISTS admin_sessions (
  token TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  revoked BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires_at ON admin_sessions(expires_at);

COMMIT;
