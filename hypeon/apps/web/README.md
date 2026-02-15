# HypeOn Web (Dashboard + Copilot)

React frontend for HypeOn Analytics: **Dashboard** (for specialists) and **Copilot** (for founders / non-technical users).

## Run locally

1. Start the API (and Postgres) first, e.g. from repo root:
   ```bash
   docker-compose -f infra/compose/docker-compose.yml up --build
   ```
   Or run API with uvicorn and set `DATABASE_URL`.

2. From this directory:
   ```bash
   npm install
   npm run dev
   ```
   Opens at http://localhost:5173. API requests are proxied to http://localhost:8000 via Vite (`/api` → backend).

3. If the API runs on another origin, set:
   ```bash
   VITE_API_URL=http://localhost:8000
   ```
   Then run `npm run dev` (no proxy; CORS must be enabled on the API).

## Build

```bash
npm run build
```
Output in `dist/`. Serve with any static host; set `VITE_API_URL` to your API base URL in production.

## Structure

- **Dashboard** (Overview, Metrics, Decisions, Optimizer, Report): data tables, charts, filters, pipeline trigger.
- **Copilot**: natural-language Q&A over the same data; suggested questions and answer history.
