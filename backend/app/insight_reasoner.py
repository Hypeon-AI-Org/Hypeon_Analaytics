"""
Insight Reasoning Layer: Signals -> Context -> Reasoned Insight.
Aggregates signals from all agents, merges related findings, adds business reasoning, produces final insight.
Agents send signals; this layer produces the canonical insight object.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# Map signal combinations to root cause and impact
ROOT_CAUSE_MAP = {
    ("roas_drop", "conversion_drop"): ("Traffic quality degradation", "HIGH", 0.88),
    ("roas_drop", "bounce_rate_increase"): ("Traffic quality degradation", "HIGH", 0.85),
    ("roas_drop",): ("ROAS decline vs baseline", "HIGH", 0.82),
    ("conversion_drop",): ("Conversion rate decline", "MEDIUM", 0.78),
    ("bounce_rate_increase",): ("Engagement drop", "MEDIUM", 0.75),
    ("waste_zero_revenue",): ("Spend with zero revenue", "HIGH", 0.90),
    ("scale_opportunity",): ("Scaling opportunity", "LOW", 0.80),
    ("funnel_leak",): ("Funnel leakage", "MEDIUM", 0.77),
    ("anomaly",): ("Anomaly detected", "MEDIUM", 0.72),
}


def _signals_key(signals: list[str]) -> tuple:
    return tuple(sorted(set(s.strip() for s in signals if s)))


def _infer_root_cause_and_impact(signals: list[str]) -> tuple[str, str, float]:
    key = _signals_key(signals)
    for pattern, (cause, impact, conf) in sorted(ROOT_CAUSE_MAP.items(), key=lambda x: -len(x[0])):
        if set(pattern).issubset(set(signals)):
            return cause, impact, conf
    if signals:
        return "Multiple signals", "MEDIUM", 0.70
    return "Unknown", "LOW", 0.5


def _recommendation_from_signals(signals: list[str], impact: str) -> str:
    s = set(signals)
    if "waste_zero_revenue" in s or "roas_drop" in s:
        return "Reduce spend by 25% and review targeting."
    if "scale_opportunity" in s:
        return "Increase budget by 15–20% on top performers."
    if "conversion_drop" in s or "bounce_rate_increase" in s:
        return "Audit landing pages and audience overlap."
    if impact == "HIGH":
        return "Review campaign and pause or reallocate budget."
    return "Monitor and reassess in 7 days."


def _entity_key(item: dict) -> tuple[str, str, int]:
    return (
        str(item.get("organization_id") or ""),
        str(item.get("entity_id") or item.get("entity") or ""),
        int(item.get("client_id") or 0),
    )


def _extract_signals(item: dict) -> list[str]:
    if "signals" in item:
        return list(item["signals"]) if isinstance(item["signals"], (list, tuple)) else [str(item["signals"])]
    if item.get("insight_type"):
        return [str(item["insight_type"])]
    return []


def _insight_id_from_signals(organization_id: str, entity_id: str, client_id: int, period: str) -> str:
    raw = f"reasoned|{organization_id}|{entity_id}|{client_id}|{period}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def reason_insights(
    agent_outputs: list[dict[str, Any]],
    *,
    period: str | None = None,
    organization_id: str = "default",
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Aggregate signals by entity, infer root_cause and impact_level, produce one reasoned insight per entity.
    agent_outputs: list of { entity_id or entity, signals (list), client_id, organization_id?, ... }
    or existing insight-like dicts (insight_type treated as single signal).
    """
    period = period or datetime.now(timezone.utc).date().isoformat()
    by_entity: dict[tuple, dict] = {}

    for item in agent_outputs:
        key = _entity_key(item)
        if key not in by_entity:
            by_entity[key] = {
                "organization_id": item.get("organization_id") or organization_id,
                "client_id": item.get("client_id", 0),
                "workspace_id": item.get("workspace_id") or workspace_id,
                "entity_type": item.get("entity_type", "campaign"),
                "entity_id": item.get("entity_id") or item.get("entity", ""),
                "signals": [],
                "evidence": list(item.get("evidence") or []),
                "detected_by": list(item.get("detected_by") or []),
            }
        agg = by_entity[key]
        signals = _extract_signals(item)
        for s in signals:
            if s and s not in agg["signals"]:
                agg["signals"].append(s)
        if item.get("evidence"):
            seen_ev = set()
            for e in agg.get("evidence") or []:
                if isinstance(e, dict):
                    seen_ev.add(tuple(sorted(e.items())))
            agg["evidence"] = [dict(x) for x in list(seen_ev)[:20]]
        if item.get("detected_by"):
            for d in item["detected_by"]:
                if d and d not in agg["detected_by"]:
                    agg["detected_by"].append(d)

    out = []
    for key, agg in by_entity.items():
        signals = agg["signals"]
        root_cause, impact_level, confidence = _infer_root_cause_and_impact(signals)
        recommended_action = _recommendation_from_signals(signals, impact_level)
        entity_id = agg["entity_id"]
        client_id = agg["client_id"]
        org = agg["organization_id"]
        insight_id = _insight_id_from_signals(org, entity_id, client_id, period)
        out.append({
            "insight_id": insight_id,
            "organization_id": org,
            "client_id": client_id,
            "workspace_id": agg.get("workspace_id"),
            "entity_type": agg["entity_type"],
            "entity_id": entity_id,
            "insight_type": "reasoned_" + (signals[0] if signals else "unknown"),
            "summary": f"{root_cause}: {', '.join(signals[:5])}",
            "explanation": f"Signals ({', '.join(signals)}) indicate {root_cause}. Impact: {impact_level}.",
            "recommendation": recommended_action,
            "root_cause": root_cause,
            "impact_level": impact_level,
            "confidence": round(confidence, 2),
            "expected_impact_value": 0.1 if impact_level == "LOW" else (0.2 if impact_level == "MEDIUM" else 0.3),
            "evidence": agg.get("evidence", [])[:10],
            "detected_by": agg.get("detected_by", []),
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "insight_hash": insight_id,
            "signals": signals,
        })
    return out
