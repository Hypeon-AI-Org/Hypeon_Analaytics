-- Marts: one row per purchase (transaction). For pareto revenue, first product, ROAS, LTV.
-- Built from stg_ga4__events where event_name = 'purchase' and transaction_id present.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_orders` AS
SELECT
  transaction_id,
  user_pseudo_id,
  event_date,
  PARSE_DATE('%Y%m%d', event_date) AS order_date,
  utm_source,
  utm_medium,
  utm_campaign,
  device_category AS device,
  city,
  country,
  -- Revenue: event-level purchase_revenue_in_usd when set, else sum of item_revenue
  COALESCE(NULLIF(MAX(purchase_revenue_in_usd), 0), SUM(COALESCE(item_revenue, 0)), 0) AS revenue_usd
FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`
WHERE event_name = 'purchase'
  AND COALESCE(transaction_id, '') != ''
GROUP BY
  transaction_id,
  user_pseudo_id,
  event_date,
  utm_source,
  utm_medium,
  utm_campaign,
  device_category,
  city,
  country;
