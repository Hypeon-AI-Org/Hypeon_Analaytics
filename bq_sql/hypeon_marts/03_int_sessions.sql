-- Intermediate: normalized session-level view from GA4 staging.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.int_sessions` AS
SELECT
  CONCAT(user_pseudo_id, '-', CAST(event_date AS STRING), '-', CAST(MOD(ABS(FARM_FINGERPRINT(CAST(event_timestamp AS STRING))), 1000000) AS STRING)) AS session_id,
  user_pseudo_id,
  utm_source,
  utm_campaign,
  event_name,
  item_id,
  event_timestamp
FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`;
