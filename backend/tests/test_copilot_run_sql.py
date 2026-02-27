"""
Tests for Copilot run_sql + knowledge base: run_readonly_query validation,
execute_tool run_sql, knowledge_base, and chat_handler system template.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Repo root
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ----- run_readonly_query (bigquery.py) -----


@pytest.fixture
def env_bq():
    """Set BQ_PROJECT, ADS_DATASET, GA4_DATASET for Copilot run_sql validation (single dataset 'analytics' for both)."""
    with patch.dict(
        "os.environ",
        {"BQ_PROJECT": "test-proj", "ADS_DATASET": "analytics", "GA4_DATASET": "analytics"},
        clear=False,
    ):
        yield


@pytest.fixture
def env_raw():
    """Raw datasets only: ADS_DATASET and GA4_DATASET distinct (e.g. 146568, analytics_444259275)."""
    with patch.dict(
        "os.environ",
        {
            "BQ_PROJECT": "test-proj",
            "BQ_SOURCE_PROJECT": "test-proj",
            "ADS_DATASET": "146568",
            "GA4_DATASET": "analytics_444259275",
        },
        clear=False,
    ):
        yield


def test_run_readonly_query_empty_sql(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    out = run_readonly_query("", client_id=1, organization_id="default")
    assert out["rows"] == []
    assert out["error"] == "Empty query."


def test_run_readonly_query_whitespace_only(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    out = run_readonly_query("   \n\t  ", client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "Empty" in (out["error"] or "")


def test_run_readonly_query_multi_statement_rejected(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT 1; SELECT 2"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "single" in (out["error"] or "").lower() and "select" in (out["error"] or "").lower()


def test_run_readonly_query_trailing_semicolon_allowed(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT 1 AS x;"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_job = MagicMock()
        mock_job.result.return_value = [MagicMock(items=lambda: [("x", 1)])]
        mock_get.return_value.query.return_value = mock_job
        out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["error"] is None
    assert len(out["rows"]) == 1


def test_run_readonly_query_insert_rejected(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "INSERT INTO `test-proj.analytics.foo` (a) VALUES (1)"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    err = (out["error"] or "").lower()
    assert "insert" in err or "read-only" in err or "only select" in err


def test_run_readonly_query_update_rejected(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "UPDATE `test-proj.analytics.marketing_performance_daily` SET spend=0"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    err = (out["error"] or "").lower()
    assert "update" in err or "read-only" in err or "only select" in err


def test_run_readonly_query_drop_rejected(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "DROP TABLE `test-proj.analytics.marketing_performance_daily`"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    err = (out["error"] or "").lower()
    assert "drop" in err or "read-only" in err or "only select" in err


def test_run_readonly_query_disallowed_dataset_rejected(env_bq):
    """Dataset not in ADS_DATASET/GA4_DATASET is rejected."""
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `test-proj.other_dataset.some_table` LIMIT 1"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "not allowed" in (out["error"] or "").lower() or "Dataset" in (out["error"] or "")


def test_run_readonly_query_analytics_dataset_rejected_when_raw_env(env_raw):
    """When only raw datasets are allowed (146568, analytics_444259275), analytics.marketing_performance_daily is rejected."""
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `test-proj.analytics.marketing_performance_daily` WHERE client_id = 1 LIMIT 1"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "not allowed" in (out["error"] or "").lower() or "Dataset" in (out["error"] or "")


def test_run_readonly_query_wrong_project_or_dataset_rejected(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `other-project.other_dataset.ads_daily_staging` LIMIT 1"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "Only tables" in (out["error"] or "") or "allowed" in (out["error"] or "").lower() or "Dataset not allowed" in (out["error"] or "")


def test_run_readonly_query_allowed_table_passes_validation(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `test-proj.analytics.ads_daily_staging` WHERE client_id = 1 LIMIT 5"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_get.return_value.query.return_value = mock_job
        out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["error"] is None
    assert out["rows"] == []


def test_run_readonly_query_with_cte_passes_validation(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "WITH t AS (SELECT 1 AS x) SELECT * FROM t LIMIT 1"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_job = MagicMock()
        mock_job.result.return_value = [MagicMock(items=lambda: [("x", 1)])]
        mock_get.return_value.query.return_value = mock_job
        out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["error"] is None
    assert len(out["rows"]) == 1


def test_run_readonly_query_adds_limit_when_missing(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `test-proj.analytics.ads_daily_staging` WHERE client_id = 1"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_get.return_value.query.return_value = mock_job
        run_readonly_query(sql, client_id=1, organization_id="default", max_rows=99)
    call_args = mock_get.return_value.query.call_args[0][0]
    assert "LIMIT 99" in call_args


def test_run_readonly_query_bq_exception_returns_error(env_bq):
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `test-proj.analytics.ads_daily_staging` WHERE client_id = 1 LIMIT 1"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_get.return_value.query.side_effect = Exception("Table not found: 404")
        out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "error" in out and out["error"]
    assert "404" in out["error"] or "not found" in out["error"].lower()


def test_run_readonly_query_any_table_in_allowed_dataset_passes(env_raw):
    """Any table in ADS_DATASET (e.g. raw ads_AccountBasicStats_*) passes validation."""
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `test-proj.146568.ads_AccountBasicStats_4221201460` LIMIT 1"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_get.return_value.query.return_value = mock_job
        out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["error"] is None
    assert out["rows"] == []


def test_run_readonly_query_events_wildcard_in_ga4_dataset_passes(env_raw):
    """GA4 events_* in GA4_DATASET passes validation."""
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT event_name FROM `test-proj.analytics_444259275.events_*` WHERE event_date = '20240201' LIMIT 1"
    with patch("backend.app.clients.bigquery.get_client") as mock_get:
        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_get.return_value.query.return_value = mock_job
        out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["error"] is None
    assert out["rows"] == []


def test_run_readonly_query_wrong_project_rejected(env_bq):
    """Table in allowed dataset but wrong project is rejected."""
    from backend.app.clients.bigquery import run_readonly_query
    sql = "SELECT * FROM `other-project.analytics.ads_daily_staging` LIMIT 1"
    out = run_readonly_query(sql, client_id=1, organization_id="default")
    assert out["rows"] == []
    assert "Only tables" in (out["error"] or "") or "project" in (out["error"] or "").lower()


# ----- execute_tool run_sql (tools.py) -----


def test_execute_tool_run_sql_empty_query():
    from backend.app.copilot.tools import execute_tool
    result = execute_tool("org", 1, "run_sql", {"query": ""})
    data = json.loads(result)
    assert data["rows"] == []
    assert "Missing" in (data.get("error") or "")


def test_execute_tool_run_sql_missing_query_key():
    from backend.app.copilot.tools import execute_tool
    result = execute_tool("org", 1, "run_sql", {})
    data = json.loads(result)
    assert data["rows"] == []
    assert data.get("error") == "Missing query."


def test_execute_tool_run_sql_delegates_to_run_readonly_query(env_bq):
    from backend.app.copilot.tools import execute_tool
    sql = "SELECT * FROM `test-proj.analytics.ads_daily_staging` WHERE client_id = 1 LIMIT 1"
    with patch("backend.app.clients.bigquery.run_readonly_query") as mock_run:
        mock_run.return_value = {"rows": [{"spend": 10.5, "revenue": 100}], "error": None}
        result = execute_tool("org", 1, "run_sql", {"query": sql})
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["client_id"] == 1
    assert mock_run.call_args[1]["organization_id"] == "org"
    data = json.loads(result)
    assert data["row_count"] == 1
    assert data["rows"][0]["spend"] == 10.5
    assert data["error"] is None


def test_execute_tool_run_sql_serializes_date_and_nan(env_bq):
    from backend.app.copilot.tools import execute_tool
    with patch("backend.app.clients.bigquery.run_readonly_query") as mock_run:
        mock_run.return_value = {
            "rows": [
                {"date": date(2025, 2, 27), "value": math.nan, "normal": 42},
            ],
            "error": None,
        }
        result = execute_tool("org", 1, "run_sql", {"query": "SELECT 1"})
    data = json.loads(result)
    assert data["rows"][0]["date"] == "2025-02-27"
    assert data["rows"][0]["value"] is None
    assert data["rows"][0]["normal"] == 42


def test_execute_tool_run_sql_propagates_error():
    from backend.app.copilot.tools import execute_tool
    with patch("backend.app.clients.bigquery.run_readonly_query") as mock_run:
        mock_run.return_value = {"rows": [], "error": "Only SELECT is allowed."}
        result = execute_tool("org", 1, "run_sql", {"query": "DELETE FROM x"})
    data = json.loads(result)
    assert data["rows"] == []
    assert "Only SELECT" in (data.get("error") or "")


def test_execute_tool_unknown_tool_returns_error():
    """Only run_sql is supported; other tool names return error."""
    from backend.app.copilot.tools import execute_tool
    result = execute_tool("org", 1, "get_business_overview", {})
    data = json.loads(result)
    assert "Unknown tool" in (data.get("error") or "")


# ----- knowledge_base -----


def test_knowledge_base_schema_contains_project_and_dataset():
    with patch.dict(
        "os.environ",
        {"BQ_PROJECT": "my-proj", "ADS_DATASET": "myds-ads", "GA4_DATASET": "myds-ga4"},
        clear=False,
    ):
        from backend.app.copilot.knowledge_base import get_schema_for_copilot
        schema = get_schema_for_copilot()
    assert "my-proj" in schema
    assert "myds-ads" in schema
    assert "myds-ga4" in schema


def test_knowledge_base_schema_contains_datasets_and_guidance():
    from backend.app.copilot.knowledge_base import get_schema_for_copilot
    schema = get_schema_for_copilot()
    assert "Ads dataset" in schema or "ADS_DATASET" in schema
    assert "GA4" in schema or "GA4_DATASET" in schema
    assert "Query guidelines" in schema or "SELECT" in schema
    assert "client_id" in schema or "customer_id" in schema


def test_knowledge_base_schema_read_only_guidance():
    from backend.app.copilot.knowledge_base import get_schema_for_copilot
    schema = get_schema_for_copilot()
    assert "SELECT" in schema
    assert "client_id" in schema or "customer_id" in schema


def test_knowledge_base_schema_contains_data_semantics():
    """Schema includes Data semantics so LLM chooses GA4 for item views and Ads for campaign metrics."""
    from backend.app.copilot.knowledge_base import get_schema_for_copilot
    schema = get_schema_for_copilot()
    assert "Data semantics" in schema
    assert "item_id" in schema or "item" in schema.lower()
    assert "traffic_source" in schema or "traffic" in schema.lower()


def test_knowledge_base_fallback_when_discovery_missing():
    """When discovery file is missing, fallback schema is returned and does not crash."""
    from backend.app.copilot import knowledge_base
    with patch.object(knowledge_base, "_discovery_path") as mock_path:
        mock_path.return_value = Path("/nonexistent/bigquery_discovery.json")
        schema = knowledge_base.get_schema_for_copilot(use_cache=False)
    assert "BigQuery" in schema or "Database" in schema
    assert "ADS_DATASET" in schema or "Ads dataset" in schema
    assert "not found" in schema or "Discovery" in schema


def test_knowledge_base_fallback_when_discovery_invalid_json():
    """When discovery file exists but is invalid JSON, fallback schema is returned."""
    import tempfile
    from backend.app.copilot import knowledge_base
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json {")
        path = Path(f.name)
    try:
        with patch.object(knowledge_base, "_discovery_path", return_value=path):
            schema = knowledge_base.get_schema_for_copilot(use_cache=False)
        assert "BigQuery" in schema or "Database" in schema
        assert "error" in schema.lower() or "Discovery" in schema
    finally:
        path.unlink(missing_ok=True)


# ----- chat_handler _build_system_template -----


def test_build_system_template_includes_client_id():
    from backend.app.copilot.chat_handler import _build_system_template
    t = _build_system_template(42)
    assert "42" in t
    assert "client_id" in t


def test_build_system_template_includes_run_sql_and_schema():
    from backend.app.copilot.chat_handler import _build_system_template
    t = _build_system_template(1)
    assert "run_sql" in t
    assert "ads_daily_staging" in t or "ga4_daily_staging" in t or "Knowledge base" in t


def test_build_system_template_run_sql_only_and_two_datasets():
    """Copilot has one tool (run_sql) and only ADS_DATASET/GA4_DATASET; no layout/widgets."""
    from backend.app.copilot.chat_handler import _build_system_template
    t = _build_system_template(1)
    assert "run_sql" in t
    assert "ADS_DATASET" in t or "GA4_DATASET" in t
    assert "get_business_overview" not in t
    assert "widgets" not in t
    assert "layout" not in t
