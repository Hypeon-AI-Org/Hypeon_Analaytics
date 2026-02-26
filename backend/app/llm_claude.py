"""
Claude LLM client for Copilot. Uses Anthropic SDK (anthropic package).
Retries on 429 (rate limit) and 529 (overloaded) with exponential backoff.
Env: ANTHROPIC_API_KEY (required). Optional: CLAUDE_MODEL, COPILOT_MAX_OUTPUT_TOKENS.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable, Generator

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)

# Retry on transient API errors (rate limit, overloaded)
def _is_retryable_error(exc: BaseException) -> bool:
    s = str(exc)
    s_lower = s.lower()
    return (
        "429" in s or "529" in s
        or "rate_limit" in s_lower
        or "overloaded" in s_lower
        or "rate limit" in s_lower
    )

# Optional: CLAUDE_MODEL (default primary), COPILOT_MAX_OUTPUT_TOKENS (default 2048)
# CLAUDE_MODEL_FALLBACKS: comma-separated model ids to try after primary. If unset, uses full list (newest first).

# All known Claude models in descending order by release date (newest first). Used when CLAUDE_MODEL_FALLBACKS is not set.
CLAUDE_MODELS_BY_RELEASE_DESC = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-1-20250805",
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


def _get_model() -> str:
    return os.environ.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)


def _get_claude_models_to_try() -> list[str]:
    """Return list of Claude model ids to try in order: primary first, then fallbacks (descending by release date)."""
    primary = (os.environ.get("CLAUDE_MODEL") or "").strip() or DEFAULT_CLAUDE_MODEL
    fallbacks_str = (os.environ.get("CLAUDE_MODEL_FALLBACKS") or "").strip()
    if fallbacks_str:
        fallbacks = [m.strip() for m in fallbacks_str.split(",") if m.strip()]
    else:
        # Use full list in descending release order, but put primary first and skip duplicates
        fallbacks = [m for m in CLAUDE_MODELS_BY_RELEASE_DESC if m != primary]
    seen = {primary}
    out = [primary]
    for m in fallbacks:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _get_max_output_tokens() -> int:
    try:
        return min(8192, max(256, int(os.environ.get("COPILOT_MAX_OUTPUT_TOKENS", "2048"))))
    except (TypeError, ValueError):
        return 2048


def _build_client():
    """Build Anthropic client from env (ANTHROPIC_API_KEY)."""
    from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Claude requires ANTHROPIC_API_KEY")
    return Anthropic(api_key=api_key)


@retry(
    retry=retry_if_exception(_is_retryable_error),
    wait=wait_random_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
    before_sleep=lambda rs: logger.warning(
        "Claude API retry %s/5",
        rs.attempt_number,
    ),
)
def _messages_create_with_retry(client, **kwargs):
    """Single Claude API call with retry on 429/529."""
    return client.messages.create(**kwargs)


def _is_overloaded_error(exc: BaseException) -> bool:
    """True if error is 529 or overloaded (try next model)."""
    s = str(exc).lower()
    return "529" in str(exc) or "overloaded" in s


def _claude_error_message(err_str: str) -> str:
    """Return user-facing message for Claude API errors."""
    err_lower = err_str.lower()
    if "529" in err_str or "overloaded" in err_lower:
        return "The AI service is temporarily overloaded. Please try again in a minute or two."
    if "429" in err_str or "rate" in err_lower:
        return "Rate limit reached. Please wait a moment and try again."
    # Only show auth message for real auth errors (401, invalid api key, unauthorized)
    if "401" in err_str or "unauthorized" in err_lower or "invalid api key" in err_lower or "invalid_api_key" in err_lower:
        return "There was an authentication issue. Please check that ANTHROPIC_API_KEY is set correctly."
    return "I couldn't complete that. Please try again."


def _fallback_json() -> str:
    """Return minimal JSON on LLM errors so the API does not 500."""
    return json.dumps({
        "summary": "Analysis temporarily unavailable.",
        "explanation": "The model could not complete the request.",
        "business_reasoning": "Please try again or use the insight data above.",
        "action_steps": [],
        "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
        "provenance": "analytics_insights, decision_history, supporting_metrics_snapshot",
        "confidence": 0.3,
        "tldr": "Request failed; see explanation.",
    })


def make_claude_copilot_client() -> Callable[[str], str]:
    """
    Return a callable(prompt: str) -> str that uses Claude via Anthropic SDK for Copilot.
    Uses ANTHROPIC_API_KEY. On LLM errors, returns minimal JSON so the API does not 500.
    """
    client = _build_client()
    model = _get_model()
    max_tokens = _get_max_output_tokens()

    def _call(prompt: str) -> str:
        t0 = time.perf_counter()
        try:
            response = _messages_create_with_retry(
                client,
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            text_parts = []
            for block in (response.content or []):
                if getattr(block, "text", None):
                    text_parts.append(block.text)
            text = "".join(text_parts).strip()
            if not text:
                raise ValueError("Empty response from Claude")
            elapsed_ms = (time.perf_counter() - t0) * 1000
            usage = getattr(response, "usage", None)
            logger.info(
                "copilot_llm (claude) latency_ms=%.0f max_tokens=%s prompt_len=%d",
                elapsed_ms, max_tokens, len(prompt),
                extra={"usage": str(usage) if usage else None},
            )
            return text
        except Exception as e:
            logger.warning(
                "Claude request failed | error=%s | type=%s",
                str(e)[:400],
                type(e).__name__,
                exc_info=True,
            )
            return _fallback_json()

    return _call


def is_claude_configured() -> bool:
    """True if ANTHROPIC_API_KEY is set so we can use Claude for Copilot."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def chat_completion(messages: list[dict], *, system: str | None = None) -> str:
    """
    Multi-turn chat: messages = [{"role": "user"|"assistant", "content": "..."}, ...].
    Optional system prompt. Returns assistant reply text.
    """
    if not messages:
        return ""
    try:
        client = _build_client()
        model = _get_model()
        max_tokens = _get_max_output_tokens()
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": 0.2,
        }
        if system:
            kwargs["system"] = system
        response = _messages_create_with_retry(client, **kwargs)
        text_parts = []
        for block in (response.content or []):
            if getattr(block, "text", None):
                text_parts.append(block.text)
        return "".join(text_parts).strip()
    except Exception as e:
        err_str = str(e)
        logger.warning(
            "Claude chat failed | error=%s | type=%s",
            err_str[:400],
            type(e).__name__,
            exc_info=True,
        )
        msg = _claude_error_message(err_str)
        if msg == "I couldn't complete that. Please try again.":
            logger.info(
                "Copilot generic fallback (user sees 'Please try again'). Actual error: %s",
                err_str[:500],
            )
        return msg


