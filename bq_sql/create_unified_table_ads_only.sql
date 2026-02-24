-- Ads-only staging table (run in EU; source dataset 146568 is in EU).
-- Output: BQ_PROJECT.STAGING_EU_DATASET.ads_daily_staging
-- Substitutes: BQ_PROJECT, BQ_SOURCE_PROJECT, ADS_DATASET, STAGING_EU_DATASET

CREATE OR REPLACE TABLE `{BQ_PROJECT}.{STAGING_EU_DATASET}.ads_daily_staging` (
  client_id INT64,
  date DATE,
  channel STRING,
  campaign_id STRING,
  ad_group_id STRING,
  device STRING,
  spend FLOAT64,
  clicks INT64,
  impressions INT64,
  conversions FLOAT64,
  revenue FLOAT64,
  sessions INT64
)
PARTITION BY date
AS (
  -- Map this Ads account to client_id=1 so GA4 and Ads appear under one client
  SELECT
    1 AS client_id,
    segments_date AS date,
    'google_ads' AS channel,
    CAST(campaign_id AS STRING) AS campaign_id,
    CAST(ad_group_id AS STRING) AS ad_group_id,
    COALESCE(segments_device, 'UNKNOWN') AS device,
    SAFE_DIVIDE(COALESCE(metrics_cost_micros, 0), 1e6) AS spend,
    COALESCE(metrics_clicks, 0) AS clicks,
    COALESCE(metrics_impressions, 0) AS impressions,
    COALESCE(metrics_conversions, 0) AS conversions,
    COALESCE(metrics_conversions_value, 0) AS revenue,
    0 AS sessions
  FROM `{BQ_SOURCE_PROJECT}.{ADS_DATASET}.ads_AdGroupBasicStats_4221201460`
  WHERE segments_date IS NOT NULL
    AND customer_id IS NOT NULL
);
