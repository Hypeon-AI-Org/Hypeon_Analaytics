# HypeOn Analytics V1

Attribution-first marketing analytics system with AI Copilot for query-based insights. GCP-native: BigQuery for data and marts, Cloud Run for API. **No automated decision engine.**

## Architecture

```
Data Sources (Ads BQ, GA4 BQ)
    → BigQuery (raw / staging)
    → Unified Metrics Layer (marts: marketing_performance_daily, analytics_insights, etc.)
    → Analytics Cache
    → Dashboards + Copilot (Q&A only)
```

- **Data:** BigQuery (project/datasets from schema; see [bigquery_schema/bigquery_discovery.json](bigquery_schema/bigquery_discovery.json)). To refresh the schema: `python scripts/bigquery_discover.py --project PROJECT --output-dir ./bigquery_schema`. For Copilot: generate [bigquery_schema/copilot_marts_catalog.json](bigquery_schema/copilot_marts_catalog.json) (marts schema + sample rows) with `python scripts/copilot_fetch_marts_catalog.py`; for raw fallback generate [bigquery_schema/raw_copilot_schema.json](bigquery_schema/raw_copilot_schema.json) with `python scripts/copilot_fetch_raw_schema.py` (run periodically, e.g. weekly).
- **Backend:** FastAPI in [backend/app/main.py](backend/app/main.py); JWT/API key auth stub, RBAC (admin, analyst, viewer).
- **Frontend:** React + Tailwind, [frontend/src/InsightsList.jsx](frontend/src/InsightsList.jsx).

## GCP setup

1. **BigQuery**
   - Create dataset (e.g. `analytics`) for unified table and optional insights/marts.
   - Run unified table job (see below).

2. **Environment variables**
   - `BQ_PROJECT` — GCP project for application DB (`marketing_performance_daily`, `analytics_insights`, etc.)
   - `BQ_SOURCE_PROJECT` — optional; GCP project for raw input (Ads + GA4). If unset, defaults to `BQ_PROJECT`.
   - `ANALYTICS_DATASET` — dataset for `marketing_performance_daily` and optional `analytics_insights` (in `BQ_PROJECT`)
   - `ADS_DATASET` — Google Ads dataset (e.g. `146568`)
   - `GA4_DATASET` — GA4 dataset (e.g. `analytics_444259275`)
   - **BigQuery auth (local):** run `gcloud auth application-default login` and leave `GOOGLE_APPLICATION_CREDENTIALS` unset (ADC). **Cloud Run / CI:** set `GOOGLE_APPLICATION_CREDENTIALS` or use workload identity.
   - **Copilot (Gemini):** set `GEMINI_API_KEY` (from [AI Studio](https://aistudio.google.com/app/apikey)) or `ANTHROPIC_API_KEY` for Claude.
   - `BQ_RAW_COPILOT_SCHEMA_PATH` — optional; path to `raw_copilot_schema.json` for Copilot raw fallback. If unset, defaults to `bigquery_schema/raw_copilot_schema.json` under repo root.
   - `BQ_MARTS_CATALOG_PATH` — optional; path to `copilot_marts_catalog.json` (marts datasets, tables, schema, sample rows). If unset, defaults to `bigquery_schema/copilot_marts_catalog.json`. Generate with `python scripts/copilot_fetch_marts_catalog.py`.
   - `BQ_COPILOT_MAX_BYTES_BILLED_MB` — optional; max bytes billed for Copilot marts queries (default 300). Clamped 50–1024 MB. Increase if fct_sessions queries with date filter still hit the limit.
   - `BQ_COPILOT_RAW_MAX_BYTES_BILLED_MB` — optional; max bytes billed for Copilot raw fallback queries (default 200). Clamped 50–1024 MB.
   - `API_KEY` — optional; if set, requests use `X-API-Key` header
   - `CORS_ORIGINS` — comma-separated origins for frontend

3. **Cloud Run**
   - Build and deploy backend: `docker build -t gcr.io/PROJECT/hypeon-backend -f backend/Dockerfile .` then push and deploy.
   - Set the env vars above in the Cloud Run service.

## Running and validating

1. **Unified table**
   - `python backend/scripts/run_unified_table.py` (or run via DAG / Cloud Scheduler).
   - Validate: In BigQuery, `SELECT * FROM your_project.analytics.marketing_performance_daily LIMIT 10`.

2. **API**
   - Local: `uvicorn backend.app.main:app --reload` from repo root (with `PYTHONPATH=.`).
   - Call `GET /insights?limit=10` with header `X-API-Key: your-key`; `POST /copilot/query` with `{"insight_id": "..."}`; `POST /api/v1/copilot/chat` for chat.

3. **Frontend**
   - `cd frontend && npm install && npm run dev`. Set `VITE_API_BASE` to backend URL if not proxied.

## Repository structure

- `bq_sql/` — BigQuery DDL ([bq_sql/README.md](bq_sql/README.md))
- `backend/` — FastAPI app, copilot_synthesizer, chat_handler, clients (BigQuery), analytics cache
- `frontend/` — React dashboard and Copilot UI
- `monitoring/` — Alerting config ([monitoring/README.md](monitoring/README.md))

## API overview

- **Dashboard (cache):** `GET /api/v1/dashboard/business-overview`, `campaign-performance`, `funnel`
- **Analytics:** `GET /insights`, `GET /insights/top`, `POST /insights/{id}/review`, `POST /insights/{id}/apply`
- **Copilot:** `POST /api/v1/copilot/chat` (LLM + run_sql over marts, run_sql_raw over GA4/Ads raw when needed), `POST /copilot/query`, `POST /copilot/stream`
- **Health:** `GET /health`, `GET /health/analytics`
- **Admin:** `POST /api/v1/admin/refresh-cache`

All queries scoped by `X-Organization-Id`. No decision store; no automated agents.

## Copilot

- **Chat** (`POST /api/v1/copilot/chat`): Marts-first, raw fallback. Answers user questions using LLM + **run_sql** (primary: hypeon_marts, hypeon_marts_ads) and **run_sql_raw** (fallback: GA4 events_*, Ads ads_AccountBasicStats_*) when marts don't have the data. Schema comes from live INFORMATION_SCHEMA plus optional `bigquery_schema/copilot_marts_catalog.json` (schema + sample rows; generate with `python scripts/copilot_fetch_marts_catalog.py`). Raw schema/samples from `bigquery_schema/raw_copilot_schema.json`; generate with `python scripts/copilot_fetch_raw_schema.py` (run periodically). Supports questions like "views count of item ID starting with X coming from Google" (fct_sessions: event_name, item_id, utm_source; always add a date filter to limit scan).
- **Insight explain** (`POST /copilot/query`, `POST /copilot/stream`): Grounded synthesis from `analytics_insights` and `supporting_metrics_snapshot` only (marts layer). Does not reference any decision tables.

## Ops

See [ops.md](ops.md) for runbooks, incident handling, and scaling.
