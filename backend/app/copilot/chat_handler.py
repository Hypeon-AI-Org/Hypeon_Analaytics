"""
Copilot chat: discover tables from org-configured datasets → LLM generates SQL from schema + guide → run → validate → format.
Fully dynamic: no hardcoded datasets or SQL templates. Each org uses only their configured data. Response: { answer, data, text, session_id }.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Generator, List, Optional, Set

_title_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="copilot_title")
_sql_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="copilot_sql")
_SQL_BACKGROUND_TIMEOUT_SEC = 30

from .defaults import get_max_retries
from .schema_summary import MAX_SUMMARY_CHARS
from .tools import discover_tables as tools_discover_tables, run_bigquery_sql, _serialize_rows
from .validator import validate as validate_result
from . import copilot_metrics

logger = logging.getLogger(__name__)

# Dataset type -> human-readable label (used when injecting dataset context into prompts; no hardcoded dataset names).
_DATASET_TYPE_LABELS = {
    "google_ads": "Google Ads",
    "ga4": "GA4",
    "meta_ads": "Meta Ads",
    "pinterest": "Pinterest",
    "marts": "Marts",
    "marts_ads": "Marts (Ads)",
    "ads": "Ads",
}

_SQL_GUIDE = """You are a BigQuery SQL expert for a read-only analytics warehouse. Output exactly one BigQuery SELECT query that answers the user question. No explanation—only the query.

Rules:
- Use ONLY tables and columns from the schema below. Quote table names as `project.dataset.table`. You may JOIN or UNION across tables when the question requires it.
- Output a single SELECT (or WITH ... SELECT). No semicolon. Add LIMIT (e.g. 500) to cap result size.
- Match the user's intent: use columns that fit the question (revenue, product, channel, campaign, date, etc.). If a "Dataset labels" or schema summary is provided, use it to pick the right source (e.g. Google Ads, GA4, Meta Ads) for the question.
- Dates: For STRING columns in YYYYMMDD format use PARSE_DATE('%Y%m%d', col) or event_date >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)). For DATE/TIMESTAMP use standard comparisons. Do not CAST string dates to DATE.
- If the schema includes client_id and the question is about this client, filter with client_id = {client_id}.
- Read-only: only SELECT is allowed. No INSERT, UPDATE, DELETE, DDL, or multiple statements.
- Do not reference tables or columns not listed. Do not output markdown or prose—only the SQL. Use ```sql ... ``` if you use a code block."""

_FORMAT_SYSTEM = """You are a marketing analytics assistant. Turn the query result into a clear, readable answer. Be concise; do not invent data.

