-- Executive summaries and system health. Substitute {BQ_PROJECT}, {ANALYTICS_DATASET}.

-- =============================================================================
-- Table: executive_summaries (daily Business Health Summary)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.executive_summaries` (
  summary_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  client_id INT64,
  workspace_id STRING,
  summary_date DATE NOT NULL,
  top_risks STRING,
  top_opportunities STRING,
  overall_growth_state STRING,
  recommended_focus_today STRING,
  created_at TIMESTAMP
)
PARTITION BY summary_date
CLUSTER BY organization_id, client_id
OPTIONS(description = 'Daily executive business health summary');

-- =============================================================================
-- Table: system_health (agent runs, failures, volume, latency)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.system_health` (
  health_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  check_time TIMESTAMP NOT NULL,
  agent_name STRING,
  agent_runtime_seconds FLOAT64,
  failures INT64,
  insight_volume INT64,
  processing_latency_seconds FLOAT64,
  status STRING,
  details STRING,
  created_at TIMESTAMP
)
PARTITION BY DATE(check_time)
CLUSTER BY organization_id, agent_name
OPTIONS(description = 'System health and agent run metrics');

-- =============================================================================
-- Table: audit_log (agent_runs, insight_generated, decision_applied, copilot_queries, user_actions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.audit_log` (
  audit_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  event_type STRING NOT NULL,
  entity_id STRING,
  user_id STRING,
  payload STRING,
  created_at TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, event_type
OPTIONS(description = 'Enterprise audit log');
