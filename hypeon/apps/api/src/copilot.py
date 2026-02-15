"""
Copilot: answer natural-language questions using dashboard data.
Designed for founders and non-technical users; uses metrics, decisions, MMM, and reports.
"""
from datetime import date, timedelta
import os
import re
from typing import Any, Optional

from sqlmodel import Session, select

from packages.shared.src.models import (
    DecisionStore,
    MMMResults,
    UnifiedDailyMetrics,
)
from packages.shared.src.dates import parse_date_range
from packages.metrics.src.attribution_mmm_report import build_attribution_mmm_report


def get_copilot_context(
    session: Session,
    lookback_days: int = 90,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict[str, Any]:
    """
    Build a summary of current data for Copilot answers (same data as dashboard).
    If start_date/end_date are provided, use that range; else use lookback_days from today.
    """
    if start_date is not None and end_date is not None:
        start, end = start_date, end_date
    else:
        start, end = parse_date_range(
            start=date.today() - timedelta(days=lookback_days),
            end=date.today(),
            default_days=lookback_days,
        )
    # Unified metrics summary (dashboard-aligned)
    stmt = select(UnifiedDailyMetrics).where(
        UnifiedDailyMetrics.date >= start,
        UnifiedDailyMetrics.date <= end,
    )
    rows = list(session.exec(stmt).all())
    by_channel: dict[str, dict[str, float]] = {}
    total_spend = 0.0
    total_revenue = 0.0
    by_date: dict[str, dict[str, float]] = {}  # date -> {spend, revenue} for trend
    for r in rows:
        if r.channel not in by_channel:
            by_channel[r.channel] = {"spend": 0.0, "revenue": 0.0}
        by_channel[r.channel]["spend"] += r.spend
        by_channel[r.channel]["revenue"] += r.attributed_revenue
        total_spend += r.spend
        total_revenue += r.attributed_revenue
        dt = r.date.isoformat()
        if dt not in by_date:
            by_date[dt] = {"spend": 0.0, "revenue": 0.0}
        by_date[dt]["spend"] += r.spend
        by_date[dt]["revenue"] += r.attributed_revenue
    channel_list = sorted(by_channel.keys())
    roas_by_channel = {}
    for ch in channel_list:
        s = by_channel[ch]["spend"] or 1
        roas_by_channel[ch] = round(by_channel[ch]["revenue"] / s, 2)
    # Recent vs previous period trend (last 7 days vs prior 7)
    sorted_dates = sorted(by_date.keys())
    trend_text = None
    if len(sorted_dates) >= 14:
        recent_dates = sorted_dates[-7:]
        prior_dates = sorted_dates[-14:-7]
        recent_spend = sum(by_date[d]["spend"] for d in recent_dates)
        recent_rev = sum(by_date[d]["revenue"] for d in recent_dates)
        prior_spend = sum(by_date[d]["spend"] for d in prior_dates)
        prior_rev = sum(by_date[d]["revenue"] for d in prior_dates)
        trend_text = (
            f"Last 7 days: spend ${recent_spend:,.0f}, revenue ${recent_rev:,.0f}. "
            f"Previous 7 days: spend ${prior_spend:,.0f}, revenue ${prior_rev:,.0f}."
        )
    # Decisions
    decisions_stmt = select(DecisionStore).order_by(DecisionStore.created_at.desc()).limit(50)
    decisions = list(session.exec(decisions_stmt).all())
    pending = sum(1 for d in decisions if d.status == "pending")
    # MMM
    mmm_stmt = select(MMMResults).order_by(MMMResults.created_at.desc()).limit(20)
    mmm_rows = list(session.exec(mmm_stmt).all())
    mmm_run_id = mmm_rows[0].run_id if mmm_rows else None
    mmm_by_channel = {}
    for r in mmm_rows:
        if r.run_id == mmm_run_id:
            mmm_by_channel[r.channel] = r.coefficient
    r2 = mmm_rows[0].goodness_of_fit_r2 if mmm_rows else None
    # Attribution vs MMM report
    report = build_attribution_mmm_report(session, start, end)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "lookback_days": lookback_days,
        "channels": channel_list,
        "spend_by_channel": {ch: round(by_channel[ch]["spend"], 2) for ch in channel_list},
        "revenue_by_channel": {ch: round(by_channel[ch]["revenue"], 2) for ch in channel_list},
        "roas_by_channel": roas_by_channel,
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "roas_overall": round(total_revenue / total_spend, 2) if total_spend else 0,
        "recent_vs_prior_trend": trend_text,
        "decisions_total": len(decisions),
        "decisions_pending": pending,
        "decisions_sample": [
            {
                "entity_type": d.entity_type,
                "decision_type": d.decision_type,
                "explanation_text": d.explanation_text,
                "confidence_score": d.confidence_score,
            }
            for d in decisions[:5]
        ],
        "mmm_last_run_id": mmm_run_id,
        "mmm_coefficients": mmm_by_channel,
        "mmm_r2": round(r2, 4) if r2 is not None else None,
        "attribution_mmm_report": {
            "channels": report["channels"],
            "attribution_share": report["attribution_share"],
            "mmm_share": report["mmm_share"],
            "disagreement_score": report["disagreement_score"],
            "instability_flagged": report["instability_flagged"],
        },
    }


