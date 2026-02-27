-- Marts: unified ad performance. Future channels (Facebook, Shopify) append here.

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts_ads.fct_ad_spend` AS
SELECT
  segments_date AS date,
  campaign_id,
  campaign_name,
  ad_group_id,
  ad_id,
  device,
  network,
  clicks,
  impressions,
  conversions,
  conversion_value,
  cost,
  channel
FROM `{BQ_PROJECT}.hypeon_marts_ads.stg_google_ads__performance`;
