"""
Copilot Router: classify user intent and route to insight Copilot vs data analysis path.
IF insight_id present -> use existing insight Copilot.
ELSE -> use data analysis path (data_copilot).
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Literal, Optional

IntentType = Literal[
    "DATA_ANALYSIS",
    "COMPARISON",
    "METRIC_EXPLANATION",
    "INSIGHT_EXPLANATION",
    "GENERAL_CHAT",
]

# Patterns for intent classification (no insight_id path)
DATA_ANALYSIS_PATTERNS = [
    r"\b(?:last|past|previous)\s*\d+\s*days?\b",
    r"\b(?:show|get|give)\s*(?:me\s*)?(?:last|past)\s*\d+\s*days?\b",
    r"\bperformance\s*(?:over|for|in)\b",
    r"\b(?:how\s*)?(?:am\s*i|are\s*we)\s*performing\b",
    r"\brevenue\s*(?:last|past|this)\b",
    r"\bspend\s*(?:last|past|this)\b",
    r"\b(?:show|see)\s*(?:last|past)\s*\d+\s*days?\b",
    r"\b(?:last|past)\s*\d+\s*days?\s*performance\b",
]
COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\b(?:this|current)\s*(?:week|month)\s*(?:vs|versus)\b",
    r"\b(?:last|previous)\s*(?:week|month)\s*vs\b",
    r"\bweek\s*over\s*week\b",
    r"\bvs\s*(?:last|previous)\s*(?:week|month)\b",
    r"\bcomparison\b",
]
METRIC_EXPLANATION_PATTERNS = [
    r"\bwhat\s*is\s*(?:roas|roi|ctr|cpa)\b",
    r"\b(?:explain|meaning\s*of)\s*(?:roas|roi|ctr|cpa)\b",
    r"\bwhy\s*(?:did\s*)?(?:revenue|spend)\s*(?:drop|increase)\b",
    r"\bwhy\s*revenue\s*(?:dropped|down)\b",
]
INSIGHT_EXPLANATION_PATTERNS = [
    r"\b(?:this|that)\s*insight\b",
    r"\bexplain\s*(?:this|that)\s*(?:recommendation|action)\b",
    r"\bwhy\s*(?:this|that)\s*recommendation\b",
]


# Greetings and short chat: use conversational path (no full report dump)
GREETING_PATTERNS = [
    r"^\s*hi\s*$", r"^\s*hello\s*$", r"^\s*hey\s*$", r"^\s*hiya\s*$",
    r"^\s*thanks\s*\.?$", r"^\s*thank you\s*\.?$", r"^\s*thx\s*\.?$",
    r"^\s*good (?:morning|afternoon|evening)\s*\.?$", r"^\s*howdy\s*$",
]
# Follow-up / conversational: "explain more", "is there a name", "what about campaign X" → chat_handler
FOLLOW_UP_PATTERNS = [
    r"\bexplain\s+more\b", r"\btell\s+me\s+more\b", r"\b(is there|do you have)\s+(a\s+)?name\b",
    r"\bname\s+(?:for|of|available)\b", r"\bwhat\s+about\s+(?:campaign\s+)?\d",
    r"\bdetails?\s+about\b", r"\b(?:can you\s+)?(?:explain|describe)\s+(?:campaign\s+)?\d",
    r"\b(?:this|that)\s+campaign\s*\d", r"\bcampaign\s+\d+\s*(?:name|details?)?",
    r"\bexplain\s+more\s+about\b", r"\babout\s+this\s+[\"']?\d+", r"\bname\s+availab",
]


def classify_intent(query: str) -> IntentType:
    """
    Classify user intent from natural language query.
    Greetings and follow-ups → GENERAL_CHAT (conversational). Report-style → DATA_ANALYSIS/COMPARISON.
    """
    q = (query or "").strip().lower()
    if not q:
        return "GENERAL_CHAT"

    # Greetings → conversational reply (no data dump)
    for pat in GREETING_PATTERNS:
        if re.search(pat, q, re.I):
            return "GENERAL_CHAT"
    if len(q) <= 15 and re.match(r"^(hi|hello|hey|thanks?|thx|ok|yes|no)\s*[!?.]?$", q):
        return "GENERAL_CHAT"

    # Follow-up questions (explain campaign X, is there a name) → conversational so LLM can answer from context
    for pat in FOLLOW_UP_PATTERNS:
        if re.search(pat, q):
            return "GENERAL_CHAT"

    for pat in COMPARISON_PATTERNS:
        if re.search(pat, q):
            return "COMPARISON"
    for pat in DATA_ANALYSIS_PATTERNS:
        if re.search(pat, q):
            return "DATA_ANALYSIS"
    for pat in METRIC_EXPLANATION_PATTERNS:
        if re.search(pat, q):
            return "METRIC_EXPLANATION"
    for pat in INSIGHT_EXPLANATION_PATTERNS:
        if re.search(pat, q):
            return "INSIGHT_EXPLANATION"

    # Channel / campaign performance queries (clear report request)
    if re.search(r"\b(?:which\s*)?channel\s*(?:perform|best)\b", q):
        return "DATA_ANALYSIS"
    if re.search(r"\b(?:best|top)\s*(?:performing\s*)?(?:channel|campaign)\b", q):
        return "DATA_ANALYSIS"
    if re.search(r"\b(?:show|see|get)\s*(?:revenue|spend|performance)\b", q):
        return "DATA_ANALYSIS"

    return "DATA_ANALYSIS"  # default for analytics product


def route_copilot(
    query: str,
    *,
    insight_id: Optional[str] = None,
) -> Literal["insight", "data_analysis"]:
    """
    Route request: use existing insight Copilot when insight_id is present,
    otherwise use data analysis path.
    """
    if insight_id and str(insight_id).strip():
        return "insight"
    return "data_analysis"
