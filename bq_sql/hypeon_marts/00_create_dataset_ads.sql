-- Ads marts dataset in EU (146568 is in EU). Separate from hypeon_marts (europe-north2) for GA4.

CREATE SCHEMA IF NOT EXISTS `{BQ_PROJECT}.hypeon_marts_ads`
OPTIONS(
  location = "{BQ_LOCATION_ADS}",
  description = "Hypeon ad spend marts (EU); sources from ADS_DATASET 146568"
);