def _normalize(q: str) -> str:
    return re.sub(r"\s+", " ", q.lower().strip())


def _answer_from_templates(question: str, ctx: dict[str, Any]) -> tuple[str, list[str]]:
    """
    Match question intent and fill template with context.
    Returns (answer, list of source descriptions).
    """
    q = _normalize(question)
    sources = ["Unified metrics", "Decisions", "MMM results", "Attribution vs MMM report"]

    # How are we doing? / How's performance?
    if any(
        x in q
        for x in (
            "how are we doing",
            "how is performance",
            "how's performance",
            "overall performance",
            "summary",
            "high level",
        )
    ):
        rev = ctx["total_revenue"]
        spend = ctx["total_spend"]
        roas = ctx["roas_overall"]
        ch = ", ".join(ctx["channels"]) or "no channels"
        return (
            f"Over the last {ctx['lookback_days']} days, total ad spend was ${spend:,.2f} "
            f"and attributed revenue was ${rev:,.2f}, for an overall ROAS of {roas}. "
            f"Channels in the data: {ch}. "
            "Use the Dashboard for detailed metrics by channel and date."
        ), sources

    # Spend by channel
    if any(
        x in q
        for x in (
            "spend by channel",
            "spending per channel",
            "how much we spend",
            "where we spend",
            "channel spend",
        )
    ):
        parts = [
            f"{ch}: ${ctx['spend_by_channel'].get(ch, 0):,.2f}"
            for ch in ctx["channels"]
        ]
        return (
            f"Spend by channel ({ctx['start_date']} to {ctx['end_date']}): "
            + "; ".join(parts)
            + ". Check the Dashboard for daily breakdowns."
        ), sources

    # Revenue by channel
    if any(
        x in q
        for x in (
            "revenue by channel",
            "revenue per channel",
            "which channel drives",
            "revenue by channel",
        )
    ):
        parts = [
            f"{ch}: ${ctx['revenue_by_channel'].get(ch, 0):,.2f}"
            for ch in ctx["channels"]
        ]
        return (
            f"Attributed revenue by channel: " + "; ".join(parts) + "."
        ), sources

    # ROAS
    if any(x in q for x in ("roas", "return on ad spend", "efficiency")):
        roas = ctx["roas_overall"]
        return (
            f"Overall ROAS for the period is {roas} (attributed revenue / ad spend). "
            "Use the Dashboard to see ROAS by channel and over time."
        ), sources

    # Decisions / recommendations
    if any(
        x in q
        for x in (
            "decisions",
            "recommendations",
            "what should we do",
            "suggestions",
            "pending",
            "actions",
        )
    ):
        total = ctx["decisions_total"]
        pending = ctx["decisions_pending"]
        if total == 0:
            return (
                "There are no decisions in the system yet. Run the pipeline (Dashboard → Run pipeline) "
                "to generate recommendations based on your metrics and MMM model."
            ), sources
        sample = ctx.get("decisions_sample") or []
        lines = [f"You have {total} decisions ({pending} pending)."]
        for s in sample[:3]:
            lines.append(
                f"- {s['entity_type']} / {s['decision_type']}: {s.get('explanation_text') or s['reason_code']} "
                f"(confidence {s['confidence_score']:.0%})"
            )
        return " ".join(lines) + " See the Dashboard → Decisions for the full list.", sources

    # MMM / model
    if any(
        x in q
        for x in (
            "model",
            "mmm",
            "marketing mix",
            "coefficient",
            "contribution",
        )
    ):
        run_id = ctx.get("mmm_last_run_id")
        if not run_id:
            return (
                "No MMM run found. Run the pipeline from the Dashboard to train the model and get channel coefficients."
            ), sources
        coefs = ctx.get("mmm_coefficients") or {}
        r2 = ctx.get("mmm_r2")
        parts = [f"{ch}: {coefs.get(ch, 0):.4f}" for ch in ctx["channels"]]
        r2_str = f" Model fit (R²): {r2}." if r2 is not None else ""
        return (
            f"Latest MMM run: {run_id}. Channel coefficients: " + "; ".join(parts) + "." + r2_str
        ), sources

    # Best / top performing channel
    if any(
        x in q
        for x in (
            "best channel",
            "which channel performs",
            "top channel",
            "strongest channel",
        )
    ):
        channels = ctx["channels"]
        if not channels:
            return "No channel data yet. Run the pipeline from the Dashboard to load data.", sources
        spend_ch = ctx.get("spend_by_channel") or {}
        rev_ch = ctx.get("revenue_by_channel") or {}
        roas_ch = {}
        for ch in channels:
            s = spend_ch.get(ch, 0) or 1
            r = rev_ch.get(ch, 0)
            roas_ch[ch] = r / s if s else 0
        best = max(channels, key=lambda c: roas_ch.get(c, 0))
        best_roas = roas_ch.get(best, 0)
        return (
            f"Based on attributed revenue and spend, {best} has the highest ROAS ({best_roas:.2f}) in this period. "
            "Use the Dashboard → Metrics to compare channels over time, and → Optimizer for budget allocation."
        ), sources

    # Budget / optimize
    if any(
        x in q
        for x in (
            "budget",
            "optimize",
            "allocate",
            "how to spend",
        )
    ):
        return (
            "Use the Dashboard → Optimizer: enter your total budget and get a recommended split across channels "
            "based on the MMM model. You can also use the Simulator to see projected revenue for spend changes."
        ), sources

    # Attribution vs MMM
    if any(
        x in q
        for x in (
            "attribution",
            "mmm comparison",
            "disagree",
            "instability",
        )
    ):
        r = ctx.get("attribution_mmm_report") or {}
        flag = r.get("instability_flagged", False)
        score = r.get("disagreement_score", 0)
        if flag:
            return (
                f"Attribution and MMM are showing some disagreement (score {score:.2f}). "
                "This can happen when last-touch attribution and model-based contribution differ. "
                "Review the Dashboard → Attribution vs MMM report for details."
            ), sources
        return (
            f"Attribution vs MMM disagreement score is {score:.2f}; no major instability flagged. "
            "See the report in the Dashboard for channel-level comparison."
        ), sources

    # Scale / grow
    if any(x in q for x in ("scale", "grow", "increase spend", "should we spend more")):
        return (
            "Check the Dashboard → Decisions for recommendations (scale up/scale down by channel). "
            "Use → Optimizer to see how to allocate a larger budget, and → Simulator to test spend changes before committing."
        ), sources

    # Default
    return (
        "I can answer questions about your ad spend, revenue, ROAS, decisions, MMM model, and budget optimization. "
        "Try: \"How are we doing?\", \"Spend by channel\", \"Which channel performs best?\", \"What decisions do we have?\", or \"How do I optimize budget?\""
    ), ["General guidance"]


