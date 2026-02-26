# Analysis engine: Python-only metrics (ROAS, trends, growth %). No LLM.

from .engine import run_analysis
from .visualization import (
    dataframe_to_chart_spec,
    chart_specs_to_layout_widgets,
    tables_to_layout_widgets,
    build_layout_from_charts_and_tables,
)

__all__ = [
    "run_analysis",
    "dataframe_to_chart_spec",
    "chart_specs_to_layout_widgets",
    "tables_to_layout_widgets",
    "build_layout_from_charts_and_tables",
]
