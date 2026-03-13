"""
Sync insight status updates from Firestore to BigQuery.

Write-through pattern: the API writes status changes to Firestore (insight_status_updates)
so the request returns immediately. This script runs as a scheduled job (e.g. Cloud Run
or cron every 5 minutes), reads all docs where synced_to_bq == False, runs the
parameterized BigQuery UPDATE for each, then marks the doc synced_to_bq = True.

Run from repo root: python -m backend.app.scripts.sync_insight_status_to_bq
Or from backend/: PYTHONPATH=. python app/scripts/sync_insight_status_to_bq.py
"""
from __future__ import annotations

import logging
import os
import sys

# Ensure backend.app is importable when run as script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_BACKEND_DIR = os.path.dirname(_APP_DIR)
_REPO = os.path.dirname(_BACKEND_DIR)
for _p in (_REPO, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_sync() -> tuple[int, int]:
    """
    Query Firestore for unsynced insight_status_updates, run BQ UPDATE for each, mark synced.
    Returns (synced_count, failed_count).
    """
    from google.cloud import bigquery

    try:
        from backend.app.auth.firestore_user import _get_firestore
        db = _get_firestore()
    except Exception:
        try:
            from app.auth.firestore_user import _get_firestore
            db = _get_firestore()
        except Exception as e:
            logger.error("Firestore unavailable: %s", e)
            return 0, 0

    if not db:
        logger.error("Firestore client is None")
        return 0, 0

    try:
        from backend.app.config import get_bq_project, get_analytics_dataset
        from backend.app.clients.bigquery import get_client
    except Exception:
        from app.config import get_bq_project, get_analytics_dataset
        from app.clients.bigquery import get_client

    project = get_bq_project()
    dataset = get_analytics_dataset()
    if not project or not dataset:
        logger.error("BQ_PROJECT or ANALYTICS_DATASET not set")
        return 0, 0

    coll = db.collection("insight_status_updates")
    # Firestore does not support != on bool; we query and filter, or use where("synced_to_bq", "==", False)
    try:
        unsynced = list(coll.where("synced_to_bq", "==", False).stream())
    except Exception as e:
        logger.error("Firestore query failed: %s", e)
        return 0, 0

    client = get_client()
    query_template = """
    UPDATE `{project}.{dataset}.analytics_insights`
    SET status = @status, applied_at = CURRENT_TIMESTAMP(), history = CONCAT(COALESCE(history, ''), '; applied_by=', @user, ' at ', @now)
    WHERE insight_id = @insight_id AND organization_id = @organization_id
    """
    query = query_template.format(project=project, dataset=dataset)
    synced = 0
    failed = 0

    for doc in unsynced:
        data = doc.to_dict() or {}
        insight_id = data.get("insight_id") or ""
        organization_id = data.get("organization_id") or ""
        status = data.get("status") or ""
        user = data.get("user_id") or "unknown"
        applied_at = data.get("applied_at") or ""

        if not insight_id or not organization_id:
            logger.warning("Skipping doc %s: missing insight_id or organization_id", doc.id)
            failed += 1
            continue

        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("status", "STRING", status),
                    bigquery.ScalarQueryParameter("user", "STRING", user),
                    bigquery.ScalarQueryParameter("now", "STRING", applied_at),
                    bigquery.ScalarQueryParameter("insight_id", "STRING", insight_id),
                    bigquery.ScalarQueryParameter("organization_id", "STRING", organization_id),
                ]
            )
            client.query(query, job_config=job_config).result()
            doc.reference.update({"synced_to_bq": True})
            synced += 1
        except Exception as e:
            logger.warning("BQ UPDATE failed for doc %s (insight_id=%s): %s", doc.id, insight_id, e)
            failed += 1

    return synced, failed


def main() -> int:
    synced, failed = run_sync()
    logger.info("sync_insight_status_to_bq: synced=%s, failed=%s", synced, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
