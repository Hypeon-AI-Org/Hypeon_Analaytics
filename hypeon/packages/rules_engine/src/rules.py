"""Decision rules: scale_up/scale_down, pause, reallocate from metrics + MMM + store_config."""
from datetime import date
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from packages.shared.src.enums import DecisionStatus, DecisionType, EntityType
from packages.shared.src.models import DecisionStore, MMMResults, StoreConfig, UnifiedDailyMetrics
from packages.rules_engine.src.confidence import confidence_score


def _get_config(session: Session, key: str, default_float: Optional[float] = None) -> Optional[float]:
    r = session.exec(select(StoreConfig).where(StoreConfig.key == key)).first()
    if r and r.value_float is not None:
        return r.value_float
    return default_float


def _latest_mmm_r2(session: Session, run_id: Optional[str] = None) -> Optional[float]:
    stmt = select(MMMResults).order_by(MMMResults.created_at.desc())
    if run_id:
        stmt = stmt.where(MMMResults.run_id == run_id)
    r = session.exec(stmt).first()
    return r.goodness_of_fit_r2 if r else None


def evaluate_rules(
    session: Session,
    start_date: date,
    end_date: date,
    mmm_run_id: Optional[str] = None,
) -> List[DecisionStore]:
    """
    Evaluate scaling and fatigue rules from unified_daily_metrics and mmm_results.
    Returns list of DecisionStore rows to insert.
    """
    decisions = []
    roas_scale_up = _get_config(session, "roas_scale_up_threshold", 2.0)
    roas_scale_down = _get_config(session, "roas_scale_down_threshold", 0.5)
    r2 = _latest_mmm_r2(session, mmm_run_id)
    metrics = session.exec(
        select(UnifiedDailyMetrics).where(
            UnifiedDailyMetrics.date >= start_date,
            UnifiedDailyMetrics.date <= end_date,
        )
    ).all()
    n = len(metrics)
    conf = confidence_score(r2=r2, sample_size=n, reference_date=end_date)
    by_channel: Dict[str, List[UnifiedDailyMetrics]] = {}
    for m in metrics:
        by_channel.setdefault(m.channel, []).append(m)
    for channel, rows in by_channel.items():
        total_spend = sum(r.spend for r in rows)
        total_rev = sum(r.attributed_revenue for r in rows)
        roas = total_rev / total_spend if total_spend else 0.0
        if roas_scale_up is not None and roas >= roas_scale_up:
            decisions.append(
                DecisionStore(
                    entity_type=EntityType.CHANNEL.value,
                    entity_id=channel,
                    decision_type=DecisionType.SCALE_UP.value,
                    reason_code="roas_above_threshold",
                    explanation_text=f"Channel {channel} ROAS {roas:.2f} >= {roas_scale_up}; recommend scaling up.",
                    projected_impact=0.1,
                    confidence_score=conf,
                    status=DecisionStatus.PENDING.value,
                )
            )
        if roas_scale_down is not None and roas <= roas_scale_down and total_spend > 0:
            decisions.append(
                DecisionStore(
                    entity_type=EntityType.CHANNEL.value,
                    entity_id=channel,
                    decision_type=DecisionType.SCALE_DOWN.value,
                    reason_code="roas_below_threshold",
                    explanation_text=f"Channel {channel} ROAS {roas:.2f} <= {roas_scale_down}; consider scaling down.",
                    projected_impact=-0.1,
                    confidence_score=conf,
                    status=DecisionStatus.PENDING.value,
                )
            )
    if not decisions:
        decisions.append(
            DecisionStore(
                entity_type=EntityType.CHANNEL.value,
                entity_id="all",
                decision_type=DecisionType.REALLOCATE_BUDGET.value,
                reason_code="no_signal",
                explanation_text="Insufficient signal for scale decisions; suggest reallocate based on MMM.",
                projected_impact=None,
                confidence_score=conf,
                status=DecisionStatus.PENDING.value,
            )
        )
    return decisions


def run_rules(
    session: Session,
    start_date: date,
    end_date: date,
    mmm_run_id: Optional[str] = None,
) -> int:
    """Evaluate rules and insert into decision_store. Returns count of decisions written."""
    decisions = evaluate_rules(session, start_date, end_date, mmm_run_id=mmm_run_id)
    for d in decisions:
        session.add(d)
    session.commit()
    return len(decisions)
