# Running the Copilot questions (script or browser)

## Questions list

The full list of questions is in `backend/scripts/run_copilot_questions.py` (variable `QUESTIONS`). They cover:

- **Product analytics:** Pareto revenue, volume vs profit, new product launch, 14-day spike, basket/co-purchase
- **Attribution:** True ROAS vs claimed, new vs recycled customers, channel path, days to purchase, campaign scale/pause
- **LTV & cohorts:** 90-day LTV by channel, repeat purchase, churn risk, top 10% spenders
- **Geo & device:** Cities/countries funnel, mobile vs desktop CVR
- **Landing & funnel:** Landing pages that drive revenue, checkout drop-off (paid vs organic)

## Option A: Browser (recommended)

1. **Start backend** (from repo root):
   ```powershell
   cd backend
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```
2. **Start frontend:**
   ```powershell
   cd frontend
   npm run dev
   ```
3. Open **http://localhost:5173**, sign in with **test@hypeon.ai** / **test@123**.
4. Go to **Copilot** and paste or type each question. Answers and charts appear in the UI.

Backend logs (in the terminal where uvicorn runs) show each request and any errors.

## Option B: Script (batch answers)

The script `backend/scripts/run_copilot_questions.py` calls the Copilot API with `X-API-Key` and `X-Organization-Id: org_test`. It requires the backend to accept that API key.

**If you get 401 Unauthorized:** the uvicorn worker may not have `API_KEY` in its environment. Do one of:

- **Start backend with .env loaded and without `--reload`** (single process keeps env):
  ```powershell
  cd Hypeon_Analaytics
  Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#=]+)=(.*)$') { $n=$matches[1].Trim(); $v=$matches[2].Trim()-replace'^["'']|["'']$'; [Environment]::SetEnvironmentVariable($n,$v,'Process') } }
  cd backend
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
  ```
  Then in another terminal:
  ```powershell
  cd Hypeon_Analaytics
  python -m backend.scripts.run_copilot_questions
  ```
  Answers are written to `docs/ai-tasks/copilot_answers.md`.

- **Run only the first N questions:**
  ```powershell
  python -m backend.scripts.run_copilot_questions --max 5
  ```

## Backend logs

- In the terminal where uvicorn runs you’ll see: request method/path, status, duration, and any DEBUG logs.
- Copilot flow: analyzing → discovering tables → generating SQL → running query → formatting. Any exception is logged there.
- To confirm API key is used: `GET http://localhost:8001/api/v1/debug-auth` with header `X-API-Key: <your API_KEY>` should return `"key_match": true` when the backend has the same key.
