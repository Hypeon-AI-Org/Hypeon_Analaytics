-- HypeOn Analytics V1: Unified marketing performance table
-- Sources: Ads + GA4 in BQ_SOURCE_PROJECT (can be different from app project).
-- Output: marketing_performance_daily in BQ_PROJECT.ANALYTICS_DATASET (app DB).
-- Run with run_unified_table.py which substitutes {BQ_PROJECT}, {BQ_SOURCE_PROJECT}, {ADS_DATASET}, {GA4_DATASET}, {ANALYTICS_DATASET}

CREATE OR REPLACE TABLE `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
PARTITION BY date
CLUSTER BY client_id, campaign_id
AS (
-- =============================================================================
-- CTE: Ads daily (one row per client_id, date, channel, campaign_id, ad_group_id, device)
-- =============================================================================
WITH ads_daily AS (
  SELECT
    CAST(customer_id AS INT64) AS client_id,
    segments_date AS date,
    'google_ads' AS channel,
    CAST(campaign_id AS STRING) AS campaign_id,
    CAST(ad_group_id AS STRING) AS ad_group_id,
    COALESCE(segments_device, 'UNKNOWN') AS device,
    SAFE_DIVIDE(COALESCE(metrics_cost_micros, 0), 1e6) AS spend,
    COALESCE(metrics_clicks, 0) AS clicks,
    COALESCE(metrics_impressions, 0) AS impressions,
    COALESCE(metrics_conversions, 0) AS conversions,
    COALESCE(metrics_conversions_value, 0) AS revenue
  FROM `{BQ_SOURCE_PROJECT}.{ADS_DATASET}.ads_AdGroupBasicStats_4221201460`
  WHERE segments_date IS NOT NULL
    AND customer_id IS NOT NULL
),

-- =============================================================================
-- CTE: GA4 daily (one row per client_id, date, device; campaign/ad_group NULL for organic)
-- Uses first GA4 property as client_id mapping; extend with ga4_property_id -> client_id if multi-tenant
-- =============================================================================
ga4_daily AS (
  SELECT
    1 AS client_id,  -- single property V1; use config table for multi-property
    PARSE_DATE('%Y%m%d', event_date) AS date,
    'ga4' AS channel,
    CAST(NULL AS STRING) AS campaign_id,
    CAST(NULL AS STRING) AS ad_group_id,
    COALESCE(device.category, 'UNKNOWN') AS device,
    0 AS spend,
    0 AS clicks,
    0 AS impressions,
    COUNTIF(event_name = 'purchase' OR event_name = 'conversion') AS conversions,
    COALESCE(SUM(COALESCE(event_value_in_usd, 0)), 0) AS revenue
  FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`
  WHERE event_date IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6
),

-- =============================================================================
-- Union and coalesce metrics (sessions from GA4 only; for Ads we use 0 or leave for later)
-- =============================================================================
unified_raw AS (
  SELECT client_id, date, channel, campaign_id, ad_group_id, device,
    spend, clicks, impressions, conversions, revenue,
    0 AS sessions
  FROM ads_daily
  UNION ALL
  SELECT client_id, date, channel, campaign_id, ad_group_id, device,
    spend, clicks, impressions, conversions, revenue,
    -- sessions: approximate from GA4 event count per day/device if needed; here use 0 for unified row
    0 AS sessions
  FROM ga4_daily
),

-- =============================================================================
-- Aggregate to one row per (client_id, date, channel, campaign_id, ad_group_id, device)
-- =============================================================================
unified_agg AS (
  SELECT
    client_id,
    date,
    channel,
    campaign_id,
    ad_group_id,
    device,
    SUM(spend) AS spend,
    SUM(clicks) AS clicks,
    SUM(impressions) AS impressions,
    SUM(conversions) AS conversions,
    SUM(revenue) AS revenue,
    SUM(sessions) AS sessions
  FROM unified_raw
  GROUP BY 1, 2, 3, 4, 5, 6
),

-- =============================================================================
-- Derived metrics + rolling baselines (7d and 28d avg for ROAS and revenue)
-- =============================================================================
with_baselines AS (
  SELECT
    *,
    SAFE_DIVIDE(revenue, spend) AS roas,
    SAFE_DIVIDE(spend, NULLIF(conversions, 0)) AS cpa,
    SAFE_DIVIDE(clicks, NULLIF(impressions, 0)) AS ctr,
    SAFE_DIVIDE(conversions, NULLIF(sessions, 0)) AS conversion_rate,
    AVG(SAFE_DIVIDE(revenue, spend)) OVER w7 AS roas_7d_avg,
    AVG(revenue) OVER w7 AS revenue_7d_avg,
    AVG(SAFE_DIVIDE(revenue, spend)) OVER w28 AS roas_28d_avg,
    AVG(revenue) OVER w28 AS revenue_28d_avg
  FROM unified_agg
  WINDOW
    w7 AS (PARTITION BY client_id, channel, campaign_id, ad_group_id, device ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
    w28 AS (PARTITION BY client_id, channel, campaign_id, ad_group_id, device ORDER BY date ROWS BETWEEN 27 PRECEDING AND CURRENT ROW)
)

SELECT
  client_id,
  date,
  channel,
  campaign_id,
  ad_group_id,
  device,
  spend,
  clicks,
  impressions,
  sessions,
  conversions,
  revenue,
  roas,
  cpa,
  ctr,
  conversion_rate,
  roas_7d_avg,
  revenue_7d_avg,
  roas_28d_avg,
  revenue_28d_avg,
  SAFE_DIVIDE(roas - roas_7d_avg, NULLIF(roas_7d_avg, 0)) AS roas_pct_delta_7d,
  SAFE_DIVIDE(revenue - revenue_7d_avg, NULLIF(revenue_7d_avg, 0)) AS revenue_pct_delta_7d,
  SAFE_DIVIDE(roas - roas_28d_avg, NULLIF(roas_28d_avg, 0)) AS roas_pct_delta_28d,
  SAFE_DIVIDE(revenue - revenue_28d_avg, NULLIF(revenue_28d_avg, 0)) AS revenue_pct_delta_28d
FROM with_baselines
);
