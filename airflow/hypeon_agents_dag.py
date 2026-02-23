"""
HypeOn Analytics V1 agents DAG.
Runs nightly: unified table job, then daily agents. Optional hourly anomaly task.
Deploy to Cloud Composer; or use Cloud Scheduler + Cloud Run for each job.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.utils.task_group import TaskGroup

# Default args: retries, retry_delay, notification
DEFAULT_ARGS = {
    "owner": "hypeon-analytics",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Project/dataset from Airflow variables or env (set in Composer)
BQ_PROJECT = "{{ var.value.get('bq_project', 'braided-verve-459208-i6') }}"
ANALYTICS_DATASET = "{{ var.value.get('analytics_dataset', 'analytics') }}"
ADS_DATASET = "{{ var.value.get('ads_dataset', '146568') }}"
GA4_DATASET = "{{ var.value.get('ga4_dataset', 'analytics_444259275') }}"


def _run_unified_table_script():
    """Run unified table via Python script (assume script on worker path)."""
    import subprocess
    import os
    from pathlib import Path
    # In Composer, repo may be mounted or synced; adjust path as needed
    repo = os.environ.get("HYPEON_REPO_PATH", "/home/airflow/gcs/dags/hypeon-analytics")
    script = Path(repo) / "backend" / "scripts" / "run_unified_table.py"
    if not script.exists():
        # Fallback: run inline BigQuery job (read SQL from GCS or embedded)
        raise FileNotFoundError(f"Script not found: {script}. Set HYPEON_REPO_PATH or sync repo.")
    subprocess.run([os.environ.get("PYTHON", "python"), str(script)], check=True, cwd=repo)


def _run_agents_script():
    """Run agents via run_agents.py."""
    import subprocess
    import os
    from pathlib import Path
    repo = os.environ.get("HYPEON_REPO_PATH", "/home/airflow/gcs/dags/hypeon-analytics")
    script = Path(repo) / "agents" / "run_agents.py"
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")
    subprocess.run([os.environ.get("PYTHON", "python"), str(script)], check=True, cwd=repo)


def _run_anomaly_detector():
    """Run BQ ML anomaly scoring (run_anomaly_scoring.py) then anomaly_agent to write insights."""
    import subprocess
    import os
    from pathlib import Path
    repo = os.environ.get("HYPEON_REPO_PATH", "/home/airflow/gcs/dags/hypeon-analytics")
    scoring = Path(repo) / "backend" / "scripts" / "run_anomaly_scoring.py"
    agent = Path(repo) / "agents" / "anomaly_agent.py"
    if scoring.exists():
        subprocess.run([os.environ.get("PYTHON", "python"), str(scoring)], check=True, cwd=repo)
    if agent.exists():
        subprocess.run([os.environ.get("PYTHON", "python"), str(agent)], check=True, cwd=repo)


with DAG(
    dag_id="hypeon_agents_v1",
    default_args=DEFAULT_ARGS,
    description="HypeOn Analytics V1: unified table + agents + optional anomaly",
    schedule_interval="0 6 * * *",  # 06:00 UTC daily
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["hypeon", "analytics"],
) as dag:

    run_unified_table = PythonOperator(
        task_id="run_unified_table",
        python_callable=_run_unified_table_script,
    )

    run_agents = PythonOperator(
        task_id="run_agents",
        python_callable=_run_agents_script,
    )

    run_anomaly = PythonOperator(
        task_id="run_anomaly_detector",
        python_callable=_run_anomaly_detector,
    )

    run_unified_table >> run_agents
    # Optional: run_agents >> run_anomaly (or run_anomaly on separate schedule)
