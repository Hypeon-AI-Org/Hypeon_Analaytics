"""
Decision engine: enrich DecisionStore rows with reasoning, risk_flags, model_versions, run_id.
Decision confidence = mta_confidence * mmm_confidence * alignment_score (clamped [0, 1]).
Build enriched decision at read time; no DB schema change.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

from packages.shared.src.models import DecisionStore
from packages.governance.src.versions import DECISION_VERSION


@dataclass
class Rule:
    """Rule definition: id, name, condition, action, priority, weight."""
    id: str
    name: str
    condition: str
    action: str
    priority: int
    weight: float = 1.0


def decision_confidence(
    mta_confidence: float,
    mmm_confidence: float,
    alignment_score: float,
) -> float:
    """
    Combined decision confidence: mta_confidence * mmm_confidence * alignment_score.
    Clamped to [0, 1].
    """
    c = mta_confidence * mmm_confidence * alignment_score
    return max(0.0, min(1.0, c))


def _recommended_action_from_decision_type(decision_type: str) -> str:
    """Map decision_type to recommended_action string."""
    return decision_type.replace("_", " ").title() if decision_type else "Review"


def _budget_change_pct_from_projected(projected_impact: Optional[float]) -> Optional[float]:
    """Map projected_impact to budget_change_pct (e.g. 0.1 -> 10)."""
    if projected_impact is None:
        return None
    return round(projected_impact * 100.0, 2)


def _risk_flags_for_channel(
    channel: str,
    alignment: Optional[Dict[str, Any]] = None,
    conflict_threshold: float = 0.30,
) -> List[str]:
    """Build risk_flags list from reconciliation and context."""
    flags = []
    if alignment and channel in alignment.get("channel_alignment", {}):
        ch_align = alignment["channel_alignment"][channel]
        if ch_align.get("conflict_flag"):
            flags.append("mta_mmm_conflict")
    return flags


def enrich_decision_row(
    row: DecisionStore,
    run_id: Optional[str] = None,
    mta_version: Optional[str] = None,
    mmm_version: Optional[str] = None,
    mta_confidence: float = 0.5,
    mmm_confidence: float = 0.5,
    alignment_score: float = 1.0,
    alignment_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Enrich a single DecisionStore row into full decision output shape.
    confidence_score = mta_confidence * mmm_confidence * alignment_score (clamped).
    """
    channel = row.entity_id if row.entity_type == "channel" else row.entity_id
    conf = decision_confidence(mta_confidence, mmm_confidence, alignment_score)
    risk_flags = _risk_flags_for_channel(channel, alignment_result)
    if row.confidence_score is not None and row.confidence_score < 0.3:
        risk_flags.append("low_confidence")
    return {
        "decision_id": row.decision_id,
        "channel": channel,
        "recommended_action": _recommended_action_from_decision_type(row.decision_type),
        "budget_change_pct": _budget_change_pct_from_projected(row.projected_impact),
        "reasoning": {
            "mta_support": mta_confidence,
            "mmm_support": mmm_confidence,
            "alignment_score": alignment_score,
        },
        "risk_flags": risk_flags,
        "confidence_score": conf,
        "model_versions": {
            "mta_version": mta_version or "mta_v1.1",
            "mmm_version": mmm_version or "mmm_v2.0",
        },
        "run_id": run_id or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "decision_type": row.decision_type,
        "explanation_text": row.explanation_text,
        "status": row.status,
    }


def enrich_decisions(
    rows: List[DecisionStore],
    run_id: Optional[str] = None,
    mta_version: Optional[str] = None,
    mmm_version: Optional[str] = None,
    mta_confidence: float = 0.5,
    mmm_confidence: float = 0.5,
    alignment_score: float = 1.0,
    alignment_result: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Enrich a list of DecisionStore rows into full decision output shape."""
    return [
        enrich_decision_row(
            row,
            run_id=run_id,
            mta_version=mta_version,
            mmm_version=mmm_version,
            mta_confidence=mta_confidence,
            mmm_confidence=mmm_confidence,
            alignment_score=alignment_score,
            alignment_result=alignment_result,
        )
        for row in rows
    ]
