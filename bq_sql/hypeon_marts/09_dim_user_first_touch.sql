-- Marts: first touch and first purchase per user. For new vs recycled, days to purchase, LTV.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.dim_user_first_touch` AS
WITH first_events AS (
  SELECT
    user_pseudo_id,
    MIN(PARSE_DATE('%Y%m%d', event_date)) AS first_visit_date,
    MIN(CASE WHEN event_name = 'purchase' THEN PARSE_DATE('%Y%m%d', event_date) END) AS first_purchase_date,
    (ARRAY_AGG(STRUCT(utm_source, utm_medium) ORDER BY event_timestamp))[OFFSET(0)] AS first_touch
  FROM `{BQ_PROJECT}.hypeon_marts.stg_ga4__events`
  GROUP BY user_pseudo_id
)
SELECT
  user_pseudo_id,
  first_visit_date,
  first_purchase_date,
  first_touch.utm_source,
  first_touch.utm_medium,
  DATE_DIFF(first_purchase_date, first_visit_date, DAY) AS days_to_first_purchase,
  CASE WHEN first_purchase_date IS NOT NULL THEN 1 ELSE 0 END AS has_purchased
FROM first_events;
