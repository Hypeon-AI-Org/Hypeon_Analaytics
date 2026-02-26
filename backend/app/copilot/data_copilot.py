"""
Data Analysis Copilot: natural language -> tool selection -> query marketing_performance_daily
-> Python analysis -> visualization spec -> LLM explanation only.
Works even when analytics_insights is not available.
Returns deterministic JSON: { message, charts, tables, metadata }.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Optional

from .router import classify_intent

logger = logging.getLogger(__name__)

# Default date range (days) when not inferred from prompt
DEFAULT_DAYS = 30
MAX_DAYS = 365


def _is_bigquery_auth_error(exc: BaseException) -> bool:
    """True if the exception indicates BigQuery/Google auth needs re-login."""
    msg = (str(exc) or "").lower()
    return (
        "reauthentication is needed" in msg
        or "application-default login" in msg
        or "refresherror" in msg
        or "invalid_grant" in msg
        or "credentials" in msg and "refresh" in msg
    )


def _parse_days_from_prompt(prompt: str) -> int:
    """Infer 'last N days' from prompt; default DEFAULT_DAYS."""
    if not prompt:
        return DEFAULT_DAYS
    m = re.search(r"(?:last|past|previous)\s*(\d+)\s*days?", prompt, re.I)
    if m:
        try:
            n = int(m.group(1))
            return min(max(1, n), MAX_DAYS)
        except ValueError:
            pass
    if re.search(r"\b(?:this|last)\s*week\b", prompt, re.I):
        return 7
    if re.search(r"\b(?:this|last)\s*month\b", prompt, re.I):
        return 30
    return DEFAULT_DAYS


def _get_date_range(prompt: str) -> tuple[date, date]:
    end = date.today()
    days = _parse_days_from_prompt(prompt)
    start = end - timedelta(days=days - 1)
    return start, end


def run(
    prompt: str,
    organization_id: str,
    *,
    client_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Execute data analysis path: route -> tool -> analysis -> viz -> LLM explanation.
    Returns { message, charts, tables, metadata }.
    Handles missing GA4/data gaps gracefully.
    """
    cid = int(client_id) if client_id is not None else 1
    start_date, end_date = _get_date_range(prompt)
    intent = classify_intent(prompt)

    tool_used = "none"
    df = None
    analysis_result = None
    chart_specs = []
    table_payloads = []
    error_reason = None  # passed to LLM for dynamic explanation

    try:
        if intent in ("DATA_ANALYSIS", "METRIC_EXPLANATION", "GENERAL_CHAT"):
            # Which channel performs best? -> channel breakdown first
            if re.search(r"\bchannel\b", (prompt or "").lower()):
                from ..tools import get_channel_breakdown
                tool_used = "channel_breakdown"
                df = get_channel_breakdown(cid, start_date, end_date, organization_id=organization_id)
                if df is not None and not df.empty:
                    from ..analysis.engine import run_analysis
                    analysis_result = run_analysis(df, analysis_type="channel_breakdown")
                    from ..analysis.visualization import dataframe_to_chart_spec
                    chart_specs.append(dataframe_to_chart_spec(df, chart_type="bar_chart", x_key="channel", y_keys=["revenue", "spend"], title="Channel performance"))
                    table_payloads.append({"title": "By channel", "rows": analysis_result.get("table", []), "columns": [
                        {"key": "channel", "label": "Channel"},
                        {"key": "spend", "label": "Spend"},
                        {"key": "revenue", "label": "Revenue"},
                        {"key": "roas", "label": "ROAS"},
                    ]})
                else:
                    error_reason = "no_data_for_period"
            else:
                # Default: campaign performance + daily trend from unified table
                from ..tools import get_campaign_performance
                from ..clients.bigquery import load_marketing_performance
                tool_used = "campaign_performance"
                df = get_campaign_performance(cid, start_date, end_date, organization_id=organization_id)
                if df is not None and not df.empty:
                    from ..analysis.engine import run_analysis
                    analysis_result = run_analysis(df, analysis_type="campaign_performance")
                    table_payloads.append({"title": "Campaign performance", "rows": analysis_result.get("table", []), "columns": [
                        {"key": "campaign_id", "label": "Campaign"},
                        {"key": "channel", "label": "Channel"},
                        {"key": "spend", "label": "Spend"},
                        {"key": "revenue", "label": "Revenue"},
                        {"key": "roas", "label": "ROAS"},
                    ]})
                    # Daily trend: load raw daily and aggregate by date
                    days = (end_date - start_date).days + 1
                    daily_df = load_marketing_performance(cid, end_date, days=min(days, MAX_DAYS), organization_id=organization_id)
                    if daily_df is not None and not daily_df.empty and "date" in daily_df.columns:
                        import pandas as pd
                        daily_df["date"] = pd.to_datetime(daily_df["date"]).dt.date
                        by_date = daily_df.groupby("date", as_index=False).agg(
                            spend=("spend", "sum"),
                            revenue=("revenue", "sum"),
                            conversions=("conversions", "sum"),
                        )
                        from ..analysis.visualization import dataframe_to_chart_spec
                        chart_specs.append(dataframe_to_chart_spec(
                            by_date, chart_type="line_chart", x_key="date", y_keys=["revenue", "spend"], title="Revenue & Spend trend",
                        ))
                else:
                    from ..tools import get_channel_breakdown
                    df = get_channel_breakdown(cid, start_date, end_date, organization_id=organization_id)
                    tool_used = "channel_breakdown"
                    if df is not None and not df.empty:
                        from ..analysis.engine import run_analysis
                        analysis_result = run_analysis(df, analysis_type="channel_breakdown")
                        from ..analysis.visualization import dataframe_to_chart_spec
                        chart_specs.append(dataframe_to_chart_spec(df, chart_type="bar_chart", x_key="channel", y_keys=["revenue", "spend"], title="By channel"))
                        table_payloads.append({"title": "By channel", "rows": analysis_result.get("table", []), "columns": [
                            {"key": "channel", "label": "Channel"},
                            {"key": "spend", "label": "Spend"},
                            {"key": "revenue", "label": "Revenue"},
                            {"key": "roas", "label": "ROAS"},
                        ]})
                    else:
                        error_reason = "no_data_for_period"
            if df is None or df.empty and not table_payloads and error_reason is None:
                error_reason = "no_data_for_period"

        elif intent == "COMPARISON":
            from ..tools import compare_periods
            tool_used = "compare_periods"
            # Default: this week (7d) vs previous week (7d)
            df = compare_periods(
                cid, start_date, end_date,
                period_a_label="current", period_b_label="previous",
                period_a_days=7, period_b_days=7,
                organization_id=organization_id,
            )
            if df is not None and not df.empty:
                from ..analysis.engine import run_analysis
                analysis_result = run_analysis(df, analysis_type="period_comparison", date_column="date")
                from ..analysis.visualization import dataframe_to_chart_spec
                chart_specs.append(dataframe_to_chart_spec(df, chart_type="line_chart", x_key="date", y_keys=["revenue", "spend"], title="Period comparison"))
                table_payloads.append({"title": "Period summary", "rows": analysis_result.get("table", []), "columns": [
                    {"key": "period_label", "label": "Period"},
                    {"key": "spend", "label": "Spend"},
                    {"key": "revenue", "label": "Revenue"},
                    {"key": "roas", "label": "ROAS"},
                ]})
            else:
                error_reason = "no_data_for_period"

    except Exception as e:
        logger.exception("Data copilot tool/analysis failed: %s", e)
        if _is_bigquery_auth_error(e):
            error_reason = "bigquery_auth_expired"
        else:
            error_reason = "data_load_failed"

    # When live data failed, try cache so the user still sees something useful
    if analysis_result is None or not (analysis_result.get("summary_stats") or {}).get("data_available"):
        try:
            from ..analytics_cache import get_cached_business_overview, get_cached_campaign_performance
            overview = get_cached_business_overview(organization_id, cid)
            campaigns = get_cached_campaign_performance(organization_id, cid)
            if overview and isinstance(overview, dict):
                try:
                    total_revenue = float(overview.get("total_revenue") or 0)
                    total_spend = float(overview.get("total_spend") or 0)
                except (TypeError, ValueError):
                    total_revenue, total_spend = 0.0, 0.0
                roas = round((total_revenue / total_spend), 2) if total_spend else 0
                analysis_result = {
                    "summary_stats": {
                        "data_available": True,
                        "total_revenue": total_revenue,
                        "total_spend": total_spend,
                        "roas": roas,
                        "from_cache": True,
                    },
                    "table": [],
                    "chart_data": [],
                }
                if campaigns and len(campaigns) > 0:
                    table_payloads.append({
                        "title": "Campaign performance (cached)",
                        "rows": campaigns[:20],
                        "columns": [
                            {"key": "campaign", "label": "Campaign"},
                            {"key": "spend", "label": "Spend"},
                            {"key": "revenue", "label": "Revenue"},
                            {"key": "roas", "label": "ROAS"},
                            {"key": "status", "label": "Status"},
                        ],
                    })
                if error_reason:
                    error_reason = "data_from_cache_only"  # LLM will explain
        except Exception as cache_e:
            logger.debug("Cache fallback failed: %s", cache_e)

    if analysis_result is None:
        analysis_result = {"summary_stats": {"data_available": False}, "table": [], "chart_data": []}

    summary_stats = analysis_result.get("summary_stats") or {}
    if error_reason:
        summary_stats["data_available"] = False
        summary_stats["error_reason"] = error_reason
    if not table_payloads and analysis_result.get("table"):
        table_payloads.append({"title": "Summary", "rows": analysis_result["table"], "columns": []})

    # Build layout for frontend (charts + tables as widgets)
    from ..analysis.visualization import build_layout_from_charts_and_tables
    layout = build_layout_from_charts_and_tables(chart_specs, table_payloads, chart_specs=chart_specs)

    # LLM explains from context (including errors); no hardcoded message
    message = _explain_with_llm(
        prompt=prompt,
        summary_stats=summary_stats,
        table_summary=table_payloads,
        intent=intent,
    )

    return {
        "message": message,
        "charts": chart_specs,
        "tables": table_payloads,
        "layout": layout,
        "metadata": {
            "tool_used": tool_used,
            "date_range": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "intent": intent,
        },
    }


