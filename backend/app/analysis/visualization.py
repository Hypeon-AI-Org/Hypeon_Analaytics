"""
Visualization Spec Generator: convert DataFrame / analysis output to chart spec and layout widgets.
Output format for charts: { "type": "line_chart"|"bar_chart"|"pie_chart", "x": "date", "y": ["revenue","spend"], "data": [...] }.
Frontend renders using Recharts; we also produce layout.widgets for existing DynamicDashboardRenderer.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd


def dataframe_to_chart_spec(
    df: pd.DataFrame,
    *,
    chart_type: str = "line_chart",
    x_key: Optional[str] = None,
    y_keys: Optional[list[str]] = None,
    title: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convert a DataFrame to a chart specification.
    Returns { type, x, y (list), data (list of dicts), title? }.
    """
    if df is None or df.empty:
        return {"type": chart_type, "x": x_key or "date", "y": y_keys or [], "data": [], "title": title or ""}

    data = df.to_dict("records")
    for row in data:
        for k, v in list(row.items()):
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat() if callable(getattr(v, "isoformat", None)) else str(v)
            elif isinstance(v, (float,)) and (v != v or v == float("inf")):  # NaN or Inf
                row[k] = 0

    x = x_key
    if not x and data:
        x = "date" if "date" in (data[0] or {}) else list((data[0] or {}).keys())[0]
    if not x:
        x = "date"

    y = y_keys
    if not y and data:
        numeric = [k for k, v in (data[0] or {}).items() if isinstance(v, (int, float))]
        y = [k for k in ("revenue", "spend", "conversions", "roas") if k in numeric][:2]
    if not y:
        y = ["revenue"]

    return {
        "type": chart_type,
        "x": x,
        "y": y,
        "data": data[:500],
        "title": title or "",
    }


def chart_specs_to_layout_widgets(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert chart specs to frontend layout widgets (chart, table) for DynamicDashboardRenderer.
    Each spec becomes a widget: type "chart" with chartType (line|bar|pie), title, data, xKey, yKey.
    For multiple y series we emit one chart per series so existing frontend (single yKey) works.
    """
    widgets = []
    for spec in (specs or []):
        if not isinstance(spec, dict):
            continue
        stype = (spec.get("type") or "line_chart").replace("_chart", "")
        chart_type = "line" if stype == "line" else ("pie" if stype == "pie" else "bar")
        data = spec.get("data") or []
        x_key = spec.get("x") or "date"
        y_list = spec.get("y")
        if not isinstance(y_list, list):
            y_list = [y_list] if y_list else ["revenue"]
        title = spec.get("title") or ""

        for y_key in y_list:
            if not y_key:
                continue
            widgets.append({
                "type": "chart",
                "chartType": chart_type,
                "title": title or (y_key.replace("_", " ").title()),
                "data": data,
                "xKey": x_key,
                "yKey": y_key,
            })
    return widgets


def tables_to_layout_widgets(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert table payloads to layout table widgets.
    Each table: { "title": "", "columns": [ { "key": "", "label": "" } ], "rows": [ {} ] }.
    """
    widgets = []
    for t in (tables or []):
        if not isinstance(t, dict):
            continue
        rows = t.get("rows") or t.get("table") or []
        cols = t.get("columns")
        if not cols and rows:
            cols = [{"key": k, "label": k.replace("_", " ").title()} for k in (rows[0] or {}).keys()]
        widgets.append({
            "type": "table",
            "title": t.get("title") or "Data",
            "columns": cols or [],
            "rows": rows[:500],
        })
    return widgets


def build_layout_from_charts_and_tables(
    charts: list[dict],
    tables: list[dict],
    *,
    chart_specs: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """
    Build full layout { widgets: [...] } from charts (raw specs) and tables (with columns/rows).
    If chart_specs provided, use those; else treat charts as already in spec form.
    """
    widget_list = []
    if chart_specs:
        widget_list.extend(chart_specs_to_layout_widgets(chart_specs))
    else:
        widget_list.extend(chart_specs_to_layout_widgets(charts or []))
    widget_list.extend(tables_to_layout_widgets(tables or []))
    return {"widgets": widget_list}
