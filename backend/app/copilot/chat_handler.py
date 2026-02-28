"""
Copilot chat handler: User question -> Marts schema + raw fallback schema -> LLM -> run_sql (marts) or run_sql_raw (raw) -> Answer + data.
Tools: run_sql (primary, marts only), run_sql_raw (fallback, GA4/Ads raw). Response: { answer, data }.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from .tools import COPILOT_TOOLS, execute_tool
from .knowledge_base import get_schema_for_copilot, get_raw_schema_for_copilot

logger = logging.getLogger(__name__)


def _build_system_template(client_id: int) -> str:
    """Build system prompt with marts schema and optional raw fallback schema."""
    schema = get_schema_for_copilot()
    raw_schema = get_raw_schema_for_copilot()
    return f"""You are an expert marketing analytics assistant. Prefer **run_sql** (marts: hypeon_marts, hypeon_marts_ads). Use **run_sql_raw** only when the question clearly needs raw data or run_sql returned no rows and the user needs data.

## Knowledge base (live schema from hypeon_marts and hypeon_marts_ads)
{schema}

## Fallback: raw data (run_sql_raw)
{raw_schema}
When using run_sql_raw, follow the schema and hints above. Always include LIMIT and, for GA4 events_*, filter by event_date.

## Tools
- **run_sql**: Primary. Marts only (fct_sessions, fct_ad_spend). Use for sessions, item views, traffic, ad spend. For item views use fct_sessions with event_name IN ('view_item','view_item_list') and item_id; for "from Google" add utm_source LIKE '%google%'. Always add a date filter for fct_sessions (e.g. WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)) to avoid bytes limit errors. For fct_ad_spend filter by client_id = {client_id} when the column exists.
- **run_sql_raw**: Fallback when marts don't have the data. Allowed: GA4 events_*, Ads ads_AccountBasicStats_*. Use backtick-quoted names. Include LIMIT and date filter for GA4.

Call run_sql when the user needs data from marts. Call run_sql_raw only when marts are insufficient. Do not call tools for greetings or thanks.

## Unavailable channel (e.g. Facebook)
If the user asks for a channel (e.g. Facebook) that is not in the data, respond with: "[Channel] channel data is not currently present in the dataset. Available channels: google_ads. Once [Channel] data is integrated, this query will be supported." Do NOT mention staging, raw tables, or analytics_cache.

