-- Catalog Health AI — Database Schema
-- Run this in your Supabase SQL editor to initialize the schema
-- Version: 1.0.0 | Created: 2026-04-25

-- ─────────────────────────────────────────────────────────────────────────────
-- Enable UUID extension
-- ─────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────────────────────
-- ASSETS
-- Stores all Collibra assets (tables, columns, reports, KPIs, etc.)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT,                          -- Collibra asset ID (for upserts)
    name            TEXT NOT NULL,
    asset_type      TEXT,                          -- Table, Column, Report, KPI, etc.
    domain          TEXT,                          -- Collibra domain
    owner           TEXT,                          -- Assigned data owner
    steward         TEXT,                          -- Assigned data steward
    description     TEXT,                          -- Asset description / business definition
    critical_flag   BOOLEAN DEFAULT FALSE,         -- Is this a Critical Data Element?
    pii_flag        BOOLEAN DEFAULT FALSE,         -- Contains PII?
    last_modified   TIMESTAMPTZ,                   -- Last modified in Collibra
    tags            TEXT[],                        -- Array of tags (PII, CDE, domain tags)
    raw_metadata    JSONB,                         -- Full raw Collibra export row
    scan_id         UUID,                          -- Which scan run ingested this
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ                    -- Soft delete
);

CREATE INDEX IF NOT EXISTS idx_assets_external_id  ON assets(external_id);
CREATE INDEX IF NOT EXISTS idx_assets_domain        ON assets(domain);
CREATE INDEX IF NOT EXISTS idx_assets_owner         ON assets(owner);
CREATE INDEX IF NOT EXISTS idx_assets_critical      ON assets(critical_flag);
CREATE INDEX IF NOT EXISTS idx_assets_last_modified ON assets(last_modified);
CREATE INDEX IF NOT EXISTS idx_assets_scan_id       ON assets(scan_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- LINEAGE
-- Stores source → target lineage relationships
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lineage (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_asset_id  UUID REFERENCES assets(id) ON DELETE CASCADE,
    target_asset_id  UUID REFERENCES assets(id) ON DELETE CASCADE,
    source_name      TEXT,                         -- Denormalized for fast lookup
    target_name      TEXT,
    confidence_score FLOAT DEFAULT 1.0,            -- 0.0 → 1.0
    lineage_type     TEXT DEFAULT 'data_flow',     -- data_flow | transformation | copy
    scan_id          UUID,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lineage_source ON lineage(source_asset_id);
CREATE INDEX IF NOT EXISTS idx_lineage_target ON lineage(target_asset_id);
CREATE INDEX IF NOT EXISTS idx_lineage_scan   ON lineage(scan_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- SCAN RUNS
-- Tracks each time the agent pipeline has been executed
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scan_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status          TEXT DEFAULT 'running',        -- running | completed | failed
    total_assets    INTEGER DEFAULT 0,
    total_findings  INTEGER DEFAULT 0,
    health_score    FLOAT,
    audit_score     FLOAT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- FINDINGS
-- Every issue detected by any agent
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS findings (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id      UUID REFERENCES scan_runs(id) ON DELETE CASCADE,
    asset_id     UUID REFERENCES assets(id) ON DELETE CASCADE,
    asset_name   TEXT,                             -- Denormalized for fast display
    agent        TEXT NOT NULL,                    -- metadata_curator | lineage_guardian | governance_gap | executive_risk
    rule_id      TEXT NOT NULL,                    -- R1 → R6 or custom rule code
    issue_type   TEXT NOT NULL,                    -- missing_owner | stale_asset | broken_lineage | etc.
    severity     TEXT NOT NULL                     -- High | Medium | Low
                 CHECK (severity IN ('High', 'Medium', 'Low')),
    message      TEXT NOT NULL,                    -- Human-readable description
    details      JSONB,                            -- Structured extra context
    status       TEXT DEFAULT 'Open'               -- Open | In Progress | Resolved | Suppressed
                 CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Suppressed')),
    resolved_by  TEXT,
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_scan_id    ON findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_findings_asset_id   ON findings(asset_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity   ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_status     ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_agent      ON findings(agent);
CREATE INDEX IF NOT EXISTS idx_findings_issue_type ON findings(issue_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- AI SUMMARIES
-- Cached Claude-generated summaries per scan run (do not re-call on every GET)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_summaries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID REFERENCES scan_runs(id) ON DELETE CASCADE,
    summary_type        TEXT NOT NULL,             -- executive | steward | trend
    content             TEXT NOT NULL,             -- Claude's raw text output
    model_used          TEXT DEFAULT 'claude-sonnet-4-20250514',
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    expires_at          TIMESTAMPTZ,               -- TTL: 24h after creation
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_summaries_scan_id ON ai_summaries(scan_id);
CREATE INDEX IF NOT EXISTS idx_summaries_type    ON ai_summaries(summary_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: auto-update updated_at on all tables
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_assets_updated_at
    BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_lineage_updated_at
    BEFORE UPDATE ON lineage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_findings_updated_at
    BEFORE UPDATE ON findings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
