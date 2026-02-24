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


def validate_layout(layout: dict | list) -> tuple[bool, list[str]]:
    if isinstance(layout, list):
        layout = {"widgets": layout}
    if not isinstance(layout, dict):
        return (False, ["Layout must be object or array"])
    contract = LayoutContract(widgets=layout.get("widgets", []))
    return contract.validate_widgets()
