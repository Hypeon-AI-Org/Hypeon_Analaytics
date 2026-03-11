# Comparing Copilot answers with BigQuery

This describes how to validate Copilot answers by running equivalent BigQuery queries and comparing results.

## 1. gcloud auth

Use Application Default Credentials so the script can call BigQuery:

```bash
gcloud auth application-default login
```

If you use a specific project:

```bash
gcloud config set project hypeon-ai-prod
gcloud auth application-default login
```

Ensure you have **BigQuery Data Viewer** (or similar) on the projects used by org_test: `hypeon-ai-prod` (pinterest, meta_ads) and `braided-verve-459208-i6` (GA4).

## 2. Run the comparison script

From the repo root:

```bash
python scripts/compare_copilot_with_bq.py
```

Options:

- `--copilot-file docs/ai-tasks/copilot_answers.md` — path to Copilot answers (default).
- `--out docs/ai-tasks/copilot_validation_report.md` — where to write the comparison report (default).
- `--skip-auth-check` — skip credential check (e.g. in CI with a service account).

The script:

1. Parses `copilot_answers.md` and extracts key metrics (e.g. Q1 total revenue, Q6 campaign count).
2. Runs equivalent read-only BigQuery queries against the same datasets.
3. Writes `copilot_validation_report.md` with expected vs actual and match/mismatch.

## 3. Fetching answers manually (without the script)

You can also run queries yourself and compare to the Copilot file:

1. **bq CLI** (after `gcloud auth application-default login`):

   ```bash
   bq query --use_legacy_sql=false --format=prettyjson \
     'SELECT SUM(Total_order_value_Checkout) AS total FROM `hypeon-ai-prod.pinterest.metrics_2025_01_01_to_2026_03_08`'
   ```

2. **BigQuery Console**: open [console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery), pick project and dataset, run the same SQL, and compare the result to the numbers in `copilot_answers.md`.

3. **Python one-off**:

   ```python
   from google.cloud import bigquery
   client = bigquery.Client(project="hypeon-ai-prod")
   job = client.query("SELECT SUM(Total_order_value_Checkout) AS total FROM `hypeon-ai-prod.pinterest.metrics_2025_01_01_to_2026_03_08`")
   for row in job.result():
       print(row.total)
   ```

Then compare the output to the Copilot answer (e.g. Q1 total revenue **$22,754.37**).

## 4. What the script checks today

- **Q6**: Campaign count (Meta `meta_ads.campaigns` + Pinterest distinct campaign names) vs Copilot’s “58 campaigns”.
- **Q1**: Total revenue from Copilot vs `SUM(Total_order_value_Checkout)` on Pinterest (only comparable if Copilot used the same source).

You can extend `scripts/compare_copilot_with_bq.py` (e.g. in `run_checks` and `parse_copilot_answers`) to add more questions and comparisons.
