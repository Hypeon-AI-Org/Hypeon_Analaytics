# Hypeon Analytics — Cleanup + Copilot Rebuild Summary

## Protected datasets (.env 18–19)

**Never delete:**

- `ADS_DATASET=146568`
- `GA4_DATASET=analytics_444259275`

All cleanup scripts and logic skip these (and any `analytics_*` / `raw_*`).

---

## 1. BigQuery cleanup (Step 1)

- **Script:** `bq_sql/cleanup_derived_datasets.sql` (commented DROP examples).
- **Safe list script:** `backend/scripts/list_derived_datasets.py`  
  - Reads `.env` for `ADS_DATASET` and `GA4_DATASET`.
  - Lists all datasets in `BQ_PROJECT`, excludes protected ones, prints `DROP SCHEMA ... CASCADE` for the rest.
  - **Deleted datasets (examples only; run script to get actual list):**  
    `analytics_cache`, `ads_daily_staging`, `ga4_daily_staging`, `unified_tables`, `decision_store`, `marts_old`, `reporting`, `dashboard_cache`, `temp_analytics`, etc.

---

## 2. New marts layer (Steps 2–5)

- **Dataset:** `hypeon_marts` (create via `bq_sql/hypeon_marts/00_create_dataset.sql` or migrations).
- **Staging:**  
  - `stg_ga4__events` — GA4 events flattened with `UNNEST(items)`; partition by `event_date`.  
  - `stg_google_ads__performance` — normalized Ads performance (`cost_micros/1e6`, `channel='google_ads'`).
- **Intermediate:** `int_sessions` — session_id, user_pseudo_id, utm_source, utm_campaign, event_name, item_id, event_timestamp.
- **Marts:**  
  - `fct_sessions` — session_id, event_time, event_name, user_pseudo_id, utm_source, utm_campaign, item_id, device.  
  - `fct_ad_spend` — unified ad performance (future channels append here).

**Run migrations:**  
`python backend/scripts/run_hypeon_marts_migrations.py`  
(Substitutes `BQ_PROJECT`, `BQ_SOURCE_PROJECT`, `GA4_DATASET`, `ADS_DATASET` from `.env`.)

---

## 3. Example generated SQL (Copilot → run_sql)

```sql
SELECT COUNT(*) AS views_count
FROM `{BQ_PROJECT}.hypeon_marts.fct_sessions`
WHERE event_name = 'view_item'
  AND item_id LIKE 'FT05B%'
  AND (utm_source LIKE '%google%' OR LOWER(COALESCE(utm_source,'')) = 'google')
```

---

## 4. Copilot response format

**Response shape (no charts/funnels/cards):**

```json
{
  "answer": "There were 14,200 view_item events for item IDs starting with FT05B from Google in the selected period.",
  "data": [
    { "views_count": 14200 }
  ],
  "session_id": "..."
}
```

Frontend shows `answer` as text and `data` as a table (no dashboard widgets).

---

## 5. Query latency

- **Target:** Single SELECT on `hypeon_marts.fct_sessions` / `fct_ad_spend`: typically **&lt; 3 s** for moderate date ranges and limits.
- **Cap:** `run_readonly_query` uses `timeout_sec=15`, `max_rows=500`, `maximum_bytes_billed=100 MB`.

---

## 6. Cost estimate

- **BigQuery:** Queries against marts/views only; no full raw scans per chat if filters (e.g. `event_date`, `item_id` prefix) are used. Rough order: **&lt; $0.01 per 100 Copilot queries** at 100 MB cap and typical filters.
- **LLM:** Per turn (Gemini/Claude): on the order of **$0.001–0.01** depending on model and token count.

---

## Architecture (end state)

```
BigQuery Raw (ADS_DATASET=146568, GA4_DATASET=analytics_444259275)
    → hypeon_marts (staging → intermediate → marts)
    → Copilot (schema injection from hypeon_marts.INFORMATION_SCHEMA, run_sql, answer + data)
```

Single analytics interface: **Copilot over hypeon_marts**.
