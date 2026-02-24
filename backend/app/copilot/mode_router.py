"""
Copilot mode router: classify user query into explain | analyze | build_dashboard | build_report.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

CopilotMode = Literal["explain", "analyze", "build_dashboard", "build_report"]

EXPLAIN_PATTERNS = [
    r"\bwhy\b", r"\bexplain\b", r"\bwhat (?:does|is)\b", r"\bhow (?:does|is)\b",
    r"\bmeaning\b", r"\breason\b", r"\bthis (?:insight|recommendation)\b",
]
ANALYZE_PATTERNS = [
    r"\bhow (?:am i|are we) performing\b", r"\bwhat (?:should i|to do) (?:today)?\b",
    r"\bwhich campaign\b", r"\bwaste(s|ing)?\s*money\b", r"\brevenue (?:drop|down)\b",
    r"\bsummary\b", r"\boverview\b", r"\btop (?:drivers|actions)\b", r"\brecommend\b",
]
BUILD_DASHBOARD_PATTERNS = [
    r"\bdashboard\b", r"\bbuild (?:a )?dashboard\b", r"\bcreate (?:a )?dashboard\b",
    r"\bshow (?:me )?(?:a )?dashboard\b", r"\bvisuali(z|s)e\b",
]
BUILD_REPORT_PATTERNS = [
    r"\breport\b", r"\bbuild (?:a )?report\b", r"\bcreate (?:a )?report\b",
    r"\bgenerate (?:a )?report\b", r"\bweekly\b", r"\bmonthly\b",
]


def route_copilot_mode(query: str, *, insight_id: Optional[str] = None) -> CopilotMode:
    q = (query or "").strip().lower()
    if not q and insight_id:
        return "explain"
    if insight_id and len(q) < 40:
        if re.search(r"explain|why|what (?:is|does)|this", q):
            return "explain"
    for pat in BUILD_DASHBOARD_PATTERNS:
        if re.search(pat, q):
            return "build_dashboard"
    for pat in BUILD_REPORT_PATTERNS:
        if re.search(pat, q):
            return "build_report"
    for pat in EXPLAIN_PATTERNS:
        if re.search(pat, q):
            return "explain"
    for pat in ANALYZE_PATTERNS:
        if re.search(pat, q):
            return "analyze"
    return "analyze"
