-- HypeOn Analytics V1: Decision Store (analytics_insights + analytics_recommendations view)
-- Run with run_decision_store.py or substitute {BQ_PROJECT}, {ANALYTICS_DATASET} and execute.

-- =============================================================================
-- Table: analytics_insights (canonical schema)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights` (
  insight_id STRING NOT NULL,
  client_id INT64 NOT NULL,
  entity_type STRING,
  entity_id STRING,
  insight_type STRING,
  summary STRING,
  explanation STRING,
  recommendation STRING,
  expected_impact STRUCT<
    metric STRING,
    estimate FLOAT64,
    units STRING
  >,
  confidence FLOAT64,
  evidence ARRAY<STRUCT<
    metric STRING,
    value FLOAT64,
    baseline FLOAT64,
    period STRING
  >>,
  detected_by ARRAY<STRING>,
  status STRING,
  created_at TIMESTAMP,
  applied_at TIMESTAMP,
  history STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY client_id, insight_type
OPTIONS(
  description = 'Canonical insights store for HypeOn Analytics V1'
);

-- =============================================================================
-- View: analytics_recommendations (actionable insights: status new or reviewed)
-- =============================================================================
CREATE OR REPLACE VIEW `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_recommendations` AS
SELECT *
FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.analytics_insights`
WHERE status IN ('new', 'reviewed');
