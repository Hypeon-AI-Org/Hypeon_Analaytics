"""
MTA vs MMM reconciliation: compare contribution % per channel, compute delta_pct,
conflict_flag (delta > 30%), overall_alignment_score, alignment_confidence.
"""
from typing import Dict, Any


CONFLICT_THRESHOLD = 0.30


def compute_reconciliation(
    mta_share: Dict[str, float],
    mmm_share: Dict[str, float],
    alignment_confidence: float = 1.0,
) -> Dict[str, Any]:
    """
    Compare MTA and MMM contribution share per channel.
    For each channel: delta_pct = |mta_pct - mmm_pct|, conflict_flag = (delta_pct > 30%).
    overall_alignment_score = 1 - mean(delta_pct), clamped [0, 1].
    alignment_confidence can be passed or default 1.0.
    Returns channel_alignment, overall_alignment_score, alignment_confidence.
    """
    channels = sorted(set(list(mta_share.keys()) + list(mmm_share.keys())))
    if not channels:
        return {
            "channel_alignment": {},
            "overall_alignment_score": 1.0,
            "alignment_confidence": max(0.0, min(1.0, alignment_confidence)),
        }
    channel_alignment: Dict[str, Dict[str, Any]] = {}
    deltas = []
    for ch in channels:
        mta_pct = mta_share.get(ch, 0.0)
        mmm_pct = mmm_share.get(ch, 0.0)
        delta_pct = abs(mta_pct - mmm_pct)
        conflict_flag = delta_pct > CONFLICT_THRESHOLD
        channel_alignment[ch] = {
            "mta_pct": mta_pct,
            "mmm_pct": mmm_pct,
            "delta_pct": delta_pct,
            "conflict_flag": conflict_flag,
        }
        deltas.append(delta_pct)
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
    overall_alignment_score = max(0.0, min(1.0, 1.0 - mean_delta))
    alignment_confidence = max(0.0, min(1.0, alignment_confidence))
    return {
        "channel_alignment": channel_alignment,
        "overall_alignment_score": overall_alignment_score,
        "alignment_confidence": alignment_confidence,
    }
