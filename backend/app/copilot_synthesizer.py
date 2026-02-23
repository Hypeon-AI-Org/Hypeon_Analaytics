"""
Copilot synthesis: build LLM prompt from analytics_insight + evidence + client_profile;
return structured summary, explanation, action steps, provenance, confidence, TL;DR.
RAG: optional FAISS retrieval of similar past insights (V1 placeholder).
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

# Injectable LLM call for tests
_llm_client: Optional[Callable[[str], str]] = None


def set_llm_client(fn: Callable[[str], str]) -> None:
    global _llm_client
    _llm_client = fn


def get_llm_client() -> Callable[[str], str]:
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    # Default: stub that returns a fixed structure (no API key required in tests)
    def _stub(prompt: str) -> str:
        return json.dumps({
            "summary": "Summary from stub.",
            "explanation": "Explanation with top 3 evidence points (stub).",
            "action_steps": ["Step 1 (stub)", "Step 2 (stub)"],
            "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
            "provenance": "rules_engine",
            "confidence": 0.85,
            "tldr": "TL;DR stub.",
        })
    return _stub


PROMPT_TEMPLATE = """You are an analytics copilot. Given the following insight and evidence, produce a structured response.

## Insight
{insight_json}

## Evidence (compact)
{evidence_table}

## Client profile (optional)
{client_profile}

## Output format (JSON only)
Return a single JSON object with exactly these keys:
- summary: short 1-2 sentence summary
- explanation: 2-3 sentences with top 3 evidence points
- action_steps: array of 1-3 concrete action steps
- expected_impact: object with metric, estimate, units
- provenance: source (e.g. rules_engine, anomaly)
- confidence: number 0-1
- tldr: one line takeaway

JSON:
"""


def _evidence_to_table(evidence: list[dict]) -> str:
    if not evidence:
        return "No evidence."
    lines = ["metric | value | baseline | period"]
    for e in evidence[:10]:
        m = e.get("metric", "")
        v = e.get("value", 0)
        b = e.get("baseline", 0)
        p = e.get("period", "")
        lines.append(f"{m} | {v} | {b} | {p}")
    return "\n".join(lines)


def build_prompt(insight: dict, client_profile: Optional[dict] = None) -> str:
    """Build the LLM prompt from insight and optional client_profile."""
    evidence = insight.get("evidence") or []
    return PROMPT_TEMPLATE.format(
        insight_json=json.dumps(insight, default=str),
        evidence_table=_evidence_to_table(evidence),
        client_profile=json.dumps(client_profile or {}, default=str),
    )


def _parse_llm_response(text: str) -> dict:
    """Parse LLM response to structured dict. Tolerate markdown code block."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```json") else 0
        end = next((i for i, L in enumerate(lines) if L.strip() == "```"), len(lines))
        text = "\n".join(lines[start:end])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": text[:200],
            "explanation": "",
            "action_steps": [],
            "expected_impact": {"metric": "", "estimate": 0.0, "units": ""},
            "provenance": "unknown",
            "confidence": 0.5,
            "tldr": text[:100],
        }


def synthesize(
    insight_id: str,
    *,
    load_insight: Optional[Callable[[str], Optional[dict]]] = None,
    client_profile: Optional[dict] = None,
    llm_client: Optional[Callable[[str], str]] = None,
) -> dict:
    """
    Load insight by id, build prompt, call LLM, return structured output.
    If load_insight is None, uses BigQuery client to fetch from analytics_insights.
    """
    if load_insight is None:
        from .clients.bigquery import get_client, get_analytics_dataset
        import os
        client = get_client()
        project = os.environ.get("BQ_PROJECT", "braided-verve-459208-i6")
        dataset = get_analytics_dataset()
        query = f"""
        SELECT * FROM `{project}.{dataset}.analytics_insights`
        WHERE insight_id = '{insight_id}'
        LIMIT 1
        """
        df = client.query(query).to_dataframe()
        if df.empty:
            return {"error": "insight not found", "insight_id": insight_id}
        row = df.iloc[0].to_dict()
        # Convert any non-serializable
        insight = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}
        # evidence may be list of dicts
        if "evidence" in insight and hasattr(insight["evidence"], "__iter__") and not isinstance(insight["evidence"], (str, bytes)):
            insight["evidence"] = [dict(e) if hasattr(e, "keys") else e for e in insight["evidence"]]
    else:
        insight = load_insight(insight_id)
        if insight is None:
            return {"error": "insight not found", "insight_id": insight_id}

    prompt = build_prompt(insight, client_profile)
    fn = llm_client or get_llm_client()
    response_text = fn(prompt)
    out = _parse_llm_response(response_text)
    out["insight_id"] = insight_id
    return out
