-- Staging: GA4 events flattened (with UNNEST(items)). Source: analytics_*.events_*
-- Extended with revenue, transaction_id, geo, page_location for pareto, basket, funnel, LTV.
-- Replace {BQ_PROJECT}, {BQ_SOURCE_PROJECT}, {GA4_DATASET} from .env before running.
-- LEFT JOIN UNNEST(items) so events without items (e.g. session_start, begin_checkout) still appear.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.stg_ga4__events` AS
SELECT
  e.event_date,
  e.event_timestamp,
  e.event_name,
  e.user_pseudo_id,
  COALESCE(e.traffic_source.source, '') AS utm_source,
  COALESCE(e.traffic_source.medium, '') AS utm_medium,
  COALESCE(e.traffic_source.name, '') AS utm_campaign,
  COALESCE(e.device.category, '') AS device_category,
  -- Revenue: event-level (purchase) and item-level
  COALESCE(e.event_value_in_usd, 0) AS event_value_in_usd,
  COALESCE(e.ecommerce.transaction_id, '') AS transaction_id,
  COALESCE(e.ecommerce.purchase_revenue_in_usd, 0) AS purchase_revenue_in_usd,
  COALESCE(item.item_revenue_in_usd, item.item_revenue, 0) AS item_revenue,
  -- Geo
  COALESCE(e.geo.city, '') AS city,
  COALESCE(e.geo.country, '') AS country,
  COALESCE(e.geo.region, '') AS region,
  -- Page (GA4 exports page_location in event_params for web)
  (SELECT COALESCE(MAX(CASE WHEN ep.key = 'page_location' THEN ep.value.string_value END), '')
   FROM UNNEST(COALESCE(e.event_params, [])) AS ep) AS page_location,
  -- Item (nullable when event has no items)
  item.item_id,
  item.item_name,
  COALESCE(item.quantity, 0) AS item_quantity
FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*` AS e
LEFT JOIN UNNEST(COALESCE(e.items, [])) AS item ON TRUE
WHERE e.event_date IS NOT NULL;
