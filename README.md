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

- **Data:** BigQuery (project/datasets from schema; see [bigquery_schema/bigquery_discovery.json](bigquery_schema/bigquery_discovery.json)). To refresh the schema: `python scripts/bigquery_discover.py --project PROJECT --output-dir ./bigquery_schema`.
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
- **Copilot:** `POST /api/v1/copilot/chat` (LLM + run_sql over ADS_DATASET / GA4_DATASET), `POST /copilot/query`, `POST /copilot/stream`
- **Health:** `GET /health`, `GET /health/analytics`
- **Admin:** `POST /api/v1/admin/refresh-cache`

All queries scoped by `X-Organization-Id`. No decision store; no automated agents.

## Copilot

- **Chat** (`POST /api/v1/copilot/chat`): Answers user questions using LLM + a single tool **run_sql** against allowed BigQuery datasets (ADS_DATASET, GA4_DATASET). No hardcoded routing; no auto-generated actions.
- **Insight explain** (`POST /copilot/query`, `POST /copilot/stream`): Grounded synthesis from `analytics_insights` and `supporting_metrics_snapshot` only (marts layer). Does not reference any decision tables.

## Ops

See [ops.md](ops.md) for runbooks, incident handling, and scaling.
