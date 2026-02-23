-- Add confidence_score to decision_history for outcome learning.
-- Run in BigQuery (ALTER TABLE for each column if not exists).

-- decision_history: add confidence_score (FLOAT64) if your schema doesn't have it.
-- ALTER TABLE `{BQ_PROJECT}.{ANALYTICS_DATASET}.decision_history`
-- ADD COLUMN IF NOT EXISTS confidence_score FLOAT64;

-- metric_change_after_7d / metric_change_after_30d are already in decision_history as outcome_metrics_after_7d, outcome_metrics_after_30d.
-- decision_success_score can be stored in a new column or in payload; for minimal change we use outcome_metrics_after_30d to store JSON including success_score.
-- Optional: ADD COLUMN IF NOT EXISTS decision_success_score FLOAT64;
