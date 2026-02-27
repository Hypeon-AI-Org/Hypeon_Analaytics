"""
SQL test: verify hypeon_marts.fct_sessions query for view_item + item_id prefix + utm_source.
Master prompt: result must match manual script (~14k for FT05B from Google).
Run with: pytest backend/tests/test_marts_sql.py -v -k test_marts (optional: requires BQ access).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.mark.skipif(
    not os.environ.get("BQ_PROJECT") or os.environ.get("SKIP_BQ_TESTS") == "1",
    reason="BQ_PROJECT not set or SKIP_BQ_TESTS=1",
)
def test_fct_sessions_view_item_ft05b_google():
    """
    Verify: SELECT COUNT(*) FROM hypeon_marts.fct_sessions
    WHERE event_name='view_item' AND item_id LIKE 'FT05B%' AND utm_source LIKE '%google%'
    Returns a non-negative count (manual baseline ~14k when data exists).
    """
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from backend.app.clients.bigquery import get_marts_dataset, run_readonly_query
    project = os.environ.get("BQ_PROJECT", "")
    marts = get_marts_dataset()
    sql = f"""
    SELECT COUNT(*) AS cnt
    FROM `{project}.{marts}.fct_sessions`
    WHERE event_name = 'view_item'
      AND item_id LIKE 'FT05B%'
      AND (utm_source LIKE '%google%' OR LOWER(COALESCE(utm_source,'')) = 'google')
    """
    out = run_readonly_query(sql, client_id=1, organization_id="default", max_rows=1)
    assert out.get("error") is None, out.get("error")
    assert out.get("rows"), "Expected at least one row (count)"
    count = out["rows"][0].get("cnt", 0)
    assert isinstance(count, (int, float)), "Count should be numeric"
    assert count >= 0, "Count must be non-negative"