def _explain_with_llm(
    prompt: str,
    summary_stats: dict,
    table_summary: list,
    intent: str,
) -> str:
    """LLM generates explanation from context (data or error). No hardcoded user-facing text."""
    context = {
        "summary_stats": summary_stats,
        "tables_preview": [],
    }
    for t in (table_summary or [])[:3]:
        rows = (t.get("rows") or t.get("table") or [])[:10]
        context["tables_preview"].append({"title": t.get("title"), "row_count": len(rows), "sample_rows": rows})

    try:
        from ..llm_gemini import is_gemini_configured
        from ..llm_claude import is_claude_configured
        from ..copilot_synthesizer import get_llm_client
        if not (is_gemini_configured() or is_claude_configured()):
            return _fallback_message()
        llm = get_llm_client()
        err = summary_stats.get("error_reason")
        if err:
            hints = {
                "bigquery_auth_expired": "BigQuery credentials expired or invalid; re-authentication may be required.",
                "no_data_for_period": "No analytics rows for the requested date range.",
                "data_load_failed": "Data could not be loaded; pipeline or date range may be the cause.",
                "data_from_cache_only": "Live data unavailable; results below are from cache.",
            }
            context["instruction"] = (
                "The user asked for analytics but we encountered an issue. error_reason: " + str(err) + ". "
                "Hint: " + (hints.get(err) or err) + " "
                "Explain in your own words what happened and what the user can do next. Do not invent data."
            )
        system = (
            "You are a senior marketing analyst. Respond to the user's question using ONLY the provided context. "
            "Use summary_stats and tables_preview. Do NOT invent numbers. "
            "If data_available is false or error_reason is set, explain the situation and suggest next steps in your own words. "
            "Keep the response concise (2-4 short paragraphs)."
        )
        user_content = (
            f"User question: {prompt}\n\n"
            f"Context:\n{json.dumps(context, default=str)}"
        )
        full_prompt = f"{system}\n\n{user_content}\n\nProvide your response:"
        response = llm(full_prompt)
        if isinstance(response, dict):
            response = response.get("explanation") or response.get("summary") or response.get("tldr") or json.dumps(response)
        if isinstance(response, str):
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    response = parsed.get("explanation") or parsed.get("summary") or parsed.get("tldr") or response
            except (json.JSONDecodeError, TypeError):
                pass
            if len(response) > 50:
                return response.strip()
    except Exception as e:
        logger.warning("Data copilot LLM call failed: %s", e)
    return _fallback_message()


def _fallback_message() -> str:
    """Only when LLM is unavailable or fails; single generic line."""
    return "I couldn't generate a response right now. Please try again."
