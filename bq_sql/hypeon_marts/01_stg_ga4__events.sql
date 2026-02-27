-- Staging: GA4 events flattened (with UNNEST(items)). Source: analytics_*.events_*
-- Replace {BQ_PROJECT}, {BQ_SOURCE_PROJECT}, {GA4_DATASET} from .env before running.

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
  item.item_id,
  item.item_name,
  COALESCE(item.quantity, 0) AS item_quantity
FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*` AS e,
  UNNEST(COALESCE(e.items, [])) AS item
WHERE e.event_date IS NOT NULL;