- Start with a short summary or bullets. Add sections (##) and small markdown tables when the result is large or multi-faceted.
- Use proper markdown tables (header, separator, rows with one newline between). For big result sets, summarize and show 1–2 small tables (e.g. top 10–15 rows); note "Full result has N rows" if needed.
- If there are 0 rows: say so simply and suggest widening filters or time range if relevant.
- If the user asked about campaign performance or budget (e.g. "should I scale", "which campaign to cut"), add a final line with only this JSON (no other text on the line): {"signal": "scale" or "hold" or "cut", "campaign": "campaign name or identifier", "reason": "one brief sentence"}. Otherwise omit the JSON line."""


def _is_simple_greeting(msg: str) -> bool:
    if not msg or len(msg) > 80:
        return False
    lower = msg.strip().lower()
    greetings = ("hi", "hello", "hey", "howdy", "hi there", "hello there", "yo", "sup", "good morning", "good afternoon", "good evening")
    return lower in greetings or lower.rstrip("!?.") in greetings


def _is_capability_question(msg: str) -> bool:
    """Fast path: "what can you do", "help", "capabilities" — avoid planner/LLM."""
    if not msg or len(msg) > 120:
        return False
    lower = msg.strip().lower().rstrip("?.!")
    if lower in ("help", "what can you do", "what can you do for me", "capabilities", "what do you do"):
        return True
    if any(x in lower for x in ("what can you do", "what do you do", "how can you help", "what are you", "your capabilities")):
        return True
    return False


def _generate_session_title(user_message: str, assistant_answer: str) -> str:
    """Generate a short 4–6 word descriptive session title via LLM from question + answer preview. Fallback: first 6 words of user message."""
    max_len = 50
    if not (user_message or "").strip():
        return "New chat"
    try:
        from ..llm_claude import is_claude_configured, chat_completion as claude_completion
        from ..llm_gemini import is_gemini_configured, chat_completion_with_tools as gemini_chat
    except Exception:
        pass
    else:
        system = (
            "You are a title generator. Given a user question and an analytics answer, output ONLY a 4–6 word descriptive title for the chat session. "
            "No punctuation, no quotes, no explanation. Examples: 'Meta ROAS last 30 days', 'Top products by revenue', 'Google Ads spend by campaign'."
        )
        user_content = f"Question: {(user_message or '')[:200]}\nAnswer preview: {(assistant_answer or '')[:300]}"
        msgs = [{"role": "user", "content": user_content}]
        raw = ""
        if is_claude_configured():
            try:
                raw = claude_completion(msgs, system=system)
            except Exception:
                pass
        if not raw and is_gemini_configured():
            try:
                out = gemini_chat(msgs, [], system=system)
                raw = (out.get("text") or "").strip()
            except Exception:
                pass
        if raw and isinstance(raw, str) and raw.strip():
            title = raw.strip()[:max_len]
            if len(raw.strip()) > max_len:
                title = title[: max_len - 3] + "..."
            return title or "New chat"
    # Fallback: first 6 words of user message
    text = (user_message or "").strip()
    words = text.split()
    title = " ".join(words[:6]) if words else "New chat"
    return title[:max_len] if len(title) <= max_len else title[: max_len - 3] + "..."


def _schedule_session_title_update(
    store: Any,
    organization_id: str,
    session_id: str,
    user_message: str,
    assistant_answer: str,
) -> None:
    """Run title generation in a background thread so it never adds latency to the response."""
    def _run() -> None:
        try:
            title = _generate_session_title(user_message, assistant_answer)
            if hasattr(store, "update_title"):
                store.update_title(organization_id, session_id, title)
        except Exception as e:
            logger.debug("Background session title update failed: %s", e)

    _title_executor.submit(_run)


def _allow_empty_for_question(message: str) -> bool:
    """Allow 0 rows as valid for analytical/segment questions where empty is a valid answer."""
    if not message:
        return False
    lower = (message or "").strip().lower()
    phrases = (
        "days from first", "time lag", "first visit to first purchase",
        "churn", "went quiet", "45", "90 days", "days since last",
        "90-day ltv", "ltv by channel", "repeat purchase", "first buy",
        "top 10%", "top 10 percent", "spenders", "profile of",
        "landing page", "entry page", "drop off", "drop-off", "abandon",
        "funnel", "checkout", "no conversions", "no data",
    )
    return any(p in lower for p in phrases)


def _datasets_used_in_sql(sql: str) -> Set[str]:
    """Extract dataset names from SQL (backtick-quoted or unquoted project.dataset.table). Returns set of dataset names."""
    if not sql or not isinstance(sql, str):
        return set()
    quoted = re.findall(r"`([^`]+)`", sql)
    used: Set[str] = set()
    for name in quoted:
        parts = name.split(".")
        if len(parts) >= 2:
            used.add(parts[1].strip().lower())
    unquoted = re.findall(r"\b(\w+)\.(\w+)\.(\w+)\b", sql)
    for _p, ds, _t in unquoted:
        used.add(ds.strip().lower())
    return used


def _tables_referenced_in_sql(sql: str) -> Set[tuple]:
    """Extract (project, dataset, table) triples from SQL. Backtick `p.d.t` and unquoted identifiers. Lowercase."""
    if not sql or not isinstance(sql, str):
        return set()
    out: Set[tuple] = set()
    # Backtick-quoted: `project.dataset.table` or `dataset.table`
    for name in re.findall(r"`([^`]+)`", sql):
        parts = [p.strip().lower() for p in name.split(".") if p.strip()]
        if len(parts) == 3:
            out.add((parts[0], parts[1], parts[2]))
        elif len(parts) == 2:
            out.add(("", parts[0], parts[1]))
    # Unquoted: project.dataset.table
    for m in re.finditer(r"\b(\w+)\.(\w+)\.(\w+)\b", sql, re.IGNORECASE):
        out.add((m.group(1).lower(), m.group(2).lower(), m.group(3).lower()))
    return out


def _sql_references_only_allowed_tables(sql: str, organization_id: str) -> bool:
    """True iff every project.dataset.table reference in sql is in the org's allowed set. Tenant isolation guard."""
    if not (organization_id or "").strip():
        return False
    try:
        from .schema_cache_firestore import get_allowed_tables_set
        allowed = get_allowed_tables_set(organization_id)
    except Exception:
        return False
    if not allowed:
        return False
    referenced = _tables_referenced_in_sql(sql)
    for triple in referenced:
        # (project, dataset, table) — allowed set uses (project, dataset, table) lowercase
        if triple in allowed:
            continue
        # Allow ( "", dataset, table ) to match any project in allowed for that dataset.table
        if triple[0] == "":
            if any((a[1], a[2]) == (triple[1], triple[2]) for a in allowed):
                continue
        logger.warning(
            "Copilot tenant isolation: SQL references table %s not in allowed set for org=%s",
            triple,
            organization_id,
        )
        return False
    return True


def _expand_candidates_with_other_datasets(
    candidates: List[dict],
    failed_sql: str,
    intent: str,
    organization_id: str,
) -> List[dict]:
    """On retry: add tables from datasets not used in the failed SQL. Merges without duplicating by full table name."""
    used_ds = _datasets_used_in_sql(failed_sql)
    if not used_ds:
        return candidates
    try:
        extra = tools_discover_tables(
            intent,
            limit=15,
            organization_id=organization_id or None,
            exclude_datasets=used_ds,
        )
    except Exception as e:
        logger.warning("Copilot expand_candidates (other datasets) failed: %s", e)
        return candidates
    if not extra:
        return candidates
    seen: Set[str] = set()
    out: List[dict] = []
    for c in candidates:
        full = (c.get("table") or "").strip()
        if full and full not in seen:
            seen.add(full)
            out.append(c)
    project = None
    try:
        from ..clients.bigquery import _get_bq_context
        ctx = _get_bq_context(organization_id) if organization_id else None
        if ctx and ctx.get("bq_project"):
            project = ctx["bq_project"]
    except Exception:
        pass
    for e in extra:
        proj = e.get("project") or project or ""
        ds = e.get("dataset") or ""
        tbl = e.get("table") or e.get("table_name") or ""
        if not tbl:
            continue
        full = f"{proj}.{ds}.{tbl}".strip(".")
        if full not in seen:
            seen.add(full)
            out.append({"table": full, "columns": e.get("columns") or []})
    if len(out) > len(candidates):
        logger.info("Copilot expanded candidates with other datasets | used=%s added=%d", used_ds, len(out) - len(candidates))
    return out


# Max candidate tables to include in schema block (multi-channel brands can have 30–50 tables)
MAX_SCHEMA_TABLES = 35


def _schema_block(candidates: List[dict]) -> str:
    """Build a single schema block for the prompt from candidate tables and columns."""
    lines = ["## Available schema (use only these tables and columns)\n"]
    for c in candidates[:MAX_SCHEMA_TABLES]:
        full = c.get("table") or ""
        cols = c.get("columns") or []
        if not full:
            continue
        lines.append(f"- Table: `{full}`")
        if cols:
            parts = []
            for x in cols:
                if isinstance(x, dict):
                    name = x.get("name") or ""
                    dtype = x.get("data_type")
                    parts.append(f"{name} ({dtype})" if dtype else name)
                else:
                    parts.append(str(x))
            lines.append(f"  Columns: {', '.join(parts)}")
        lines.append("")
    return "\n".join(lines)


# Max chart rows to store in session meta (Firestore doc size limit)
MAX_CHART_ROWS_STORED = 100


def _get_dataset_labels_for_org(organization_id: str) -> str:
    """Return a short line mapping dataset names to source labels (e.g. 146568 = Google Ads) from Firestore org config. Empty if not available."""
    if not (organization_id or "").strip():
        return ""
    try:
        from ..auth.firestore_user import get_organization, get_org_projects_flat
        org_doc = get_organization(organization_id)
        flat = get_org_projects_flat(org_doc) or []
        if not flat:
            return ""
        parts = []
        for item in flat:
            ds = (item.get("bq_dataset") or "").strip()
            t = item.get("type")
            if not ds:
                continue
            label = _DATASET_TYPE_LABELS.get(t, t) if t else ds
            parts.append(f"{ds} = {label}")
        return ", ".join(parts) if parts else ""
    except Exception:
        return ""


def _build_sql_prompt(
    question: str,
    candidates: List[dict],
    client_id: int,
    previous_sql: Optional[str] = None,
    previous_error: Optional[str] = None,
    conversation_context: Optional[str] = None,
    schema_summary: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> tuple[str, str]:
    """Return (system_prompt, user_message) for LLM SQL generation. schema_summary and dataset labels are optional context."""
    system = _SQL_GUIDE.format(client_id=client_id)
    schema = _schema_block(candidates)
    user_parts = []
    labels = _get_dataset_labels_for_org(organization_id or "")
    if labels:
        user_parts.append("## Dataset labels (use to match user question to the right source)\n")
        user_parts.append(labels)
        user_parts.append("")
    if schema_summary and schema_summary.strip():
        user_parts.append("## Your data (summary)\n")
        user_parts.append(schema_summary.strip()[:MAX_SUMMARY_CHARS])
        user_parts.append("")
    user_parts.append(schema)
    if conversation_context and conversation_context.strip():
        user_parts.append("## Conversation so far")
        user_parts.append(conversation_context.strip())
        user_parts.append("")
    user_parts.extend([
        "## User question",
        question.strip(),
        "",
    ])
    if previous_sql or previous_error:
        user_parts.append("## Previous attempt (do not repeat; try a different table or query)")
        if previous_sql:
            user_parts.append(f"SQL: {previous_sql[:500]}")
        if previous_error:
            user_parts.append(f"Result: {previous_error[:300]}")
        user_parts.append("")
    user_parts.append("Output only the single BigQuery SELECT query:")
    return system, "\n".join(user_parts)


def _extract_sql_from_response(text: str) -> Optional[str]:
    """Extract a single SQL query from LLM response (handles ```sql ... ``` or raw SQL)."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    # Code block
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Whole text if it starts with SELECT/WITH (multi-line allowed)
    if text.upper().startswith("SELECT") or text.upper().startswith("WITH"):
        return text
    # Find first line starting with SELECT/WITH and take from there to end
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("SELECT") or line.strip().upper().startswith("WITH"):
            return "\n".join(lines[i:]).strip()
    # Fallback: find SELECT or WITH anywhere (e.g. "The query is: SELECT ...")
    sel = re.search(r"(\bSELECT\b[\s\S]*?)(?=\s*$|\n\n|\n```|;\s*$)", text, re.IGNORECASE | re.DOTALL)
    if sel:
        return sel.group(1).strip().rstrip(";")
    with_match = re.search(r"(\bWITH\s+\w+\s+AS\s*\([\s\S]*)", text, re.IGNORECASE | re.DOTALL)
    if with_match:
        return with_match.group(1).strip().rstrip(";")
    return None


def _llm_generate_sql(
    system: str,
    user_content: str,
    organization_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[str]:
    """Call LLM (Claude or Gemini) to generate SQL; return extracted SQL or None."""
    try:
        from ..llm_claude import is_claude_configured, chat_completion as claude_completion
        from ..llm_gemini import is_gemini_configured, chat_completion_with_tools as gemini_chat
    except Exception:
        return None
    msgs = [{"role": "user", "content": user_content}]
    raw = ""
    if is_claude_configured():
        try:
            raw = claude_completion(msgs, system=system, organization_id=organization_id, session_id=session_id)
        except Exception as e:
            logger.warning("Claude SQL generation failed: %s", e)
            if is_gemini_configured():
                try:
                    out = gemini_chat(msgs, [], system=system, organization_id=organization_id, session_id=session_id)
                    raw = (out.get("text") or "").strip()
                except Exception:
                    pass
    if not raw and is_gemini_configured():
        try:
            out = gemini_chat(msgs, [], system=system, organization_id=organization_id, session_id=session_id)
            raw = (out.get("text") or "").strip()
        except Exception as e:
            logger.warning("Gemini SQL generation failed: %s", e)
    extracted = _extract_sql_from_response(raw) if raw else None
    if raw and not extracted:
        logger.warning(
            "Copilot LLM returned text but no SQL could be extracted (len=%s). Preview: %s",
            len(raw),
            (raw[:400] + "..." if len(raw) > 400 else raw),
        )
    return extracted


def _llm_generate_sql_and_format(
    system: str,
    user_content: str,
    organization_id: Optional[str] = None,
    session_id: Optional[str] = None,
    rows_hint: Optional[list] = None,
    message: Optional[str] = None,
    sql_used: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Single entry point: when rows_hint is None, generate SQL only (returns (sql, None)).
    When rows_hint is provided (after BQ execution), format the result only (returns (None, formatted_text)).
    Falls back to _llm_generate_sql and _format_answer.
    """
    if rows_hint is None:
        sql = _llm_generate_sql(system, user_content, organization_id=organization_id, session_id=session_id)
        return (sql, None)
    if message is None or sql_used is None:
        return (None, None)
    formatted = _format_answer(
        message, sql_used, rows_hint,
        organization_id or "", session_id or "",
        from_raw=False,
    )
    return (None, formatted)


def _llm_interpret_question(message: str) -> Optional[str]:
    """Ask the LLM to describe what it is thinking. Used when streaming is not available."""
    if not (message or "").strip():
        return None
    try:
        from ..llm_claude import is_claude_configured, chat_completion as claude_completion
        from ..llm_gemini import is_gemini_configured, chat_completion_with_tools as gemini_chat
    except Exception:
        return None
    system = (
        "You are an analytics assistant. The user asked a question about their data. "
        "Reply with your thinking: what they want, what data to use, and how you'd approach it. Use markdown if helpful. No preamble—only your reasoning."
    )
    user_content = f'User asked: "{message.strip()}"'
    msgs = [{"role": "user", "content": user_content}]
    raw = ""
    if is_claude_configured():
        try:
            raw = claude_completion(msgs, system=system)
        except Exception:
            pass
    if not raw and is_gemini_configured():
        try:
            out = gemini_chat(msgs, [], system=system)
            raw = (out.get("text") or "").strip()
        except Exception:
            pass
    if not raw:
        return None
    return (raw or "").strip() or None


def _stream_llm_thinking(
    message: str,
    candidates: List[dict],
    organization_id: str,
    schema_summary: Optional[str] = None,
) -> Generator[str, None, None]:
    """Stream the model's live reasoning about the question and which data to use. Yields text chunks. No fixed format."""
    if not (message or "").strip():
        return
    labels = _get_dataset_labels_for_org(organization_id or "")
    table_list = []
    for c in (candidates or [])[:MAX_SCHEMA_TABLES]:
        full = c.get("table") or ""
        if full:
            table_list.append(full)
    context_parts = []
    if labels:
        context_parts.append(f"Dataset labels: {labels}.")
    if table_list:
        context_parts.append(f"Available tables ({len(table_list)}): " + ", ".join(table_list[:15]) + ("..." if len(table_list) > 15 else ""))
    if schema_summary and schema_summary.strip():
        context_parts.append("Summary: " + schema_summary.strip()[:1500])
    context_str = " ".join(context_parts) if context_parts else "Schema and tables will be used for the query."
    system = (
        "You are an analytics assistant. Think step by step out loud: what the user is asking for, which data sources or tables are relevant, and how you would answer. "
        "Be concise. Output one short thought per line; use - or • for bullets. No SQL, no code blocks. This is for the user to see your thought process."
    )
    user_content = f"User question: {message.strip()}\n\nContext: {context_str}\n\nThink out loud (one thought per line):"
    combined = f"{system}\n\n---\n\n{user_content}"
    try:
        from ..llm_claude import is_claude_configured, stream_claude
        from ..llm_gemini import is_gemini_configured, stream_gemini
    except Exception:
        return
    if is_claude_configured():
        try:
            for chunk in stream_claude(combined):
                if chunk and isinstance(chunk, str):
                    yield chunk
            return
        except Exception:
            pass
    if is_gemini_configured():
        try:
            for chunk in stream_gemini(combined):
                if chunk and isinstance(chunk, str):
                    yield chunk
        except Exception:
            pass


def _format_answer(message: str, sql_used: str, rows: list, organization_id: str, session_id: str, from_raw: bool = False) -> str:
    """One LLM call to format the result. Prefer Claude, fallback Gemini."""
    try:
        from ..llm_claude import is_claude_configured, chat_completion_with_tools as claude_chat
        from ..llm_gemini import is_gemini_configured, chat_completion_with_tools as gemini_chat
    except Exception:
        return _fallback_answer(rows, sql_used)
    # For large result sets, pass more rows for context but instruct the LLM to summarize
    preview_rows = rows[:50] if len(rows) > 30 else rows[:20]
    data_preview = json.dumps(preview_rows, default=str)[:6000]
    extra = " (Data from raw fallback.)" if from_raw else ""
    zero_row_note = ""
    if len(rows) == 0:
        zero_row_note = " The query returned 0 rows. State that no data matches; suggest widening the time window or relaxing filters if relevant."
    large_set_note = ""
    if len(rows) > 30:
        large_set_note = f" The result has {len(rows)} rows. Output a concise summary with clear sections (##) and at most 1–2 small markdown tables (max 10–15 rows each). Do not list every row."
    prompt = (
        f"User question: {message}\n\n"
        f"SQL used: {sql_used}\n\n"
        f"Result ({len(rows)} rows): {data_preview}\n\n"
        f"Format the above into a clear, well-formatted answer. Use markdown tables with proper newlines between header, separator, and rows. Use ## for sections. Do not invent data.{large_set_note}{zero_row_note}{extra}"
    )
    msgs = [{"role": "user", "content": prompt}]
    if is_claude_configured():
        try:
            res = claude_chat(msgs, [], system=_FORMAT_SYSTEM, organization_id=organization_id, session_id=session_id)
            return (res.get("text") or "").strip() or _fallback_answer(rows, sql_used)
        except Exception:
            if is_gemini_configured():
                res = gemini_chat(msgs, [], system=_FORMAT_SYSTEM, organization_id=organization_id, session_id=session_id)
                return (res.get("text") or "").strip() or _fallback_answer(rows, sql_used)
    if is_gemini_configured():
        try:
            res = gemini_chat(msgs, [], system=_FORMAT_SYSTEM, organization_id=organization_id, session_id=session_id)
            return (res.get("text") or "").strip() or _fallback_answer(rows, sql_used)
        except Exception:
            pass
    return _fallback_answer(rows, sql_used)


def _extract_signal_from_answer(text: str) -> tuple[str, Optional[dict]]:
    """If the formatted answer ends with a JSON line containing signal (scale|hold|cut), extract it and return (text without that line, signal dict)."""
    if not text or not isinstance(text, str):
        return (text or "", None)
    lines = text.strip().split("\n")
    for i in range(len(lines) - 1, -1, -1):
        line = (lines[i] or "").strip()
        if not line or not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict) and data.get("signal") in ("scale", "hold", "cut"):
                clean_lines = lines[:i] + lines[i + 1:]
                clean_text = "\n".join(clean_lines).strip()
                return (clean_text, {"signal": data["signal"], "campaign": data.get("campaign") or "", "reason": data.get("reason") or ""})
        except (json.JSONDecodeError, TypeError):
            continue
    return (text, None)


def _fallback_answer(rows: list, sql_used: str) -> str:
    if not rows:
        return f"No rows returned. SQL: {sql_used[:200]}..."
    lines = [f"**Result ({len(rows)} rows)**", ""]
    if rows and isinstance(rows[0], dict):
        headers = list(rows[0].keys())
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        for r in rows[:20]:
            lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
    else:
        for r in rows[:20]:
            lines.append(f"- {r}")
    return "\n".join(lines)


def _format_answer_stream(
    message: str, sql_used: str, rows: list, from_raw: bool = False
) -> Generator[str, None, None]:
    """Yield formatted answer chunks from LLM stream. Uses same prompt as _format_answer. Falls back to full text if streaming unavailable."""
    try:
        from ..llm_claude import is_claude_configured, stream_claude
        from ..llm_gemini import is_gemini_configured, stream_gemini
    except Exception:
        yield _fallback_answer(rows, sql_used)
        return
    preview_rows = rows[:50] if len(rows) > 30 else rows[:20]
    data_preview = json.dumps(preview_rows, default=str)[:6000]
    extra = " (Data from raw fallback.)" if from_raw else ""
    zero_row_note = ""
    if len(rows) == 0:
        zero_row_note = " The query returned 0 rows. State that no data matches; suggest widening the time window or relaxing filters if relevant."
    large_set_note = ""
    if len(rows) > 30:
        large_set_note = f" The result has {len(rows)} rows. Output a concise summary with clear sections (##) and at most 1–2 small markdown tables (max 10–15 rows each). Do not list every row."
    user_content = (
        f"User question: {message}\n\n"
        f"SQL used: {sql_used}\n\n"
        f"Result ({len(rows)} rows): {data_preview}\n\n"
        f"Format the above into a clear, well-formatted answer. Use markdown tables with proper newlines between header, separator, and rows. Use ## for sections. Do not invent data.{large_set_note}{zero_row_note}{extra}"
    )
    combined_prompt = f"{_FORMAT_SYSTEM}\n\n---\n\n{user_content}"
    if is_claude_configured():
        try:
            for chunk in stream_claude(combined_prompt):
                if chunk:
                    yield chunk
            return
        except Exception:
            if is_gemini_configured():
                for chunk in stream_gemini(combined_prompt):
                    if chunk:
                        yield chunk
                return
    if is_gemini_configured():
        try:
            for chunk in stream_gemini(combined_prompt):
                if chunk:
                    yield chunk
            return
        except Exception:
            pass
    yield _fallback_answer(rows, sql_used)


def chat(
    organization_id: str,
    message: str,
    *,
    session_id: Optional[str] = None,
    client_id: Optional[int] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    One turn: discover tables → LLM generates SQL from schema + guide → run → validate → format. Retry on empty/error.
    Returns { answer, data, text, session_id }. user_id scopes session to the logged-in user for history.
    """
    try:
        from .session_memory import get_session_store
        from .planner import analyze as planner_analyze, replan as planner_replan
    except Exception as e:
        logger.exception("Copilot imports failed")
        sid = session_id or str(uuid.uuid4())
        return {"answer": f"Configuration error: {str(e)[:200]}", "data": [], "text": str(e)[:200], "session_id": str(sid)}

    store = get_session_store()
    sid = str(session_id or uuid.uuid4())
    try:
        cid = int(client_id) if client_id is not None else 1
    except (TypeError, ValueError):
        cid = 1

    msg_clean = (message or "").strip()
    if not msg_clean:
        out = {"answer": "Please type a message to get a response.", "data": [], "text": "Please type a message to get a response.", "session_id": sid}
        return out
    if len(msg_clean) > 32000:
        msg_clean = msg_clean[:32000] + "... [truncated]"
    message = msg_clean

    if _is_simple_greeting(message):
        reply = "Hi! I can help with marketing analytics. Ask about revenue, top products, channels, ROAS, sessions, conversions, or any metric we have in the warehouse."
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", reply, meta=None, user_id=user_id)
        return {"answer": reply, "data": [], "text": reply, "session_id": sid}

    if _is_capability_question(message):
        reply = (
            "I'm your analytics copilot. I can:\n\n"
            "- **Answer questions** about your data in plain language (e.g. “What was revenue last month?”, “Top 10 products by sales”).\n"
            "- **Run safe read-only queries** on your BigQuery warehouse (Google Ads, GA4, Meta Ads, Pinterest, etc.) and return tables or charts.\n"
            "- **Compare periods**, break down by channel, campaign, or product, and summarize trends.\n\n"
            "Describe what you want to analyze and I'll suggest the right tables and run the query. Ask anything about your connected datasets."
        )
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", reply, meta=None, user_id=user_id)
        return {"answer": reply, "data": [], "text": reply, "session_id": sid}

    # When org is set, require Firestore BQ config; no env fallback.
    o = (organization_id or "").strip()
    if o:
        try:
            from ..auth.firestore_user import get_org_bq_context
            if get_org_bq_context(organization_id) is None:
                from ..clients.bigquery import MSG_ORG_DATASETS_NOT_CONFIGURED
                store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
                store.append(organization_id, sid, "assistant", MSG_ORG_DATASETS_NOT_CONFIGURED, meta=None, user_id=user_id)
                return {"answer": MSG_ORG_DATASETS_NOT_CONFIGURED, "data": [], "text": MSG_ORG_DATASETS_NOT_CONFIGURED, "session_id": sid}
        except Exception:
            pass

    try:
        from ..auth.firestore_user import get_org_bq_context
        bq_ctx = get_org_bq_context(organization_id) if o else None
        datasets_info = []
        if bq_ctx:
            try:
                from ..auth.firestore_user import get_org_all_dataset_configs
                for cfg in get_org_all_dataset_configs(organization_id) or []:
                    ds = (cfg.get("bq_dataset") or "").strip()
                    if ds and ds not in datasets_info:
                        datasets_info.append(ds)
            except Exception:
                pass
        logger.info(
            "Copilot chat | org_id=%s user_id=%s session_id=%s datasets=%s",
            organization_id, user_id or "(none)", sid[:16] if sid else "", datasets_info or "(env)",
        )
    except Exception:
        pass

    # Load session context for follow-up questions (when continuing an existing session)
    session_context_messages: List[dict] = []
    if session_id:
        try:
            session_context_messages = store.get_messages(organization_id, sid, user_id=user_id)[-12:]
        except Exception:
            pass
    conversation_context_str: Optional[str] = None
    if session_context_messages:
        parts = []
        for m in session_context_messages:
            role = (m.get("role") or "").strip().lower()
            content = (m.get("content") or "").strip()
            if content:
                parts.append(f"{role.capitalize()}: {content[:500]}" + ("..." if len(content) > 500 else ""))
        if parts:
            conversation_context_str = "\n".join(parts)

    start_ms = time.perf_counter() * 1000
    max_retries = get_max_retries()
    copilot_metrics.increment("copilot.planner_attempts_total")
    plan = planner_analyze(message, context=session_context_messages or None, client_id=cid, organization_id=organization_id)
    copilot_metrics.timing("copilot.planner_ms", (time.perf_counter() * 1000) - start_ms)
    candidates = list(plan.get("candidates") or [])
    schema_summary: Optional[str] = None
    try:
        from .schema_cache_firestore import get_schema_summary
        schema_summary = get_schema_summary(organization_id)
    except Exception:
        pass

    if not candidates:
        logger.info("Copilot no candidates | intent=%s", plan.get("intent", ""))
        copilot_metrics.increment("copilot.query_empty_results_total")
        final_text = (
            "I couldn't find any tables in the warehouse for that question. "
            "Check that BigQuery discovery is configured (project and datasets) and try again."
        )
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", final_text, meta=None, user_id=user_id)
        return {"answer": final_text, "data": [], "text": final_text, "session_id": sid}

    valid_result = None
    sql_used = None
    tables_tried: list[str] = []
    attempt = 0
    previous_sql: Optional[str] = None
    previous_error: Optional[str] = None

    while attempt < max_retries:
        attempt += 1
        if attempt > 1 and previous_sql:
            candidates = _expand_candidates_with_other_datasets(
                candidates, previous_sql, plan.get("intent", ""), organization_id
            )
        system, user_content = _build_sql_prompt(
            message, candidates, cid,
            previous_sql=previous_sql, previous_error=previous_error,
            conversation_context=conversation_context_str,
            schema_summary=schema_summary,
            organization_id=organization_id,
        )
        t_sql_start = time.perf_counter() * 1000
        sql_used = _llm_generate_sql(system, user_content, organization_id=organization_id, session_id=sid)
        copilot_metrics.timing("copilot.sql_gen_ms", (time.perf_counter() * 1000) - t_sql_start)
        if not sql_used:
            previous_error = "LLM did not return a valid SQL query."
            logger.warning("Copilot LLM returned no SQL on attempt %s (check for 'no SQL could be extracted' above)", attempt)
            continue
        if not _sql_references_only_allowed_tables(sql_used, organization_id or ""):
            previous_error = "Generated SQL references tables outside this organization; rejected for tenant isolation."
            logger.warning("Copilot tenant isolation rejected SQL on attempt %s for org=%s", attempt, organization_id)
            continue
        tables_tried.append(sql_used[:500])
        t_bq_start = time.perf_counter() * 1000
        try:
            out = run_bigquery_sql(sql_used, organization_id=organization_id, client_id=cid)
            copilot_metrics.timing("copilot.bq_execution_ms", (time.perf_counter() * 1000) - t_bq_start)
        except Exception as e:
            copilot_metrics.timing("copilot.bq_execution_ms", (time.perf_counter() * 1000) - t_bq_start)
            previous_sql = sql_used
            previous_error = str(e)[:300]
            logger.warning("Copilot run_bigquery_sql failed: %s", e)
            continue
        if out.get("error"):
            previous_sql = sql_used
            previous_error = (out.get("error") or "Unknown error")[:300]
            continue
        # Allow 0 rows for analytical/segment questions (churn, LTV, repeat purchase, funnel, etc.)
        allow_empty = _allow_empty_for_question(message)
        is_valid, _reason = validate_result(out, message, allow_empty=allow_empty)
        if is_valid:
            valid_result = out
            if attempt > 1:
                copilot_metrics.increment("copilot.fallback_success_total")
            break
        previous_sql = sql_used
        previous_error = (
            "Query returned no rows or invalid result. "
            "Try a different table from the schema, a wider time window, or fewer WHERE filters."
        )

    if valid_result is not None and sql_used:
        rows = valid_result.get("rows") or []
        execution_time_ms = int((time.perf_counter() * 1000) - start_ms)
        logger.info(
            "Copilot success | intent=%s sql_tried=%s row_count=%d execution_time_ms=%d",
            plan.get("intent", ""),
            len(tables_tried),
            len(rows),
            execution_time_ms,
        )
        t_fmt_start = time.perf_counter() * 1000
        _, raw_final = _llm_generate_sql_and_format(
            "", "", organization_id=organization_id, session_id=sid,
            rows_hint=rows, message=message, sql_used=sql_used,
        )
        if raw_final is None:
            raw_final = _format_answer(message, sql_used, rows, organization_id, sid)
        copilot_metrics.timing("copilot.format_ms", (time.perf_counter() * 1000) - t_fmt_start)
        final_text, signal = _extract_signal_from_answer(raw_final)
        serialized_data = _serialize_data_for_sse(rows)
        chart_meta = {"data": serialized_data[:MAX_CHART_ROWS_STORED]} if serialized_data else None
        msgs_before = store.get_messages(organization_id, sid, user_id=user_id)
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", final_text, meta=chart_meta, user_id=user_id)
        if len(msgs_before) == 0:
            _schedule_session_title_update(store, organization_id, sid, message, final_text)
        out = {"answer": final_text, "data": rows, "text": final_text, "session_id": sid}
        if signal:
            out["signal"] = signal
        return out

    copilot_metrics.increment("copilot.query_empty_results_total")
    if tables_tried:
        logger.info(
            "Copilot no valid result | intent=%s sql_tried_count=%d sql_preview=%s",
            plan.get("intent", ""),
            len(tables_tried),
            (tables_tried[0][:500] + "..." if len(tables_tried[0]) >= 500 else tables_tried[0]),
        )
    final_text = (
        "I couldn't find data matching that question. Try rephrasing or ask about a specific metric (e.g. revenue by product, top channels, ROAS)."
    )
    msgs_before_fail = store.get_messages(organization_id, sid, user_id=user_id)
    store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
    store.append(organization_id, sid, "assistant", final_text, meta=None, user_id=user_id)
    if len(msgs_before_fail) == 0:
        _schedule_session_title_update(store, organization_id, sid, message, final_text)
    return {"answer": final_text, "data": [], "text": final_text, "session_id": sid}


def _serialize_data_for_sse(raw_data: list) -> list:
    """Ensure data is JSON-serializable for SSE (e.g. date/datetime to string)."""
    out = []
    for r in raw_data or []:
        if not isinstance(r, dict):
            continue
        row = {}
        for k, v in r.items():
            row[k] = v.isoformat() if hasattr(v, "isoformat") else v
        out.append(row)
    return out


def chat_stream(
    organization_id: str,
    message: str,
    *,
    session_id: Optional[str] = None,
    client_id: Optional[int] = None,
    user_id: Optional[str] = None,
) -> Generator[dict[str, Any], None, None]:
    """
    Same flow as chat() but yields SSE-style events: phase (status) then done or error.
    Events: {"phase": "analyzing", "message": "..."}, {"phase": "discovering", "message": "..."},
    {"phase": "generating_sql", "message": "..."}, {"phase": "running_query", "message": "..."},
    {"phase": "formatting", "message": "..."}, {"phase": "done", "answer", "data", "session_id"},
    or {"phase": "error", "error": "..."}.
    """
    try:
        from .session_memory import get_session_store
        from .planner import analyze as planner_analyze
    except Exception as e:
        logger.exception("Copilot imports failed")
        sid = session_id or str(uuid.uuid4())
        yield {"phase": "error", "error": str(e)[:200], "session_id": str(sid)}
        return

    store = get_session_store()
    sid = str(session_id or uuid.uuid4())
    try:
        cid = int(client_id) if client_id is not None else 1
    except (TypeError, ValueError):
        cid = 1

    msg_clean = (message or "").strip()
    if not msg_clean:
        yield {"phase": "done", "answer": "Please type a message to get a response.", "data": [], "session_id": sid}
        return
    if len(msg_clean) > 32000:
        msg_clean = msg_clean[:32000] + "... [truncated]"
    message = msg_clean

    if _is_simple_greeting(message):
        reply = "Hi! I can help with marketing analytics. Ask about revenue, top products, channels, ROAS, sessions, conversions, or any metric we have in the warehouse."
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", reply, meta=None, user_id=user_id)
        yield {"phase": "done", "answer": reply, "data": [], "session_id": sid}
        return

    if _is_capability_question(message):
        reply = (
            "I'm your analytics copilot. I can:\n\n"
            "- **Answer questions** about your data in plain language (e.g. “What was revenue last month?”, “Top 10 products by sales”).\n"
            "- **Run safe read-only queries** on your BigQuery warehouse (Google Ads, GA4, Meta Ads, Pinterest, etc.) and return tables or charts.\n"
            "- **Compare periods**, break down by channel, campaign, or product, and summarize trends.\n\n"
            "Describe what you want to analyze and I’ll suggest the right tables and run the query. Ask anything about your connected datasets."
        )
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", reply, meta=None, user_id=user_id)
        yield {"phase": "done", "answer": reply, "data": [], "session_id": sid}
        return

    # When org is set, require Firestore BQ config; no env fallback.
    o = (organization_id or "").strip()
    if o:
        try:
            from ..auth.firestore_user import get_org_bq_context
            if get_org_bq_context(organization_id) is None:
                from ..clients.bigquery import MSG_ORG_DATASETS_NOT_CONFIGURED
                store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
                store.append(organization_id, sid, "assistant", MSG_ORG_DATASETS_NOT_CONFIGURED, meta=None, user_id=user_id)
                yield {"phase": "done", "answer": MSG_ORG_DATASETS_NOT_CONFIGURED, "data": [], "session_id": sid}
                return
        except Exception:
            pass

    # Early exit when org has no tables. Avoids 100s+ LLM/planner delay.
    try:
        from .schema_cache_firestore import get_allowed_tables_set
        allowed = get_allowed_tables_set(organization_id or "")
        if not allowed:
            logger.info("Copilot early exit: get_allowed_tables_set returned 0 tables for org=%s", organization_id or "(empty)")
            yield {"phase": "discovering", "message": "Checking schema…", "tables_count": 0, "detail": "Found 0 tables.", "detail_kind": "text"}
            final_text = (
                "I couldn't find any tables in the warehouse for that question. "
                "Check that BigQuery discovery is configured (project and datasets) and try again."
            )
            store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
            store.append(organization_id, sid, "assistant", final_text, meta=None, user_id=user_id)
            yield {"phase": "done", "answer": final_text, "data": [], "session_id": sid}
            return
    except Exception:
        pass

    # Load session context for follow-up questions (when continuing an existing session)
    session_context_messages: List[dict] = []
    if session_id:
        try:
            session_context_messages = store.get_messages(organization_id, sid, user_id=user_id)[-12:]
        except Exception:
            pass
    conversation_context_str: Optional[str] = None
    if session_context_messages:
        parts = []
        for m in session_context_messages:
            role = (m.get("role") or "").strip().lower()
            content = (m.get("content") or "").strip()
            if content:
                parts.append(f"{role.capitalize()}: {content[:500]}" + ("..." if len(content) > 500 else ""))
        if parts:
            conversation_context_str = "\n".join(parts)

    try:
        max_retries = get_max_retries()
        copilot_metrics.increment("copilot.planner_attempts_total")
        plan = planner_analyze(message, context=session_context_messages or None, client_id=cid, organization_id=organization_id)
        candidates = list(plan.get("candidates") or [])
        schema_summary_stream: Optional[str] = None
        try:
            from .schema_cache_firestore import get_schema_summary
            schema_summary_stream = get_schema_summary(organization_id)
        except Exception:
            pass

        def _table_name(c: dict) -> str:
            full = c.get("table") or c.get("table_name") or ""
            return full.split(".")[-1] if full and "." in full else full
        tables_list = [_table_name(c) for c in candidates if _table_name(c)]
        labels_str = _get_dataset_labels_for_org(organization_id or "")
        discovering_message = f"Using {len(candidates)} tables from your data sources"
        discovering_detail = ", ".join(tables_list[:12]) + ("..." if len(tables_list) > 12 else "") if tables_list else "No tables"
        if labels_str:
            discovering_detail = f"Sources: {labels_str}. Tables: " + discovering_detail
        logger.info("Copilot discovered %s candidate tables for org=%s | intent=%s", len(candidates), organization_id or "", plan.get("intent", ""))
        yield {"phase": "discovering", "message": discovering_message, "tables_count": len(candidates), "detail": discovering_detail, "detail_kind": "text"}
        if not candidates:
            logger.info("Copilot no candidates | intent=%s", plan.get("intent", ""))
            copilot_metrics.increment("copilot.query_empty_results_total")
            final_text = (
                "I couldn't find any tables in the warehouse for that question. "
                "Check that BigQuery discovery is configured (project and datasets) and try again."
            )
            store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
            store.append(organization_id, sid, "assistant", final_text, meta=None, user_id=user_id)
            yield {"phase": "done", "answer": final_text, "data": [], "session_id": sid}
            return

        # Build prompt for first attempt so we can run SQL gen in parallel with thinking
        system_first, user_content_first = _build_sql_prompt(
            message, candidates, cid,
            previous_sql=None, previous_error=None,
            conversation_context=conversation_context_str,
            schema_summary=schema_summary_stream,
            organization_id=organization_id,
        )
        sql_future = _sql_executor.submit(
            _llm_generate_sql,
            system_first, user_content_first,
            organization_id=organization_id, session_id=sid,
        )
        # Live thinking: stream the model's reasoning; SQL gen runs concurrently in background
        yield {"phase": "thinking", "message": "Thinking…", "detail": "", "detail_kind": "text", "step_kind": "reasoning"}
        for thinking_chunk in _stream_llm_thinking(message, candidates, organization_id, schema_summary_stream):
            if thinking_chunk:
                yield {"phase": "thinking_chunk", "chunk": thinking_chunk}

        valid_result = None
        sql_used = None
        tables_tried: list[str] = []
        attempt = 0
        previous_sql: Optional[str] = None
        previous_error: Optional[str] = None
        sql_from_background: Optional[str] = None
        try:
            sql_from_background = sql_future.result(timeout=_SQL_BACKGROUND_TIMEOUT_SEC)
        except (FuturesTimeoutError, Exception) as e:
            logger.debug("Background SQL gen timeout or failed, falling back to sequential: %s", e)
            sql_from_background = None

        while attempt < max_retries:
            attempt += 1
            if attempt > 1 and previous_sql:
                candidates = _expand_candidates_with_other_datasets(
                    candidates, previous_sql, plan.get("intent", ""), organization_id
                )
                yield {"phase": "discovering", "message": "Trying other datasets…", "tables_count": len(candidates), "detail": f"Expanded to {len(candidates)} tables.", "detail_kind": "text"}
            tables_preview = ", ".join((c.get("table") or "").split(".")[-1] for c in candidates[:5] if c.get("table")) + ("..." if len(candidates) > 5 else "")
            generating_detail = f"Building a query from the schema to answer your question." + (f" Considering tables: {tables_preview}" if tables_preview else "")
            yield {"phase": "generating_sql", "message": "Writing SQL…", "detail": generating_detail, "detail_kind": "text"}
            if attempt == 1 and sql_from_background is not None:
                sql_used = sql_from_background
                sql_from_background = None  # use only once
            else:
                system, user_content = _build_sql_prompt(
                    message, candidates, cid,
                    previous_sql=previous_sql, previous_error=previous_error,
                    conversation_context=conversation_context_str,
                    schema_summary=schema_summary_stream,
                    organization_id=organization_id,
                )
                sql_used = _llm_generate_sql(system, user_content, organization_id=organization_id, session_id=sid)
            if not sql_used:
                previous_error = "LLM did not return a valid SQL query."
                logger.warning("Copilot LLM returned no SQL on attempt %s (check above for 'no SQL could be extracted' if LLM returned text)", attempt)
                continue
            if not _sql_references_only_allowed_tables(sql_used, organization_id or ""):
                previous_error = "Generated SQL references tables outside this organization; rejected for tenant isolation."
                logger.warning("Copilot tenant isolation rejected SQL on attempt %s for org=%s", attempt, organization_id)
                continue
            tables_tried.append(sql_used[:500])
            yield {"phase": "running_query", "message": "Running query in BigQuery…", "sql_preview": (sql_used if sql_used else None), "detail_kind": "sql"}
            try:
                out = run_bigquery_sql(sql_used, organization_id=organization_id, client_id=cid)
            except Exception as e:
                previous_sql = sql_used
                previous_error = str(e)[:300]
                logger.warning("Copilot run_bigquery_sql failed: %s", e)
                continue
            if out.get("error"):
                previous_sql = sql_used
                previous_error = (out.get("error") or "Unknown error")[:300]
                continue
            allow_empty = _allow_empty_for_question(message)
            is_valid, _reason = validate_result(out, message, allow_empty=allow_empty)
            if is_valid:
                valid_result = out
                if attempt > 1:
                    copilot_metrics.increment("copilot.fallback_success_total")
                break
            previous_sql = sql_used
            previous_error = (
                "Query returned no rows or invalid result. "
                "Try a different table from the schema, a wider time window, or fewer WHERE filters."
            )

        if valid_result is not None and sql_used:
            rows = valid_result.get("rows") or []
            yield {"phase": "formatting", "message": "Formatting answer…", "detail": "Turning the result into a clear answer.", "detail_kind": "text"}
            accumulated: List[str] = []
            for chunk in _format_answer_stream(message, sql_used, rows, from_raw=False):
                accumulated.append(chunk)
                yield {"phase": "answer_chunk", "chunk": chunk}
            raw_final = "".join(accumulated)
            final_text, signal = _extract_signal_from_answer(raw_final)
            serialized_data = _serialize_data_for_sse(rows)
            chart_meta = {"data": serialized_data[:MAX_CHART_ROWS_STORED]} if serialized_data else None
            msgs_before = store.get_messages(organization_id, sid, user_id=user_id)
            store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
            store.append(organization_id, sid, "assistant", final_text, meta=chart_meta, user_id=user_id)
            if len(msgs_before) == 0:
                _schedule_session_title_update(store, organization_id, sid, message, final_text)
            done_payload = {"phase": "done", "answer": final_text, "data": serialized_data, "session_id": sid}
            if signal:
                done_payload["signal"] = signal
            yield done_payload
            return

        copilot_metrics.increment("copilot.query_empty_results_total")
        if tables_tried:
            logger.info(
                "Copilot no valid result | intent=%s sql_tried_count=%d sql_preview=%s",
                plan.get("intent", ""),
                len(tables_tried),
                (tables_tried[0][:500] + "..." if len(tables_tried[0]) >= 500 else tables_tried[0]),
            )
        final_text = (
            "I couldn't find data matching that question. Try rephrasing or ask about a specific metric (e.g. revenue by product, top channels, ROAS)."
        )
        msgs_before_fail = store.get_messages(organization_id, sid, user_id=user_id)
        store.append(organization_id, sid, "user", message, meta=None, user_id=user_id)
        store.append(organization_id, sid, "assistant", final_text, meta=None, user_id=user_id)
        if len(msgs_before_fail) == 0:
            _schedule_session_title_update(store, organization_id, sid, message, final_text)
        yield {"phase": "done", "answer": final_text, "data": [], "session_id": sid}
    except Exception as e:
        logger.exception("Copilot stream failed")
        yield {"phase": "error", "error": str(e)[:300], "session_id": sid}
        return
