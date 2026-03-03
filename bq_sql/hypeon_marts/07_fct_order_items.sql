-- Marts: one row per item in a purchase. For basket analysis, co-purchase, product revenue.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_order_items` AS
SELECT
  transaction_id,
  user_pseudo_id,
  event_date,
  item_id,
  item_name,
  item_quantity,
  item_revenue,
  utm_source,
  device_category AS device
FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`
WHERE event_name = 'purchase'
  AND COALESCE(transaction_id, '') != ''
  AND item_id IS NOT NULL;
