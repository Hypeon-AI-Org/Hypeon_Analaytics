-- Build marketing_performance_daily from unified pipeline (run in europe-north2).
-- Source: build from raw Ads/GA4 or from intermediate tables; substitute BQ_PROJECT, ANALYTICS_DATASET.
-- (Legacy: if you still have ads_daily_staging and ga4_daily_staging, the UNION below uses them.)

CREATE OR REPLACE TABLE `{BQ_PROJECT}.{ANALYTICS_DATASET}.marketing_performance_daily`
PARTITION BY date
CLUSTER BY client_id, campaign_id
AS (
WITH unified_raw AS (
  SELECT client_id, date, channel, campaign_id, ad_group_id, device,
    spend, clicks, impressions, conversions, revenue, sessions
  FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ads_daily_staging`
  UNION ALL
  SELECT client_id, date, channel, campaign_id, ad_group_id, device,
    spend, clicks, impressions, conversions, revenue, sessions
  FROM `{BQ_PROJECT}.{ANALYTICS_DATASET}.ga4_daily_staging`
),
unified_agg AS (
  SELECT
    client_id, date, channel, campaign_id, ad_group_id, device,
    SUM(spend) AS spend,
    SUM(clicks) AS clicks,
    SUM(impressions) AS impressions,
    SUM(conversions) AS conversions,
    SUM(revenue) AS revenue,
    SUM(sessions) AS sessions
  FROM unified_raw
  GROUP BY 1, 2, 3, 4, 5, 6
),
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
  client_id, date, channel, campaign_id, ad_group_id, device,
  spend, clicks, impressions, sessions, conversions, revenue,
  roas, cpa, ctr, conversion_rate,
  roas_7d_avg, revenue_7d_avg, roas_28d_avg, revenue_28d_avg,
  SAFE_DIVIDE(roas - roas_7d_avg, NULLIF(roas_7d_avg, 0)) AS roas_pct_delta_7d,
  SAFE_DIVIDE(revenue - revenue_7d_avg, NULLIF(revenue_7d_avg, 0)) AS revenue_pct_delta_7d,
  SAFE_DIVIDE(roas - roas_28d_avg, NULLIF(roas_28d_avg, 0)) AS roas_pct_delta_28d,
  SAFE_DIVIDE(revenue - revenue_28d_avg, NULLIF(revenue_28d_avg, 0)) AS revenue_pct_delta_28d
FROM with_baselines
);
