-- Marts: core analytics table for event/product/traffic analytics. Copilot queries this.
-- Extended with event_date, transaction_id, revenue, geo, page for pareto, funnel, LTV questions.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_sessions` AS
SELECT
  CONCAT(user_pseudo_id, '-', event_date, '-', CAST(MOD(ABS(FARM_FINGERPRINT(CAST(event_timestamp AS STRING))), 1000000) AS STRING)) AS session_id,
  event_date,
  TIMESTAMP_MICROS(event_timestamp) AS event_time,
  event_name,
  user_pseudo_id,
  utm_source,
  utm_medium,
  utm_campaign,
  item_id,
  device_category AS device,
  transaction_id,
  event_value_in_usd,
  purchase_revenue_in_usd,
  item_revenue,
  city,
  country,
  region,
  page_location
FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`;
