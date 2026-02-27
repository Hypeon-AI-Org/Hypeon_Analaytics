# Analytics Data Report

**Generated:** 2026-02-26  
**Purpose:** Assess Google Analytics (GA4), Google Ads, and hypeon-ai-prod analytics dataset for usability.

---

## Configuration (from .env)

| Variable | Value | Role |
|----------|--------|------|
| **BQ_PROJECT** | `hypeon-ai-prod` | Application DB: analytics_insights, decision_history, marketing_performance_daily |
| **BQ_SOURCE_PROJECT** | `braided-verve-459208-i6` | Raw GA4 and Google Ads export data |
| **ANALYTICS_DATASET** | `analytics` | Dataset in hypeon-ai-prod (and staging tables) |
| **GA4_DATASET** | `analytics_444259275` | Raw GA4 BigQuery export dataset (in source project) |
| **ADS_DATASET** | `146568` | Raw Google Ads export dataset (in source project, EU) |

---

## 1. hypeon-ai-prod – Analytics dataset (table row counts)

| Table | Rows | Notes |
|-------|------|--------|
| **marketing_performance_daily** | 465 | Unified table (Ads + GA4 by channel); used by dashboard and Copilot |
| **analytics_insights** | (missing) | Table not found in hypeon-ai-prod; Decision Store not created yet |

---

## 2. Google Analytics (GA4) – Raw events (source project)

**Dataset:** `braided-verve-459208-i6.analytics_444259275.events_*`

| Metric | Value |
|--------|--------|
| **Event count** | 553,674 |
| **Date range** | 2026-02-21 to 2026-02-26 |
| **Conversion events (purchase/conversion)** | 301 |
| **Total revenue (event_value_in_usd)** | ~$40,791 |

**Top event names (sample):** page_view (188,622), view_item (113,503), user_engagement (110,613), session_start (52,021), first_visit (31,654), scroll (30,510), view_item_list (19,077), begin_checkout (3,329), purchase (301).

**Assessment:** Raw GA4 data is present and substantial (6 days, 553K events, 301 purchases). This is enough for pipeline and analysis.

---

## 3. marketing_performance_daily (channel=ga4)

**Table:** `hypeon-ai-prod.analytics.marketing_performance_daily` WHERE channel = 'ga4'

| Metric | Value |
|--------|--------|
| **Row count** | 15 |
| **Date range** | 2026-02-21 to 2026-02-25 |
| **Total spend** | 0 (GA4 has no spend) |
| **Total revenue** | ~$35,198 |
| **Total conversions** | 256 |
| **Total sessions** | 44,336 |

**Sample (last 5 rows):**

| date       | channel | device  | spend | revenue   | conversions | sessions |
|------------|---------|---------|-------|-----------|-------------|----------|
| 2026-02-25 | ga4     | tablet  | 0.0   | 0         | 0           | 72       |
| 2026-02-25 | ga4     | mobile  | 0.0   | 43.44     | 3           | 1,611    |
| 2026-02-25 | ga4     | desktop | 0.0   | 1,309.65  | 6           | 449      |
| 2026-02-24 | ga4     | mobile  | 0.0   | 5,456.50  | 42          | 7,536    |
| 2026-02-24 | ga4     | tablet  | 0.0   | 161.03    | 3           | 316      |

**Assessment:** GA4 rows in unified table; revenue and sessions populated. Limited history for trends and baselines.

---

## 4. Google Ads – Raw (source project, EU)

**Table:** `braided-verve-459208-i6.146568.ads_AdGroupBasicStats_4221201460`

| Metric | Value |
|--------|--------|
| **Row count** | 860 |
| **Date range** | 2026-02-11 to 2026-02-24 |
| **Total spend** | ~$15,161.54 |
| **Total revenue** | ~$24,617.36 |
| **Total clicks** | 40,749 |
| **Total impressions** | 1,784,518 |

**Assessment:** Raw Google Ads data is present and usable (14 days, 860 rows, non-zero spend and revenue).

---

## 5. marketing_performance_daily (channel=google_ads)

**Table:** `hypeon-ai-prod.analytics.marketing_performance_daily` WHERE channel = 'google_ads'

| Metric | Value |
|--------|--------|
| **Row count** | 804 |
| **Date range** | 2026-02-11 to 2026-02-23 |
| **Total spend** | ~$13,900.65 |
| **Total revenue** | ~$24,617.36 |
| **Total clicks** | 37,163 |
| **Total impressions** | 1,613,530 |

