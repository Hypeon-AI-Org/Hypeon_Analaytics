-- Marts: core analytics table for event/product/traffic analytics. Copilot queries this.
-- Simpler: single source from stg_ga4 with session_id derived.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_sessions` AS
SELECT
  CONCAT(user_pseudo_id, '-', event_date, '-', CAST(MOD(ABS(FARM_FINGERPRINT(CAST(event_timestamp AS STRING))), 1000000) AS STRING)) AS session_id,
  TIMESTAMP_MICROS(event_timestamp) AS event_time,
  event_name,
  user_pseudo_id,
  utm_source,
  utm_campaign,
  item_id,
  device_category AS device
FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`;
