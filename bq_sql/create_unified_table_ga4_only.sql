-- GA4-only staging table (run in europe-north2; source dataset is in europe-north2).
-- Output: BQ_PROJECT.ANALYTICS_DATASET.ga4_daily_staging
-- Substitutes: BQ_PROJECT, BQ_SOURCE_PROJECT, GA4_DATASET, ANALYTICS_DATASET

CREATE OR REPLACE TABLE `{BQ_PROJECT}.{ANALYTICS_DATASET}.ga4_daily_staging` (
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
  SELECT
    1 AS client_id,
    PARSE_DATE('%Y%m%d', event_date) AS date,
    'ga4' AS channel,
    CAST(NULL AS STRING) AS campaign_id,
    CAST(NULL AS STRING) AS ad_group_id,
    COALESCE(device.category, 'UNKNOWN') AS device,
    0 AS spend,
    0 AS clicks,
    0 AS impressions,
    COUNTIF(event_name = 'purchase' OR event_name = 'conversion') AS conversions,
    COALESCE(SUM(COALESCE(event_value_in_usd, 0)), 0) AS revenue,
    COUNTIF(event_name = 'session_start') AS sessions
  FROM `{BQ_SOURCE_PROJECT}.{GA4_DATASET}.events_*`
  WHERE event_date IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6
);
