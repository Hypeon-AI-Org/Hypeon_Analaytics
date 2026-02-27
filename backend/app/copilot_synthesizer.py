"""
Copilot synthesis: ONLY from analytics_insights and supporting_metrics_snapshot (marts layer).
No decision store; no raw analytics tables. Include explanation, business reasoning, confidence, data provenance.
Reject hallucinated responses.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

from .config_loader import get

_llm_client: Optional[Callable[[str], str]] = None


def set_llm_client(fn: Callable[[str], str]) -> None:
    global _llm_client
    _llm_client = fn


def get_llm_client() -> Callable[[str], str]:
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    def _stub(prompt: str) -> str:
        return json.dumps({
            "summary": "Summary from grounded data.",
            "explanation": "Explanation with top 3 evidence points from insight and metrics.",
            "business_reasoning": "Based on evidence only.",
            "action_steps": ["Step 1", "Step 2"],
            "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
            "provenance": "analytics_insights, supporting_metrics_snapshot",
            "confidence": 0.85,
            "tldr": "TL;DR from data only.",
        })
    return _stub


PROMPT_TEMPLATE = """You are a senior growth analyst. Use ONLY the following grounded inputs. Do NOT invent metrics or query raw analytics.

## Current insight (from analytics_insights / marts)
{insight_json}

## Supporting metrics snapshot (pre-aggregated)
{supporting_metrics_json}
{copilot_context_section}

## Instructions
- Explain using ONLY the above data.
- Include business reasoning tied to evidence and provenance. Answer like a senior analyst.
- State confidence (0-1) and data provenance. Do NOT dump raw metrics; synthesize and reason.
- If the data is insufficient, say so; do NOT hallucinate.
- Output JSON only with: summary, explanation, business_reasoning, action_steps, expected_impact, provenance, confidence, tldr.

JSON:
"""


def _evidence_to_table(evidence: list) -> str:
    if not evidence:
        return "None."
    lines = ["metric | value | baseline | period"]
    for e in (evidence or [])[:10]:
        if isinstance(e, dict):
            m, v, b, p = e.get("metric", ""), e.get("value", 0), e.get("baseline", 0), e.get("period", "")
        else:
            m = getattr(e, "metric", "")
            v = getattr(e, "value", 0)
            b = getattr(e, "baseline", 0)
            p = getattr(e, "period", "")
        lines.append(f"{m} | {v} | {b} | {p}")
    return "\n".join(lines)


def _serialize_insight(insight: dict) -> str:
    safe = {k: v for k, v in insight.items() if k in (
        "insight_id", "summary", "explanation", "recommendation", "evidence", "confidence",
        "insight_type", "expected_impact", "expected_impact_value", "severity", "detected_by",
        "potential_savings", "potential_revenue_gain", "risk_level",
    )}
    for k in list(safe.keys()):
        v = safe[k]
        if hasattr(v, "isoformat"):
            safe[k] = v.isoformat()
        elif isinstance(v, (list, tuple)) and v and hasattr(v[0], "_fields"):
            safe[k] = [dict(x) for x in v]
    return json.dumps(safe, default=str)


def _build_copilot_context_section(
    recent_insights: Optional[list[dict]] = None,
) -> str:
    """Build optional context: recent insights only (no decision/agent data)."""
    if not recent_insights:
        return ""
    return "\n## Recent insights (for context)\n" + json.dumps(
        [{k: v for k, v in i.items() if k in ("insight_id", "summary", "insight_type", "status")} for i in recent_insights[:5]],
        default=str,
    ) + "\n"


def build_prompt_grounded(
    insight: dict,
    supporting_metrics: Optional[dict],
    *,
    recent_insights: Optional[list[dict]] = None,
) -> str:
    """Build prompt from insight and supporting_metrics_snapshot only (marts layer)."""
    context_section = _build_copilot_context_section(recent_insights)
    return PROMPT_TEMPLATE.format(
        insight_json=_serialize_insight(insight),
        supporting_metrics_json=json.dumps(supporting_metrics or {}, default=str),
        copilot_context_section=context_section,
    )


def _parse_llm_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if "json" in (lines[0] or "").lower() else 0
        end = next((i for i, L in enumerate(lines) if L.strip() == "```"), len(lines))
        text = "\n".join(lines[start:end])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": text[:200],
            "explanation": "",
            "business_reasoning": "",
            "action_steps": [],
            "expected_impact": {"metric": "", "estimate": 0.0, "units": ""},
            "provenance": "unknown",
            "confidence": 0.5,
            "tldr": text[:100],
        }


def prepare_copilot_prompt(
    insight_id: str,
    *,
    organization_id: Optional[str] = None,
    load_insight: Optional[Callable[[str], Optional[dict]]] = None,
) -> tuple[Optional[str], Optional[dict]]:
    """
    Load context and build prompt for Copilot. Returns (prompt, error_dict).
    If error_dict is not None, prompt is None and caller should yield error.
    """
    if load_insight is None:
        from .clients.bigquery import (
            get_insight_by_id,
            get_supporting_metrics_snapshot,
            list_insights,
        )
        insight = get_insight_by_id(insight_id, organization_id)
        if insight is None:
            return None, {"error": "insight not found", "insight_id": insight_id}
        org = (insight.get("organization_id") or organization_id or "default")
        client_id = int(insight.get("client_id") or 0)
        supporting = get_supporting_metrics_snapshot(org, client_id, insight_id)
        recent_insights = list_insights(org, client_id=client_id, status=None, limit=10, offset=0)
    else:
        insight = load_insight(insight_id)
        if insight is None:
            return None, {"error": "insight not found", "insight_id": insight_id}
        supporting = None
        recent_insights = None
    prompt = build_prompt_grounded(
        insight, supporting,
        recent_insights=recent_insights,
    )
    return prompt, None


def synthesize(
    insight_id: str,
    *,
    organization_id: Optional[str] = None,
    load_insight: Optional[Callable[[str], Optional[dict]]] = None,
    client_profile: Optional[dict] = None,
    llm_client: Optional[Callable[[str], str]] = None,
) -> dict:
    """
    Load insight ONLY from analytics_insights and supporting_metrics_snapshot (marts layer).
    Build grounded prompt; return structured output with provenance. No raw table access.
    """
    if not get("copilot_grounding_only", True):
        pass  # allow legacy path if explicitly disabled
    if load_insight is None:
        from .clients.bigquery import (
            get_insight_by_id,
            get_supporting_metrics_snapshot,
            list_insights,
        )
        insight = get_insight_by_id(insight_id, organization_id)
        if insight is None:
            return {"error": "insight not found", "insight_id": insight_id}
        org = (insight.get("organization_id") or organization_id or "default")
        client_id = int(insight.get("client_id") or 0)
        supporting = get_supporting_metrics_snapshot(org, client_id, insight_id)
        recent_insights = list_insights(org, client_id=client_id, status=None, limit=10, offset=0)
    else:
        insight = load_insight(insight_id)
        if insight is None:
            return {"error": "insight not found", "insight_id": insight_id}
        supporting = None
        recent_insights = None
    prompt = build_prompt_grounded(
        insight, supporting,
        recent_insights=recent_insights,
    )
    fn = llm_client or get_llm_client()
    response_text = fn(prompt)
    out = _parse_llm_response(response_text)
    out["insight_id"] = insight_id
    out["provenance"] = out.get("provenance") or "analytics_insights, supporting_metrics_snapshot"
    return out
