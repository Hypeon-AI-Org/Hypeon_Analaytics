-- Staging: Google Ads performance normalized. Source: ADS_DATASET (ads_* tables).
-- Replace {BQ_PROJECT}, {BQ_SOURCE_PROJECT}, {ADS_DATASET} from .env.
-- Uses ads_AccountStats (account-level); for campaign/ad level use ads_AdGroupBasicStats or similar.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts_ads.stg_google_ads__performance` AS
SELECT
  customer_id AS campaign_id,
  CAST(NULL AS STRING) AS campaign_name,
  CAST(NULL AS INT64) AS ad_group_id,
  CAST(NULL AS INT64) AS ad_id,
  segments_date AS segments_date,
  COALESCE(segments_device, 'UNKNOWN') AS device,
  COALESCE(segments_ad_network_type, '') AS network,
  COALESCE(metrics_clicks, 0) AS clicks,
  COALESCE(metrics_impressions, 0) AS impressions,
  COALESCE(metrics_conversions, 0) AS conversions,
  COALESCE(metrics_conversions_value, 0) AS conversion_value,
  SAFE_DIVIDE(COALESCE(metrics_cost_micros, 0), 1e6) AS cost,
  'google_ads' AS channel
FROM `{BQ_SOURCE_PROJECT}.{ADS_DATASET}.ads_AccountStats_4221201460`
WHERE segments_date IS NOT NULL;
