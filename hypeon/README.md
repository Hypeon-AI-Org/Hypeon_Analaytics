# HypeOn Product Engine

Backend product intelligence, modeling, rules, and decision outputs for HypeOn Analytics v1. Data is assumed to be delivered as CSVs into `data/raw/` by another team. No frontend, no data-pipeline connectors, no synthetic data generator.

## Setup

- **Python 3.11+**
- **PostgreSQL** (local or via Docker)
- Create a virtualenv and install: `pip install -e ".[dev]"`

## Database

**Postgres with Docker (recommended)** — uses host port **5433** to avoid conflict with a local Postgres on 5432:

```bash
docker compose -f infra/compose/docker-compose.yml up -d postgres
```

Then set `DATABASE_URL=postgresql://postgres:postgres@localhost:5433/hypeon` and run migrations (see below).

**Or** use a local Postgres and set `DATABASE_URL` (default: `postgresql://postgres:postgres@localhost:5432/hypeon`).

**Run migrations:**

```bash
# From hypeon/ (Windows PowerShell example)
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5433/hypeon"   # or 5432 if local
$env:PYTHONPATH = "."
python -m alembic -c infra/migrations/alembic.ini upgrade head
```

On macOS/Linux: `./scripts/setup_db.sh` (or set `DATABASE_URL` and run the `alembic` command above).

## Sample data

To generate 90 days of realistic sample data (Meta + Google campaigns, Shopify orders):

```bash
python scripts/generate_sample_data.py
```

Writes `data/raw/meta_ads.csv`, `google_ads.csv`, `shopify_orders.csv` (date range 2025-01-01 to 2025-03-31). Then run the pipeline (or use the Dashboard **Run pipeline** button).

## Run pipeline

From repo root (e.g. `hypeon/`):

```bash
./scripts/run_product_engine.sh --seed 42
```

This will:

1. Upsert CSVs from `data/raw/` into raw tables
2. Run attribution → MMM → metrics → rules
3. Write results to `attribution_events`, `mmm_results`, `unified_daily_metrics`, `decision_store`

## Run API

**With Docker (Postgres + API):**

```bash
docker-compose -f infra/compose/docker-compose.yml up --build
```

Then open http://localhost:8000/docs.

**Local (uvicorn):**

```bash
# If using Docker Postgres (port 5433):
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/hypeon
# Or local Postgres on 5432:
# export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hypeon
export PYTHONPATH=.   # or path to hypeon repo root
uvicorn apps.api.src.app:app --reload --host 0.0.0.0 --port 8000
```

## Sample API usage

- **Liveness:** `curl http://localhost:8000/health`
- **Unified metrics:** `curl "http://localhost:8000/metrics/unified?start_date=2025-01-01&end_date=2025-01-31"`
- **Decisions:** `curl http://localhost:8000/decisions`
- **Trigger pipeline:** `curl -X POST "http://localhost:8000/run?seed=42"`
- **MMM status:** `curl http://localhost:8000/model/mmm/status`
- **MMM results:** `curl http://localhost:8000/model/mmm/results`
- **Budget optimizer:** `curl "http://localhost:8000/optimizer/budget?total_budget=1000"`
- **Simulate spend changes:** `curl -X POST http://localhost:8000/simulate -H "Content-Type: application/json" -d "{\"meta_spend_change\": 0.2, \"google_spend_change\": -0.1}"`
- **Attribution vs MMM report:** `curl http://localhost:8000/report/attribution-mmm-comparison`

## Tests

```bash
pytest packages apps tests -v
```

## Architecture

See [design/arch.md](design/arch.md) for a one-page design and data flow.
