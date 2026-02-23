-- Enterprise: multi-tenant columns, insight prioritization fields, decision_history.
-- Run after create_decision_store.sql. Substitute {BQ_PROJECT}, {ANALYTICS_DATASET}.

-- =============================================================================
-- 1) Add columns to analytics_insights (run once; ignore if already present)
-- =============================================================================
ALTER TABLE `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights`
  ADD COLUMN IF NOT EXISTS organization_id STRING,
  ADD COLUMN IF NOT EXISTS workspace_id STRING,
  ADD COLUMN IF NOT EXISTS priority_score FLOAT64,
  ADD COLUMN IF NOT EXISTS expected_impact_value FLOAT64,
  ADD COLUMN IF NOT EXISTS severity STRING,
  ADD COLUMN IF NOT EXISTS rank INT64,
  ADD COLUMN IF NOT EXISTS insight_hash STRING,
  ADD COLUMN IF NOT EXISTS potential_savings FLOAT64,
  ADD COLUMN IF NOT EXISTS potential_revenue_gain FLOAT64,
  ADD COLUMN IF NOT EXISTS risk_level STRING;

-- =============================================================================
-- 2) decision_history: lifecycle NEW → REVIEWED → APPLIED → VERIFIED
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.decision_history` (
  history_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  client_id INT64 NOT NULL,
  workspace_id STRING,
  insight_id STRING NOT NULL,
  recommended_action STRING,
  status STRING NOT NULL,
  applied_by STRING,
  applied_at TIMESTAMP,
  outcome_metrics_after_7d STRING,
  outcome_metrics_after_30d STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, client_id, status
OPTIONS(description = 'Decision lifecycle tracking for enterprise V1');

-- =============================================================================
-- 3) supporting_metrics_snapshot: for Copilot grounding (no raw analytics tables)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.supporting_metrics_snapshot` (
  snapshot_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  client_id INT64 NOT NULL,
  insight_id STRING NOT NULL,
  metrics_json STRING,
  created_at TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, client_id;
