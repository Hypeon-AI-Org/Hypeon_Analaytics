-- =============================================================================
-- BigQuery cleanup: DROP derived datasets only. RAW datasets are NEVER deleted.
-- =============================================================================
-- PROTECTED (do not drop; from .env):
--   ADS_DATASET   = 146568
--   GA4_DATASET   = analytics_444259275
-- Also keep any dataset matching: analytics_* (GA4 raw), raw_*
-- =============================================================================
-- Usage: Run list_derived_datasets.py first to see what would be dropped, then
-- run the generated DROP statements below (or via script) after review.
-- =============================================================================

-- Example DROP statements for common derived dataset names.
-- Remove or comment out any line if that dataset should be kept.
-- Replace @BQ_PROJECT@ with your BQ project (e.g. hypeon-ai-prod).

-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.analytics_cache` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.ads_daily_staging` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.ga4_daily_staging` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.unified_tables` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.decision_store` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.marts_old` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.reporting` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.dashboard_cache` CASCADE;
-- DROP SCHEMA IF EXISTS `@BQ_PROJECT@.temp_analytics` CASCADE;

-- NEVER run DROP on:
--   `project.146568`           (ADS_DATASET)
--   `project.analytics_444259275` (GA4_DATASET)
--   any `project.analytics_*` or `project.raw_*`