def chat_completion_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    system: str | None = None,
    max_rounds: int = 5,
) -> dict:
    """
    Multi-turn chat with tool use. messages = [{"role": "user"|"assistant", "content": "..." or list[blocks]}, ...].
    tools = list of {name, description, input_schema} (JSON Schema).
    Returns {"text": "..."} for final reply, or {"tool_calls": [{"id", "name", "arguments"}]} when LLM requests tools.
    """
    if not messages:
        return {"text": ""}
    client = _build_client()
    max_tokens = _get_max_output_tokens()
    anthropic_tools = []
    for t in (tools or []):
        if not isinstance(t, dict):
            continue
        name = t.get("name")
        if not name:
            continue
        anthropic_tools.append({
            "name": name,
            "description": t.get("description") or "",
            "input_schema": t.get("input_schema") if isinstance(t.get("input_schema"), dict) else {"type": "object", "properties": {}},
        })
    base_kwargs = {
        "max_tokens": max_tokens,
        "messages": messages,
        "tools": anthropic_tools,
        "tool_choice": {"type": "auto"},
        "temperature": 0.2,
    }
    if system:
        base_kwargs["system"] = system

    models_to_try = _get_claude_models_to_try()
    last_exception = None
    for model in models_to_try:
        try:
            kwargs = {**base_kwargs, "model": model}
            response = _messages_create_with_retry(client, **kwargs)
            content = response.content or []
            tool_calls = []
            text_parts = []
            content_blocks = []
            for block in content:
                btype = getattr(block, "type", None)
                if btype == "tool_use":
                    raw_input = getattr(block, "input", None)
                    if isinstance(raw_input, dict):
                        block_args = raw_input
                    elif isinstance(raw_input, str):
                        try:
                            block_args = json.loads(raw_input) if raw_input else {}
                        except (json.JSONDecodeError, TypeError):
                            block_args = {}
                    else:
                        block_args = {}
                    tool_calls.append({
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "arguments": block_args,
                    })
                    content_blocks.append({
                        "type": "tool_use",
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": block_args,
                    })
                elif getattr(block, "text", None):
                    text_parts.append(block.text)
                    content_blocks.append({"type": "text", "text": block.text})
            if tool_calls:
                return {"tool_calls": tool_calls, "content_blocks": content_blocks}
            return {"text": "".join(text_parts).strip()}
        except Exception as e:
            last_exception = e
            err_str = str(e)
            if _is_overloaded_error(e):
                logger.warning(
                    "Claude model %s overloaded (529), trying next model",
                    model,
                )
                continue
            if _is_retryable_error(e):
                logger.warning(
                    "Claude model %s retryable error, trying next model: %s",
                    model,
                    err_str[:200],
                )
                continue
            logger.warning(
                "Claude chat with tools failed | model=%s | error=%s | type=%s",
                model,
                err_str[:400],
                type(e).__name__,
                exc_info=True,
            )
            msg = _claude_error_message(err_str)
            return {"text": msg}

    err_str = str(last_exception or "")
    logger.warning(
        "Claude chat with tools failed on all models | last_error=%s",
        err_str[:400],
    )
    msg = _claude_error_message(err_str)
    return {"text": msg}


def stream_claude(prompt: str) -> Generator[str, None, None]:
    """
    Yield text chunks from Claude (streaming) via Anthropic SDK.
    Uses COPILOT_MAX_OUTPUT_TOKENS for max_tokens guard.
    """
    max_tokens = _get_max_output_tokens()
    t0 = time.perf_counter()
    try:
        client = _build_client()
        model = _get_model()
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "copilot_llm_stream (claude) latency_ms=%.0f max_tokens=%s prompt_len=%d",
            elapsed_ms, max_tokens, len(prompt),
        )
    except Exception as e:
        logger.warning(
            "Claude stream failed | error=%s | type=%s",
            str(e)[:400],
            type(e).__name__,
            exc_info=True,
        )
        yield _fallback_json()
