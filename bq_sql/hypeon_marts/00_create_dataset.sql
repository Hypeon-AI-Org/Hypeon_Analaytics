-- Create hypeon_marts dataset (RAW -> STAGING -> INTERMEDIATE -> MARTS -> COPILOT)
-- Location must match GA4 (europe-north2) / Ads (EU) so views can reference them.

CREATE SCHEMA IF NOT EXISTS `{BQ_PROJECT}.hypeon_marts`
OPTIONS(
  location = "{BQ_LOCATION}",
  description = "Hypeon marts layer: staging, intermediate, and fact tables for Copilot"
);
