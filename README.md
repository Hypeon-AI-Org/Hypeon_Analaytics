# HypeOn Analytics V1

Enterprise-grade AI Decision Intelligence platform for e-commerce marketers. GCP-native: BigQuery for data and insights, Cloud Run for API and agents, Cloud Composer for orchestration.

## Architecture

```
Sources (Ads BQ, GA4 BQ)
    → marketing_performance_daily (unified table)
    → Rules engine + Agents → analytics_insights
    → BQ ML anomaly → anomaly_flags → anomaly_agent → analytics_insights
FastAPI (Cloud Run) ← analytics_insights / copilot / simulate
    ← React InsightsList (frontend)
```

- **Data:** BigQuery (project/datasets from schema; see [bigquery_schema/bigquery_discovery.json](bigquery_schema/bigquery_discovery.json)). To refresh the schema: `python scripts/bigquery_discover.py --project PROJECT --output-dir ./bigquery_schema`.
- **Orchestration:** Airflow DAG in [airflow/hypeon_agents_dag.py](airflow/hypeon_agents_dag.py) (Cloud Composer) or Cloud Scheduler + Cloud Run jobs.
- **Backend:** FastAPI in [backend/app/main.py](backend/app/main.py); JWT/API key auth stub, RBAC (admin, analyst, viewer).
- **Frontend:** React + Tailwind, [frontend/src/InsightsList.jsx](frontend/src/InsightsList.jsx).

## GCP setup

1. **BigQuery**
   - Create dataset (e.g. `analytics`) for unified table and insights.
   - Run [bq_sql/create_decision_store.sql](bq_sql/create_decision_store.sql) (substitute `{BQ_PROJECT}`, `{ANALYTICS_DATASET}`).
   - Run unified table job (see below).

2. **Environment variables**
   - `BQ_PROJECT` — GCP project ID
   - `ANALYTICS_DATASET` — dataset for `marketing_performance_daily` and `analytics_insights`
   - `ADS_DATASET` — Google Ads dataset (e.g. `146568`)
   - `GA4_DATASET` — GA4 dataset (e.g. `analytics_444259275`)
   - `GOOGLE_APPLICATION_CREDENTIALS` — path to service account key JSON
   - `API_KEY` — optional; if set, requests use `X-API-Key` header
   - `RULES_CONFIG_PATH` — optional; path to [rules_config.json](rules_config.json) (default: repo root)
   - `CORS_ORIGINS` — comma-separated origins for frontend

3. **Cloud Run**
   - Build and deploy backend: `docker build -t gcr.io/PROJECT/hypeon-backend -f backend/Dockerfile .` then push and deploy.
   - Set the env vars above in the Cloud Run service.

4. **Cloud Composer (Airflow)**
   - Upload DAGs from [airflow/](airflow/) to the Composer DAG bucket.
   - Set Airflow variables: `bq_project`, `analytics_dataset`, `ads_dataset`, `ga4_dataset`.
   - Set `HYPEON_REPO_PATH` to the path where the repo is synced (e.g. GCS-mounted path).

## Running and validating in GCP

1. **Unified table**
   - `python backend/scripts/run_unified_table.py` (or run via DAG / Cloud Scheduler).
   - Validate: In BigQuery, `SELECT * FROM your_project.analytics.marketing_performance_daily LIMIT 10`.

2. **Decision Store**
   - `python backend/scripts/run_decision_store.py` to create `analytics_insights` and view.

3. **Agents**
   - `python agents/run_agents.py` (set `RUN_DATE`, `CLIENT_IDS` if needed).
   - Validate: Query `analytics_insights` or call `GET /insights` on the API.

4. **API**
   - Local: `uvicorn backend.app.main:app --reload` from repo root (with `PYTHONPATH=.`).
   - Call `GET /insights?limit=10` with header `X-API-Key: your-key`; `POST /copilot_query` with `{"insight_id": "..."}`.

5. **Frontend**
   - `cd frontend && npm install && npm run dev`. Set `VITE_API_BASE` to backend URL if not proxied.

## Adding or editing rules

Edit [rules_config.json](rules_config.json). Each rule has:
- `id`, `name`, `insight_type`
- `condition`: `metric`, `op` (eq, lt, gt), `value`, optional `min_spend` / `min_sessions`
- `summary_template`, `explanation_template`, `recommendation_template` (use `{entity_id}`, `{spend}`, `{revenue}`, etc.)

No redeploy needed for rule changes; the rules engine reads the file at runtime.

## Extending agents

- New rule types: add an entry to `rules_config.json` and ensure the rules engine’s condition logic supports the metric/op.
- New agent: add a module under [agents/](agents/) that calls `backend.app.rules_engine.generate_insights` or reads BQ and writes to `analytics_insights`; then add a task in [airflow/hypeon_agents_dag.py](airflow/hypeon_agents_dag.py).

## Repository structure

- `bq_sql/` — BigQuery DDL and ML ([bq_sql/README.md](bq_sql/README.md))
- `backend/` — FastAPI app, rules_engine, copilot_synthesizer, simulation, clients
- `agents/` — performance, trend, funnel, opportunity, anomaly agents; run_agents.py
- `airflow/` — DAG for Cloud Composer
- `frontend/` — React InsightsList
- `monitoring/` — Alerting config ([monitoring/README.md](monitoring/README.md))
- `rules_config.json` — Rule definitions

## Ops

See [ops.md](ops.md) for runbooks, incident handling, and scaling.
