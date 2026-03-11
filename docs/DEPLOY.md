# Deployment checklist

Use this checklist to deploy HypeOn Analytics to production (e.g. Cloud Run).

## Environment variables (production)

Set these on your backend service (e.g. Cloud Run env vars or Secret Manager):

| Variable | Required | Notes |
|----------|----------|--------|
| `ENV` | Yes | Set to `production` (rejects `dev-local-secret`; use Bearer or real API_KEY). |
| `API_KEY` | Yes | Strong secret for `X-API-Key` header; never use `dev-local-secret` in prod. |
| `CORS_ORIGINS` | Yes | Comma-separated frontend origins, e.g. `https://app.example.com`. |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project for Auth + Firestore. |
| `FIRESTORE_DATABASE_ID` | Optional | Default `(default)`; use e.g. `hypeon-analytics` if you use a named database. |
| `LOG_LEVEL` | Recommended | Set to `INFO` (avoid `DEBUG` in production). |
| `GOOGLE_CLOUD_PROJECT` | Recommended | Same as Firebase project; used when using ADC. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Cloud Run/CI | Path to service account JSON or use workload identity. |
| `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` | For Copilot | At least one for Copilot LLM. |

Frontend (build-time or runtime via `window.__APP_CONFIG__`): `VITE_API_BASE` (API URL), `VITE_API_KEY`, and all `VITE_FIREBASE_*` from Firebase Console.

## Build and run

1. **Backend image** (from repo root):
   ```bash
   docker build -f backend/Dockerfile -t your-registry/backend:latest .
   ```

2. **Frontend image** (build assets first, then image):
   ```bash
   cd frontend && npm ci && npm run build && cd ..
   docker build -f frontend/Dockerfile -t your-registry/frontend:latest ./frontend
   ```

3. Ensure `.env` is never copied into images (`.dockerignore` already excludes `.env`, `.env.*`).

4. Run backend with `PORT` set (e.g. 8080 for Cloud Run). Run frontend behind a reverse proxy or static host; set backend URL via `VITE_API_BASE` or runtime config.

## Pre-deploy checks

- [ ] `ENV=production` set on backend.
- [ ] `API_KEY` set and not `dev-local-secret`.
- [ ] `CORS_ORIGINS` includes your frontend origin(s) only.
- [ ] Firebase project has Firestore enabled; service account has Firestore + Auth permissions.
- [ ] Frontend build uses correct `VITE_API_BASE` (or inject at runtime) and Firebase config.
