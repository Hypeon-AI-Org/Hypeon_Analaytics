# Copilot "Queries tried: none" – why it happens and how to fix

## What it means

**"I couldn't find relevant data for that question. Queries tried: none."** means:

1. The Copilot **did** find tables for your org (discovery worked).
2. The planner returned **candidate tables** (so the "no tables in the warehouse" path was not taken).
3. **No SQL was ever run** because the LLM never returned a query that could be extracted.

So the failure is between "Writing SQL query…" and "Running query…": the model either returned no text, threw an error, or returned text that didn’t contain a valid `SELECT`/`WITH` (e.g. an explanation or refusal).

## What to check in backend logs

With the new logging you should see one or more of:

- **`Copilot early exit: get_allowed_tables_set returned 0 tables`**  
  → No BigQuery tables for this org. Fix: ensure org has project/datasets in Firestore and schema cache has been populated (or discovery runs).

- **`Copilot no candidates | intent=...`**  
  → Discovery returned no tables for this question. Fix: check `list_tables_for_discovery` and org BQ config.

- **`Copilot discovered N candidate tables ...`**  
  → Discovery is fine; next step is SQL generation.

- **`Claude SQL generation failed: ...` or `Gemini SQL generation failed: ...`**  
  → LLM call failed (auth, rate limit, network). Fix: check API keys and provider status.

- **`Copilot LLM returned text but no SQL could be extracted (len=...). Preview: ...`**  
  → The model answered, but the reply didn’t contain parseable SQL (e.g. "I don’t see a revenue column" or prose only). The **Preview** shows the start of that reply so you can adjust schema/prompt or question.

- **`Copilot LLM returned no SQL on attempt N`**  
  → After all retries, no SQL was extracted. If you also see the "no SQL could be extracted" line above, the model is refusing or explaining instead of outputting SQL.

## Typical causes

1. **Question doesn’t match the schema**  
   e.g. "Top 10 product IDs by revenue" but your tables are GA4/Meta/Pinterest without clear `product_id`/`revenue` columns. The model may refuse or explain instead of writing a query.  
   **Fix:** Rephrase for your actual schema (e.g. "top events by count", "spend by campaign") or add datasets that have product/revenue.

2. **Schema cache empty or stale**  
   So the model gets no (or wrong) table/column list.  
   **Fix:** Trigger schema refresh for the org so the cache has the right tables and columns.

3. **LLM returns explanation instead of SQL**  
   The prompt asks for "only the SQL query", but the model still sometimes returns a paragraph. The new "Preview" log shows that.  
   **Fix:** If it keeps happening, the system prompt/instructions may need to be tightened for your use case.

## Quick check

Run one question and watch the backend (uvicorn) logs. You should see in order:

1. `Copilot chat | org_id=...`
2. `Copilot discovered N candidate tables ...`
3. Either `Copilot success | ...` or one of the warning messages above.

That tells you whether the failure is discovery, SQL generation, or execution.
