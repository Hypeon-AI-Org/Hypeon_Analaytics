"""
Cross-agent deduplication: merge similar entity insights, combine evidence, preserve provenance.
Example: trend_agent + performance_agent -> single unified insight.
"""
from __future__ import annotations

from typing import Any

from .config_loader import get

THRESHOLD = 0.85


def _entity_key(insight: dict) -> tuple[str, str, str, str]:
    return (
        str(insight.get("organization_id") or ""),
        str(insight.get("client_id") or ""),
        str(insight.get("entity_type") or ""),
        str(insight.get("entity_id") or ""),
    )


def _similar(a: dict, b: dict) -> bool:
    if _entity_key(a) != _entity_key(b):
        return False
    ta = a.get("insight_type") or ""
    tb = b.get("insight_type") or ""
    if ta == tb:
        return True
    similar_pairs = {
        ("roas_decline", "waste_zero_revenue"),
        ("scale_opportunity", "roas_decline"),
    }
    return (ta, tb) in similar_pairs or (tb, ta) in similar_pairs


def _merge_evidence(ev1: list, ev2: list) -> list:
    seen = set()
    out = []
    for e in (ev1 or []) + (ev2 or []):
        if isinstance(e, dict):
            k = (e.get("metric"), e.get("period"))
        else:
            k = (getattr(e, "metric", None), getattr(e, "period", None))
        if k in seen:
            continue
        seen.add(k)
        out.append(e if isinstance(e, dict) else dict(e))
    return out[:20]


def _merge_detected_by(d1: list, d2: list) -> list:
    seen = set()
    out = []
    for x in (d1 or []) + (d2 or []):
        s = str(x)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def merge_insights(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Merge similar entity insights: same org/client/entity_type/entity_id and similar type.
    Combine evidence and detected_by; keep first insight_id and highest confidence.
    """
    if not insights:
        return []
    threshold = get("insight_merge_similarity_threshold", THRESHOLD)
    merged: list[dict[str, Any]] = []
    used: set[int] = set()
    for i, a in enumerate(insights):
        if i in used:
            continue
        base = dict(a)
        base["evidence"] = list(base.get("evidence") or [])
        base["detected_by"] = list(base.get("detected_by") or [])
        for j, b in enumerate(insights):
            if j <= i or j in used:
                continue
            if not _similar(a, b):
                continue
            used.add(j)
            base["evidence"] = _merge_evidence(base["evidence"], b.get("evidence") or [])
            base["detected_by"] = _merge_detected_by(base["detected_by"], b.get("detected_by") or [])
            if (b.get("confidence") or 0) > (base.get("confidence") or 0):
                base["confidence"] = b["confidence"]
            if b.get("summary") and len(str(b["summary"])) > len(str(base.get("summary") or "")):
                base["summary"] = b["summary"]
        merged.append(base)
    return merged
