-- EPIAP Database Initialization Script
-- This script runs automatically on first docker-compose up

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- Employees reference table
-- ============================================================
CREATE TABLE IF NOT EXISTS employees (
    employee_id VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    role VARCHAR,
    team VARCHAR,
    jira_account_id VARCHAR,
    github_username VARCHAR,
    is_active BOOLEAN DEFAULT true,
    PRIMARY KEY (employee_id)
);

-- ============================================================
-- Activity events — core normalized event table
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_events (
    event_id VARCHAR NOT NULL,
    employee_id VARCHAR NOT NULL,
    source VARCHAR(20) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    raw_source_id VARCHAR,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (event_id, "timestamp")
);

CREATE INDEX IF NOT EXISTS ix_activity_employee_id ON activity_events (employee_id);
CREATE INDEX IF NOT EXISTS ix_activity_source_ts ON activity_events (source, "timestamp");
CREATE INDEX IF NOT EXISTS ix_activity_employee_ts ON activity_events (employee_id, "timestamp");

-- Convert to TimescaleDB hypertable
SELECT create_hypertable(
    'activity_events', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Partial unique index for deduplication
CREATE UNIQUE INDEX IF NOT EXISTS ix_activity_raw_source_id
    ON activity_events (raw_source_id, "timestamp")
    WHERE raw_source_id IS NOT NULL;

-- ============================================================
-- Connector state tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS connector_states (
    connector_name VARCHAR NOT NULL,
    last_sync_at TIMESTAMPTZ,
    last_cursor VARCHAR,
    events_fetched_total INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'idle',
    error_detail VARCHAR,
    metadata JSONB,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (connector_name)
);

-- ============================================================
-- Metric snapshots — computed metric values
-- ============================================================
CREATE TABLE IF NOT EXISTS metric_snapshots (
    snapshot_id VARCHAR NOT NULL,
    employee_id VARCHAR NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_category VARCHAR(20) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(20),
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB,
    PRIMARY KEY (snapshot_id, computed_at)
);

CREATE INDEX IF NOT EXISTS ix_metric_employee_id ON metric_snapshots (employee_id);
CREATE INDEX IF NOT EXISTS ix_metric_emp_name_ts ON metric_snapshots (employee_id, metric_name, computed_at);

SELECT create_hypertable(
    'metric_snapshots', 'computed_at',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- ============================================================
-- Business value tags
-- ============================================================
CREATE TABLE IF NOT EXISTS business_value_tags (
    feature_id VARCHAR NOT NULL,
    feature_name VARCHAR NOT NULL,
    dollar_value FLOAT NOT NULL,
    tagged_by VARCHAR,
    tagged_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (feature_id)
);

-- ============================================================
-- Feature contributions
-- ============================================================
CREATE TABLE IF NOT EXISTS feature_contributions (
    id VARCHAR NOT NULL,
    feature_id VARCHAR NOT NULL,
    employee_id VARCHAR NOT NULL,
    contribution_factor FLOAT NOT NULL,
    source_evidence VARCHAR,
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_fc_feature_id ON feature_contributions (feature_id);
CREATE INDEX IF NOT EXISTS ix_fc_employee_id ON feature_contributions (employee_id);

-- Enable compression on activity_events
ALTER TABLE activity_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'employee_id, source'
);

SELECT add_compression_policy('activity_events', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================
-- Employee scores (Module C)
-- ============================================================
CREATE TABLE IF NOT EXISTS employee_scores (
    score_id VARCHAR NOT NULL,
    employee_id VARCHAR NOT NULL,
    delivery_score FLOAT NOT NULL DEFAULT 0,
    quality_score FLOAT NOT NULL DEFAULT 0,
    team_exp_score FLOAT NOT NULL DEFAULT 0,
    business_value_score FLOAT NOT NULL DEFAULT 0,
    overall_score FLOAT NOT NULL DEFAULT 0,
    weights JSONB,
    details JSONB,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (score_id, computed_at)
);

CREATE INDEX IF NOT EXISTS ix_score_employee_id ON employee_scores (employee_id);
CREATE INDEX IF NOT EXISTS ix_score_emp_ts ON employee_scores (employee_id, computed_at);

SELECT create_hypertable(
    'employee_scores', 'computed_at',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- ============================================================
-- Alert rules (Module D1)
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id VARCHAR NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    operator VARCHAR(5) NOT NULL,
    threshold FLOAT NOT NULL,
    threshold_unit VARCHAR(20),
    time_window VARCHAR(20),
    priority VARCHAR(10) NOT NULL,
    targets VARCHAR NOT NULL,
    description VARCHAR,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (rule_id)
);

-- ============================================================
-- Alert records (Module D2)
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_records (
    alert_id VARCHAR NOT NULL,
    rule_id VARCHAR NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    operator VARCHAR(5) NOT NULL,
    employee_id VARCHAR,
    team VARCHAR,
    priority VARCHAR(10) NOT NULL,
    status VARCHAR(15) DEFAULT 'active',
    targets VARCHAR NOT NULL,
    message VARCHAR,
    details JSONB,
    fired_at TIMESTAMPTZ DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    PRIMARY KEY (alert_id)
);

CREATE INDEX IF NOT EXISTS ix_alert_rule_id ON alert_records (rule_id);
CREATE INDEX IF NOT EXISTS ix_alert_employee_id ON alert_records (employee_id);
CREATE INDEX IF NOT EXISTS ix_alert_status ON alert_records (status);
CREATE INDEX IF NOT EXISTS ix_alert_priority_status ON alert_records (priority, status);
CREATE INDEX IF NOT EXISTS ix_alert_fired_at ON alert_records (fired_at);

-- Mark Alembic as up to date so migrations don't conflict
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    PRIMARY KEY (version_num)
);

INSERT INTO alembic_version (version_num)
VALUES ('002')
ON CONFLICT (version_num) DO NOTHING;
