-- Marts: funnel steps (view_item, add_to_cart, begin_checkout, purchase) for drop-off and conversion by device/channel.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.fct_funnel` AS
SELECT
  event_date,
  event_name,
  device_category AS device,
  utm_source,
  utm_medium,
  CASE WHEN COALESCE(utm_source, '') = '' AND COALESCE(utm_medium, '') = '' THEN 'organic' ELSE 'paid' END AS channel_type,
  COUNT(DISTINCT user_pseudo_id) AS unique_users,
  COUNT(*) AS events
FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`
WHERE event_name IN ('view_item', 'view_item_list', 'add_to_cart', 'begin_checkout', 'purchase', 'session_start')
GROUP BY event_date, event_name, device_category, utm_source, utm_medium;
