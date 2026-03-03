-- Marts: per-user order summary for churn risk, top spenders, repeat purchase rate.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.dim_user_order_summary` AS
SELECT
  user_pseudo_id,
  MIN(order_date) AS first_order_date,
  MAX(order_date) AS last_order_date,
  COUNT(*) AS order_count,
  SUM(revenue_usd) AS total_revenue_usd,
  DATE_DIFF(CURRENT_DATE(), MAX(order_date), DAY) AS days_since_last_order
FROM `{BQ_PROJECT}.hypeon_marts.fct_orders`
GROUP BY user_pseudo_id;
