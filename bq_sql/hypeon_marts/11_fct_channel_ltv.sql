-- Marts: 90-day (and 7/30) LTV by acquisition channel. "Which channel acquires customers with highest 90-day LTV."

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_channel_ltv` AS
SELECT
  COALESCE(first_touch_utm_source, '(direct)') AS channel_source,
  COALESCE(first_touch_utm_medium, '') AS channel_medium,
  COUNT(*) AS users_with_purchase,
  SUM(revenue_7d) AS total_revenue_7d,
  SUM(revenue_30d) AS total_revenue_30d,
  SUM(revenue_90d) AS total_revenue_90d,
  SAFE_DIVIDE(SUM(revenue_90d), COUNT(*)) AS avg_ltv_90d
FROM `{BQ_PROJECT}.hypeon_marts.fct_user_ltv`
GROUP BY first_touch_utm_source, first_touch_utm_medium;
