-- HypeOn Analytics V1: BigQuery ML anomaly / forecasting
-- Substitute {BQ_PROJECT}, {ANALYTICS_DATASET} when running.

-- =============================================================================
-- 1) Create ARIMA_PLUS model for daily revenue per (client_id, campaign_id)
-- =============================================================================
CREATE OR REPLACE MODEL `{BQ_PROJECT}.{ANALYTICS_DATASET}.revenue_anomaly_model`
OPTIONS(
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'date',
  time_series_data_col = 'revenue',
  time_series_id_col = 'campaign_key',
  horizon = 7,
  auto_arima = TRUE
) AS
SELECT
  date,
  CONCAT(CAST(client_id AS STRING), '_', COALESCE(CAST(campaign_id AS STRING), '')) AS campaign_key,
  SUM(COALESCE(revenue, 0)) AS revenue
FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2
ORDER BY 1, 2;

-- =============================================================================
-- 2) Anomaly flags table
-- =============================================================================
CREATE TABLE IF NOT EXISTS `{BQ_PROJECT}.{ANALYTICS_DATASET}.anomaly_flags` (
  client_id INT64,
  campaign_id STRING,
  date DATE,
  is_anomaly BOOL,
  anomaly_score FLOAT64,
  revenue FLOAT64,
  predicted_revenue FLOAT64,
  created_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY client_id, campaign_id;

-- =============================================================================
-- 3) Scoring: run ML.FORECAST for last 3 days and compare to actual; flag large deviations.
--    Execute via backend/scripts/run_anomaly_scoring.py or scheduled query.
-- =============================================================================
-- See backend/scripts/run_anomaly_scoring.py for the scoring job that:
-- - Calls ML.FORECAST(horizon=3), joins to actuals, computes residual, sets is_anomaly and anomaly_score
-- - Inserts into anomaly_flags
