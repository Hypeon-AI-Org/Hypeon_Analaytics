"""
Copilot chat handler: multi-turn conversation with tools (on-demand data fetch) and optional layout.
Uses session_memory for history; LLM calls tools only when needed; executor returns JSON for each tool.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

from .query_contract import validate_layout
from .layout_generator import _sanitize_widget, _validate_widget_type
from .tools import COPILOT_TOOLS, execute_tool

logger = logging.getLogger(__name__)

VALID_WIDGET_TYPES = frozenset(("kpi", "chart", "table", "funnel"))

SYSTEM_TEMPLATE = """You are an expert marketing analytics assistant. You have tools to fetch live data when needed.

## When to use tools
- Use tools when the user asks about: performance, revenue, spend, ROAS, campaigns, funnel, conversions, Google Ads, Google Analytics (GA4), recommended actions, or decision history.
- For greetings, thanks, or conceptual questions (e.g. "what is ROAS?"), answer from knowledge without calling tools.
- For follow-ups like "what about last 7 days?" or "by device?", call the relevant tool with the right parameters (e.g. days=7).

## Answering
- Base answers only on tool results or the conversation. Never invent metrics.
- Be clear and concise. Do not use emojis in your responses.
- Present the best report for the user's query: use bullet points, and when data is numeric or comparative, prefer tables and charts so the UI can render them.
- When the user asks for an overview, performance summary, or any data-driven answer, include a JSON layout block at the end so the UI can render visuals. Use this format: ```json {{"layout": {{ "widgets": [ ... ] }} }} ```
- Supported widgets: kpi (title, value, trend, subtitle), chart (chartType: line|bar|pie; title; data; xKey; yKey), table (title; columns with key/label; rows), funnel (title; stages with name, value, dropPct).
- When you have no data or empty results, say so and suggest what they can ask next."""


def _extract_layout_from_response(text: str) -> tuple[str, Optional[dict]]:
    """
    Parse optional layout from LLM response. Looks for ```json ... {"layout": {"widgets": [...]}} ... ``` or ```json ... {"widgets": [...]} ... ```.
    Returns (text_without_layout_block, layout_dict or None).
    """
    if not isinstance(text, str):
        text = str(text) if text else ""
    layout = None
    # Match ```json ... ``` block
    pattern = r"```(?:json)?\s*(\{[^`]*\})\s*```"
    for m in re.finditer(pattern, text, re.DOTALL):
        try:
            raw = json.loads(m.group(1))
            if not isinstance(raw, dict):
                continue
            if "layout" in raw and isinstance(raw.get("layout"), dict):
                layout = raw["layout"]
            elif "widgets" in raw and isinstance(raw.get("widgets"), list):
                layout = raw
            if layout and isinstance(layout, dict):
                # Remove this block from text for display
                text = text.replace(m.group(0), "").strip()
                break
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    if layout and isinstance(layout, dict) and "widgets" in layout:
        try:
            widgets = []
            raw_widgets = layout.get("widgets", [])
            if not isinstance(raw_widgets, list):
                raw_widgets = []
            for w in raw_widgets:
                if not isinstance(w, dict):
                    continue
                if _validate_widget_type(w):
                    out_w = _sanitize_widget(w)
                    if isinstance(out_w, dict):
                        widgets.append(out_w)
            layout = {"widgets": widgets}
            valid, _ = validate_layout(layout)
            if not valid:
                layout = None
        except Exception as e:
            logger.warning("Layout extraction failed: %s", e)
            layout = None
    else:
        layout = None
    return (text.strip(), layout)


def chat(
    organization_id: str,
    message: str,
    *,
    session_id: Optional[str] = None,
    client_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    One turn of chat: get history, build messages, call LLM with tools (loop until final reply), parse layout, persist to session.
    Returns { "text", "layout"?, "session_id" }. Never raises; returns error message in text on failure.
    """
    try:
        from .session_memory import get_session_store
        from ..llm_claude import is_claude_configured, chat_completion_with_tools as claude_tools_chat
        from ..llm_gemini import is_gemini_configured, chat_completion_with_tools as gemini_tools_chat
    except Exception as e:
        logger.exception("Copilot chat imports failed")
        sid = session_id or str(uuid.uuid4())
        return {"text": f"Configuration error: {str(e)[:200]}", "session_id": str(sid)}

    store = get_session_store()
    sid = session_id or str(uuid.uuid4())
    sid = str(sid)
    cid = int(client_id) if client_id is not None else 1
    max_rounds = 5

    def _is_error_response(result: dict) -> bool:
        """True if result is a text-only error message (Claude failed); use for Gemini fallback."""
        if result.get("tool_calls"):
            return False
        text = (result.get("text") or "").strip()
        if not text:
            return False
        err_phrases = (
            "I couldn't complete that",
            "temporarily overloaded",
            "Rate limit reached",
            "authentication issue",
            "Something went wrong",
        )
        return any(p in text for p in err_phrases)

    def _sanitize_messages(msgs: list[dict]) -> list[dict]:
        """Ensure every message has content as string or list of dicts; avoid .get on non-dict."""
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
        if is_claude_configured():
            try:
                result = claude_tools_chat(msgs, COPILOT_TOOLS, system=SYSTEM_TEMPLATE)
                if not isinstance(result, dict):
                    raise TypeError("Claude returned non-dict")
                if is_gemini_configured() and _is_error_response(result):
                    logger.info("Copilot: Claude returned error, falling back to Gemini")
                    out = gemini_tools_chat(msgs, COPILOT_TOOLS, system=SYSTEM_TEMPLATE)
                    logger.info("Copilot: served by Gemini (fallback)")
                    return out
                logger.info("Copilot: served by Claude")
                return result
            except Exception as e:
                if is_gemini_configured():
                    logger.info("Copilot: Claude raised %s, falling back to Gemini", type(e).__name__)
                    out = gemini_tools_chat(msgs, COPILOT_TOOLS, system=SYSTEM_TEMPLATE)
                    logger.info("Copilot: served by Gemini (fallback)")
                    return out
                raise
        if is_gemini_configured():
            logger.info("Copilot: served by Gemini (Claude not configured or not used)")
            return gemini_tools_chat(msgs, COPILOT_TOOLS, system=SYSTEM_TEMPLATE)
        return {"text": "No LLM configured. Set ANTHROPIC_API_KEY or GEMINI_API_KEY for the Copilot."}

    try:
        # Edge case: empty or whitespace-only message
        msg_clean = (message or "").strip()
        if not msg_clean:
            return {
                "text": "Please type a message to get a response.",
                "session_id": sid,
            }
        # Cap message length to avoid token overflow (optional; ~4 chars per token)
        max_message_len = 32000
        if len(msg_clean) > max_message_len:
            msg_clean = msg_clean[:max_message_len] + "... [truncated]"
        message = msg_clean

        state = store.get_or_create_session(organization_id, sid)
        history = state.get_messages()
        messages = []
        for m in history:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user") or "user"
            content = m.get("content", "")
            if content is None:
                content = ""
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": message})

        reply_text = ""
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
            # Append assistant message with tool_use (and any text) blocks
            messages.append({"role": "assistant", "content": content_blocks})
            # Build tool_result blocks and append as user message
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
                result_str = execute_tool(organization_id, cid, name, args)
                if not isinstance(result_str, str):
                    result_str = json.dumps(result_str) if result_str is not None else "{}"
                tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": result_str})
            messages.append({"role": "user", "content": tool_results})

        reply_text = (reply_text or "").strip() or "I couldn't generate a reply."
        text_clean, layout = _extract_layout_from_response(reply_text)

        store.append(organization_id, sid, "user", message)
        store.append(
            organization_id, sid, "assistant", text_clean or reply_text,
            meta={"layout": layout} if layout else None,
        )

        out = {"text": text_clean or reply_text, "session_id": sid}
        if layout:
            out["layout"] = layout
        return out
    except Exception as e:
        import traceback
        logger.exception(
            "Copilot chat failed | org=%s session_id=%s error=%s",
            organization_id, sid, str(e)[:200],
        )
        logger.info("Copilot traceback:\n%s", traceback.format_exc())
        return {
            "text": f"Something went wrong: {str(e)[:300]}. Try again or check that ANTHROPIC_API_KEY or GEMINI_API_KEY is set.",
            "session_id": sid,
        }
