-- Enterprise: full schema for new deployments (analytics_insights + decision_history + supporting_metrics_snapshot).
-- Substitute {BQ_PROJECT}, {ANALYTICS_DATASET}.

-- =============================================================================
-- Table: analytics_insights (with organization_id, workspace_id, priority, impact)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights` (
  insight_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  client_id INT64 NOT NULL,
  workspace_id STRING,
  entity_type STRING,
  entity_id STRING,
  insight_type STRING,
  summary STRING,
  explanation STRING,
  recommendation STRING,
  expected_impact STRUCT<metric STRING, estimate FLOAT64, units STRING>,
  expected_impact_value FLOAT64,
  confidence FLOAT64,
  priority_score FLOAT64,
  severity STRING,
  rank INT64,
  insight_hash STRING,
  potential_savings FLOAT64,
  potential_revenue_gain FLOAT64,
  risk_level STRING,
  evidence ARRAY<STRUCT<metric STRING, value FLOAT64, baseline FLOAT64, period STRING>>,
  detected_by ARRAY<STRING>,
  status STRING,
  created_at TIMESTAMP,
  applied_at TIMESTAMP,
  history STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, client_id, insight_type
OPTIONS(description = 'Canonical insights store for HypeOn Analytics V1 Enterprise');

-- =============================================================================
-- View: analytics_recommendations
-- =============================================================================
CREATE OR REPLACE VIEW `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_recommendations` AS
SELECT * FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights`
WHERE status IN ('new', 'reviewed');

-- =============================================================================
-- Table: decision_history
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
OPTIONS(description = 'Decision lifecycle: NEW -> REVIEWED -> APPLIED -> VERIFIED');

-- =============================================================================
-- Table: supporting_metrics_snapshot (Copilot grounding only)
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