**Assessment:** Ads staging is well populated and in sync with raw data; only 1 client_id (1) in sample.

---

## 6. Unified table – marketing_performance_daily (hypeon-ai-prod)

**Table:** `hypeon-ai-prod.analytics.marketing_performance_daily`  
**Used by:** Dashboard API, Copilot, rules engine, anomaly scoring.

| Metric | Value |
|--------|--------|
| **Row count** | 465 |
| **Distinct clients** | 1 |
| **Date range** | 2026-02-11 to 2026-02-25 |
| **Total spend** | ~$13,900.65 |
| **Total revenue** | ~$59,815.43 (Ads + GA4 combined) |
| **Total sessions** | 44,336 |
| **Total conversions** | ~270.67 |

**Assessment:** Unified table is populated and usable for the single client. Revenue combines Ads (~$24.6k) and GA4 (~$35.2k). Limited by short GA4 history (few days) and single client.

---

## 7. Insights data (analytics_insights)

### BigQuery table (hypeon-ai-prod)

**Table:** `hypeon-ai-prod.analytics.analytics_insights`  
**Status:** **Not found** (404 in europe-north2).

The rules engine and agents write insights to this table; Copilot and the dashboard “actions” read from it. When the table is missing, the API returns an empty list for insights.

### Local insights file (you do have this)

**File:** `agents/output/insights_latest.json`  
**Status:** Present. **4 insights** (client_id=1, created 2026-02-23).

| # | insight_type      | entity_id                    | summary (short) |
|---|-------------------|------------------------------|------------------|
| 1 | funnel_leak       | nan_nan                      | High traffic, conversion rate &lt; 1%. |
| 2 | scale_opportunity | 23034602618_192452068704     | ROAS &gt; 20% above 28d baseline. |
| 3 | scale_opportunity | 23034602618_189028062920     | ROAS &gt; 20% above 28d baseline. |
| 4 | scale_opportunity | 23092324681_190231567567     | ROAS &gt; 20% above 28d baseline. |

These were produced by the agents pipeline (rules engine) and written to JSON. The backend can serve them **instead of** BigQuery if you set in `.env`:

```bash
INSIGHTS_JSON_PATH=agents/output/insights_latest.json
```

(Currently this is commented out in `.env`, so the app tries only BigQuery and gets no insights.)

**To use BigQuery for insights:** Run the Decision Store setup in hypeon-ai-prod so the table exists, then run the agents (or rules engine) with write to BQ so insights are written to `analytics_insights` instead of (or in addition to) the JSON file.

---

## Summary: Can we use the current analytics data?

### Yes, with caveats

| Area | Usable? | Notes |
|------|---------|--------|
| **Raw GA4** | Yes | 553K events, 6 days, 301 purchases, ~$40.8k revenue. |
| **Raw Google Ads** | Yes | 860 rows, 14 days, ~$15.2k spend, ~$24.6k revenue. |
| **GA4 staging** | Partial | Only 15 rows (~5 days). Enough for “current” metrics; weak for week-over-week or baselines. |
| **Ads staging** | Yes | 804 rows; good coverage. |
| **marketing_performance_daily** | Yes | 465 rows, 1 client; dashboard and Copilot can use it. |
| **analytics_insights** (BQ) | No | Table missing in hypeon-ai-prod; create Decision Store. |
| **Insights (local JSON)** | Yes | 4 insights in `agents/output/insights_latest.json`; set `INSIGHTS_JSON_PATH` to use them. |

### Gaps and recommendations

1. **GA4 history is short**  
   If GA4 rows in `marketing_performance_daily` are few, run the pipeline regularly so history grows; then 7d/28d baselines and trend analyses will improve.

2. **Single client**  
   All data is `client_id = 1`. Fine for single-tenant; for multi-tenant, ensure Ads/GA4 exports and pipeline use correct client mapping.

3. **Decision Store not in hypeon-ai-prod**  
   Create `analytics_insights` (and related tables/views) in `hypeon-ai-prod.analytics` so insights and recommendations work.

4. **Data is not “empty”**  
   Raw GA4 and Ads have solid volume; hypeon-ai-prod has staging and unified table populated. The main limitations are short GA4 staging history and missing Decision Store, not absence of data.

---

## How to re-run this report

From repo root (with `.env` loaded):

```bash
python backend/scripts/analytics_data_report.py
```

Report is appended to stdout and written to `analytics_data_report.md`.  
Optional: run `backend/scripts/check_ga4_data.py` and `backend/scripts/check_ads_data.py` for more detail on raw and staging data.
