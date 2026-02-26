"""
Query Contract Layer: layout validation for Copilot-generated dashboards and reports.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class KpiWidget(BaseModel):
    type: Literal["kpi"] = "kpi"
    title: str = ""
    value: Union[str, int, float] = ""
    trend: Optional[Literal["up", "down", "neutral"]] = None
    subtitle: Optional[str] = None


class ChartWidget(BaseModel):
    type: Literal["chart"] = "chart"
    chartType: Literal["line", "bar", "pie"] = "bar"
    title: Optional[str] = None
    data: List[Any] = Field(default_factory=list)
    xKey: Optional[str] = None
    yKey: Optional[str] = None


class TableColumn(BaseModel):
    key: str
    label: str


class TableWidget(BaseModel):
    type: Literal["table"] = "table"
    title: Optional[str] = None
    columns: List[TableColumn] = Field(default_factory=list)
    rows: List[dict] = Field(default_factory=list)


class FunnelStage(BaseModel):
    name: str
    value: Union[int, float]
    dropPct: Optional[float] = None


class FunnelWidget(BaseModel):
    type: Literal["funnel"] = "funnel"
    title: Optional[str] = None
    stages: List[FunnelStage] = Field(default_factory=list)


class LayoutContract(BaseModel):
    widgets: List[dict] = Field(default_factory=list)

    def validate_widgets(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for i, w in enumerate(self.widgets):
            if not isinstance(w, dict):
                errors.append(f"widget[{i}]: must be object")
                continue
            t = w.get("type")
            if t == "kpi":
                try:
                    KpiWidget(**w)
                except Exception as e:
                    errors.append(f"widget[{i}] (kpi): {e}")
            elif t == "chart":
                try:
                    ChartWidget(**w)
                except Exception as e:
                    errors.append(f"widget[{i}] (chart): {e}")
            elif t == "table":
                try:
                    TableWidget(**w)
                except Exception as e:
                    errors.append(f"widget[{i}] (table): {e}")
            elif t == "funnel":
                try:
                    FunnelWidget(**w)
                except Exception as e:
                    errors.append(f"widget[{i}] (funnel): {e}")
            elif t:
                errors.append(f"widget[{i}]: unknown type '{t}'")
            else:
                errors.append(f"widget[{i}]: missing 'type'")
        return (len(errors) == 0, errors)


VALID_CHART_TYPES = frozenset(("line", "bar", "pie"))


def validate_chart_type(chart_type: Any) -> tuple[bool, list[str]]:
    """Only line, bar, pie allowed. Reject invalid to avoid frontend crash."""
    if chart_type in VALID_CHART_TYPES:
        return (True, [])
    return (False, [f"chart_type must be one of line, bar, pie; got {chart_type!r}"])


def validate_dataset(widget: Any) -> tuple[bool, list[str]]:
    """
    Validate widget data shape: table columns/rows, chart data array, funnel stages.
    Reject invalid so frontend never receives bad layout.
    """
    errors: list[str] = []
    if not isinstance(widget, dict):
        return (False, ["widget must be an object"])
    t = widget.get("type")
    if t == "table":
        cols = widget.get("columns")
        rows = widget.get("rows")
        if not isinstance(cols, list):
            errors.append("table.columns must be list")
        if not isinstance(rows, list):
            errors.append("table.rows must be list")
        if isinstance(rows, list) and rows and not isinstance(rows[0], dict):
            errors.append("table.rows must be list of objects")
    elif t == "chart":
        data = widget.get("data")
        if not isinstance(data, list):
            errors.append("chart.data must be list")
        if isinstance(data, list) and data and not isinstance(data[0], dict):
            errors.append("chart.data must be list of objects")
        ct = widget.get("chartType")
        if ct and ct not in VALID_CHART_TYPES:
            errors.append(f"chart.chartType must be line, bar, or pie; got {ct!r}")
    elif t == "funnel":
        stages = widget.get("stages")
        if not isinstance(stages, list):
            errors.append("funnel.stages must be list")
        if isinstance(stages, list):
            for i, s in enumerate(stages):
                if not isinstance(s, dict) or "name" not in s or "value" not in s:
                    errors.append(f"funnel.stages[{i}] must have name and value")
    return (len(errors) == 0, errors)


def validate_layout(layout: dict | list) -> tuple[bool, list[str]]:
    if isinstance(layout, list):
        layout = {"widgets": layout}
    if not isinstance(layout, dict):
        return (False, ["Layout must be object or array"])
    raw_widgets = layout.get("widgets", [])
    if not isinstance(raw_widgets, list):
        raw_widgets = []
    widgets = [w for w in raw_widgets if isinstance(w, dict)]
    contract = LayoutContract(widgets=widgets)
    ok, errors = contract.validate_widgets()
    if not ok:
        return (False, errors)
    for i, w in enumerate(contract.widgets):
        if not isinstance(w, dict):
            errors.append(f"widget[{i}]: must be object")
            continue
        if w.get("type") in ("chart", "table", "funnel"):
            ok_ds, err_ds = validate_dataset(w)
            if not ok_ds:
                errors.extend([f"widget[{i}]: {e}" for e in err_ds])
    return (len(errors) == 0, errors)