def _build_llm_prompt(question: str, ctx: dict[str, Any]) -> str:
    """Prompt so the model answers like an experienced marketing specialist to a founder."""
    return (
        "You are an experienced marketing specialist advising a founder. Use ONLY the data below. "
        "Be concise, data-driven, and actionable. Use specific numbers from the data. "
        "Recommend clear next steps when relevant (e.g. 'Check Dashboard → Decisions' or 'Run the pipeline'). "
        "Write in a confident, professional tone. Answer in 2–5 sentences unless more detail is needed.\n\n"
        "Data (dashboard metrics, decisions, MMM, attribution):\n"
        f"{ctx}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def generate_copilot_answer(session: Session, question: str) -> tuple[str, list[str]]:
    """
    Generate a plain-language answer from dashboard data.
    Prefers Gemini if GEMINI_API_KEY is set, else OpenAI if OPENAI_API_KEY is set, else templates.
    Returns (answer_text, sources).
    """
    ctx = get_copilot_context(session)
    q = question.strip()
    use_llm = len(q) > 10

    if use_llm and os.environ.get("GEMINI_API_KEY"):
        try:
            return _answer_with_gemini(question, ctx)
        except Exception:
            pass

    if use_llm and os.environ.get("OPENAI_API_KEY"):
        try:
            return _answer_with_openai(question, ctx)
        except Exception:
            pass

    return _answer_from_templates(question, ctx)


def _answer_with_gemini(question: str, ctx: dict[str, Any]) -> tuple[str, list[str]]:
    """Use Google Gemini API to generate answer from dashboard context."""
    try:
        import google.generativeai as genai
    except ImportError:
        return _answer_from_templates(question, ctx)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _answer_from_templates(question, ctx)

    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)
    prompt = _build_llm_prompt(question, ctx)

    response = model.generate_content(prompt)
    text = (response.text or "").strip()
    if not text:
        return _answer_from_templates(question, ctx)
    return text, ["Unified metrics", "Decisions", "MMM", "Attribution report"]


def stream_answer_with_gemini(question: str, ctx: dict[str, Any]):
    """
    Yield (delta_text, sources). For each content chunk yield (chunk, None);
    at the end yield (None, sources). If Gemini is unavailable, yields one (full, sources).
    """
    try:
        import google.generativeai as genai
    except ImportError:
        full, sources = _answer_from_templates(question, ctx)
        yield full, None
        yield None, sources
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        full, sources = _answer_from_templates(question, ctx)
        yield full, None
        yield None, sources
        return

    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)
    prompt = _build_llm_prompt(question, ctx)
    sources = ["Unified metrics", "Decisions", "MMM", "Attribution report"]

    try:
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text, None
        yield None, sources
    except Exception:
        full, sources = _answer_from_templates(question, ctx)
        yield full, None
        yield None, sources


def _answer_with_openai(question: str, ctx: dict[str, Any]) -> tuple[str, list[str]]:
    """Use OpenAI to generate a friendlier answer with same context."""
    try:
        import openai
    except ImportError:
        return _answer_from_templates(question, ctx)

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    prompt = _build_llm_prompt(question, ctx)
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        return _answer_from_templates(question, ctx)
    return text, ["Unified metrics", "Decisions", "MMM", "Attribution report"]