## Answering
- Base answers only on tool results. Never invent metrics.
- If tool returns no data or error, say so. Do not make up numbers.
- Response: answer text + optional data. No charts, funnels, or KPI cards."""


def chat(
    organization_id: str,
    message: str,
    *,
    session_id: Optional[str] = None,
    client_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    One turn of chat: get history, build messages, call LLM with run_sql (loop until final reply), persist to session.
    Returns { "text", "session_id" } only. No layout. Never raises; returns error message in text on failure.
    """
    try:
        from .session_memory import get_session_store
        from ..llm_claude import is_claude_configured, chat_completion_with_tools as claude_tools_chat
        from ..llm_gemini import is_gemini_configured, chat_completion_with_tools as gemini_tools_chat
    except Exception as e:
        logger.exception("Copilot chat imports failed")
        sid = session_id or str(uuid.uuid4())
        return {"answer": f"Configuration error: {str(e)[:200]}", "data": [], "text": f"Configuration error: {str(e)[:200]}", "session_id": str(sid)}

    store = get_session_store()
    sid = session_id or str(uuid.uuid4())
    sid = str(sid)
    try:
        cid = int(client_id) if client_id is not None else 1
    except (TypeError, ValueError):
        cid = 1
    max_rounds = 5

    def _normalize_for_compare(s: str) -> str:
        if not s:
            return ""
        s = (s or "").strip()
        for old, new in [("\u2019", "'"), ("\u2018", "'"), ("\u0027", "'")]:
            s = s.replace(old, new)
        return s.lower()

    def _is_error_response(result: dict) -> bool:
        if result.get("tool_calls"):
            return False
        text = (result.get("text") or "").strip()
        if not text:
            return False
        normalized = _normalize_for_compare(text)
        if "please try again" in normalized and "complete" in normalized and len(normalized) < 120:
            return True
        err_phrases = (
            "couldn't complete that",
            "couldnt complete that",
            "temporarily overloaded",
            "rate limit reached",
            "authentication issue",
            "something went wrong",
            "no llm configured",
        )
        return any(p in normalized for p in err_phrases)

    def _is_simple_greeting(msg: str) -> bool:
        if not msg or len(msg) > 50:
            return False
        lower = msg.strip().lower()
        greetings = ("hi", "hello", "hey", "howdy", "hi there", "hello there", "yo", "sup", "good morning", "good afternoon", "good evening")
        return lower in greetings or lower.rstrip("!?.") in greetings

    def _sanitize_messages(msgs: list[dict]) -> list[dict]:
        out = []
        for m in (msgs or []):
            if not isinstance(m, dict):
                continue
            role = m.get("role") or "user"
            content = m.get("content")
            if content is not None and isinstance(content, list):
                content = [b for b in content if isinstance(b, dict)]
            out.append({"role": role, "content": content if content else ""})
        return out

    def _llm_tools_call(msgs: list[dict]) -> dict:
        msgs = _sanitize_messages(msgs)
        system_prompt = _build_system_template(cid)
        if is_claude_configured():
            try:
                result = claude_tools_chat(msgs, COPILOT_TOOLS, system=system_prompt)
                if not isinstance(result, dict):
                    raise TypeError("Claude returned non-dict")
                if is_gemini_configured() and _is_error_response(result):
                    logger.info("Copilot: Claude returned error, falling back to Gemini")
                    out = gemini_tools_chat(msgs, COPILOT_TOOLS, system=system_prompt)
                    logger.info("Copilot: served by Gemini (fallback)")
                    return out
                logger.info("Copilot: served by Claude")
                return result
            except Exception as e:
                if is_gemini_configured():
                    logger.info("Copilot: Claude raised %s, falling back to Gemini", type(e).__name__)
                    out = gemini_tools_chat(msgs, COPILOT_TOOLS, system=system_prompt)
                    logger.info("Copilot: served by Gemini (fallback)")
                    return out
                raise
        if is_gemini_configured():
            logger.info("Copilot: served by Gemini (Claude not configured or not used)")
            return gemini_tools_chat(msgs, COPILOT_TOOLS, system=system_prompt)
        return {"answer": "No LLM configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY for the Copilot.", "data": [], "text": "No LLM configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY for the Copilot."}

    try:
        msg_clean = (message or "").strip()
        if not msg_clean:
            return {"answer": "Please type a message to get a response.", "data": [], "text": "Please type a message to get a response.", "session_id": sid}
        max_message_len = 32000
        if len(msg_clean) > max_message_len:
            msg_clean = msg_clean[:max_message_len] + "... [truncated]"
        message = msg_clean

        state = store.get_or_create_session(organization_id, sid)
        history = state.get_messages()
        messages = []
        max_history = 20
        for m in (history[-max_history:] if len(history) > max_history else history):
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user") or "user"
            content = m.get("content", "")
            if content is None:
                content = ""
            if role in ("user", "assistant"):
                content_str = str(content).strip() if content else ""
                messages.append({"role": role, "content": content_str or "(no content)"})
        messages.append({"role": "user", "content": message})

        reply_text = ""
        last_sql_data: list[dict] = []
        for _ in range(max_rounds):
            result = _llm_tools_call(messages)
            if not isinstance(result, dict):
                reply_text = "I couldn't generate a reply."
                break
            if "text" in result:
                reply_text = (result.get("text") or "").strip() or "I couldn't generate a reply."
                break
            tool_calls = [t for t in (result.get("tool_calls") or []) if isinstance(t, dict)]
            content_blocks = [b for b in (result.get("content_blocks") or []) if isinstance(b, dict)]
            if not tool_calls:
                break
            logger.info("Copilot tool round: %s tools", len(tool_calls))
            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                tid = tc.get("id") or tc.get("name") or ""
                name = (tc.get("name") or "").strip()
                if not name:
                    logger.warning("Copilot: skipping tool call with empty name")
                    continue
                args = tc.get("arguments")
                if not isinstance(args, dict):
                    args = {}
                try:
                    result_str = execute_tool(organization_id, cid, name, args)
                except Exception as tool_err:
                    logger.warning("Copilot tool %s failed: %s", name, tool_err)
                    result_str = json.dumps({"error": str(tool_err)[:200], "tool": name})
                if not isinstance(result_str, str):
                    result_str = json.dumps(result_str) if result_str is not None else "{}"
                # Track last run_sql or run_sql_raw rows for response data
                if name in ("run_sql", "run_sql_raw"):
                    try:
                        parsed = json.loads(result_str)
                        last_sql_data = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
                    except Exception:
                        last_sql_data = []
                tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": result_str})
            messages.append({"role": "user", "content": tool_results})

        final_text = (reply_text or "").strip() or "I couldn't generate a reply."
        if _is_error_response({"text": final_text}):
            if _is_simple_greeting(message):
                final_text = "Hi! How can I help with your marketing analytics today? You can ask about sessions, item views, traffic (e.g. from Google), or ad spend by channel."
            else:
                final_text = (
                    "I'm having trouble right now. Please try again in a moment, "
                    "or ask a specific question about the data (e.g. \"How many views for item IDs starting with FT05B?\")."
                )
        is_error = _is_error_response({"text": final_text}) or (
            "try again" in (final_text or "").lower() and "complete" in (final_text or "").lower() and len((final_text or "").strip()) < 120
        )
        if is_error:
            logger.info("Copilot: replacing LLM error response with friendly fallback (user msg=%s)", message[:50] if message else "")
            if _is_simple_greeting(message):
                final_text = "Hi! How can I help with your marketing analytics today? Ask about sessions, item views, traffic, or ad spend."
            else:
                final_text = (
                    "I'm having trouble right now. Please try again in a moment, "
                    "or ask a specific question about the data."
                )

        store.append(organization_id, sid, "user", message)
        store.append(organization_id, sid, "assistant", final_text, meta=None)
        # Response format: { answer, data } per spec. No charts/funnels/cards.
        return {
            "answer": final_text,
            "data": last_sql_data,
            "text": final_text,  # backward compat
            "session_id": sid,
        }
    except Exception as e:
        import traceback
        logger.exception(
            "Copilot chat failed | org=%s session_id=%s error=%s",
            organization_id, sid, str(e)[:200],
        )
        logger.info("Copilot traceback:\n%s", traceback.format_exc())
        msg_for_greeting = (message or "").strip().lower()
        if msg_for_greeting in ("hi", "hello", "hey", "howdy", "hi there", "hello there", "yo") or msg_for_greeting.rstrip("!?.") in ("hi", "hello", "hey"):
            return {"answer": "Hi! How can I help with your marketing analytics today? Ask about sessions, item views, traffic, or ad spend.", "data": [], "text": "Hi! How can I help with your marketing analytics today? Ask about sessions, item views, traffic, or ad spend.", "session_id": sid}
        err_preview = str(e)[:150].replace("\n", " ")
        return {
            "answer": f"I ran into a problem ({err_preview}). Please try again in a moment.",
            "data": [],
            "text": f"I ran into a problem ({err_preview}). Please try again in a moment.",
            "session_id": sid,
        }
