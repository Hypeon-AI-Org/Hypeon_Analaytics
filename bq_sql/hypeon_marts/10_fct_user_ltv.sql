-- Marts: per-user LTV in first 7/30/90 days after first purchase. First-touch channel for "which channel acquires highest 90-day LTV".

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_user_ltv` AS
WITH users AS (
  SELECT user_pseudo_id, first_purchase_date, utm_source AS first_touch_utm_source, utm_medium AS first_touch_utm_medium
  FROM `{BQ_PROJECT}.hypeon_marts.dim_user_first_touch`
  WHERE first_purchase_date IS NOT NULL
),
orders AS (
  SELECT user_pseudo_id, order_date, revenue_usd
  FROM `{BQ_PROJECT}.hypeon_marts.fct_orders`
)
SELECT
  u.user_pseudo_id,
  u.first_touch_utm_source,
  u.first_touch_utm_medium,
  u.first_purchase_date,
  COALESCE(SUM(CASE WHEN o.order_date >= u.first_purchase_date AND o.order_date <= DATE_ADD(u.first_purchase_date, INTERVAL 7 DAY) THEN o.revenue_usd ELSE 0 END), 0) AS revenue_7d,
  COALESCE(SUM(CASE WHEN o.order_date >= u.first_purchase_date AND o.order_date <= DATE_ADD(u.first_purchase_date, INTERVAL 30 DAY) THEN o.revenue_usd ELSE 0 END), 0) AS revenue_30d,
  COALESCE(SUM(CASE WHEN o.order_date >= u.first_purchase_date AND o.order_date <= DATE_ADD(u.first_purchase_date, INTERVAL 90 DAY) THEN o.revenue_usd ELSE 0 END), 0) AS revenue_90d
FROM users u
LEFT JOIN orders o ON u.user_pseudo_id = o.user_pseudo_id
  AND o.order_date >= u.first_purchase_date
  AND o.order_date <= DATE_ADD(u.first_purchase_date, INTERVAL 90 DAY)
GROUP BY u.user_pseudo_id, u.first_touch_utm_source, u.first_touch_utm_medium, u.first_purchase_date;
