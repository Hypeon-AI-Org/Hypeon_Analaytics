"""
Gemini LLM client for Copilot. Supports Gemini API (API key) or Vertex AI (GCP).
Returns a callable(prompt: str) -> str for use with copilot_synthesizer.set_llm_client().
Max output tokens guarded via COPILOT_MAX_OUTPUT_TOKENS (default 2048) to prevent cost explosion.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Env: GEMINI_API_KEY or GOOGLE_API_KEY (Gemini API); or GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION (Vertex AI)
# Optional: GEMINI_MODEL (default gemini-2.0-flash), COPILOT_MAX_OUTPUT_TOKENS (default 2048)


def _get_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def _get_max_output_tokens() -> int:
    try:
        return min(8192, max(256, int(os.environ.get("COPILOT_MAX_OUTPUT_TOKENS", "2048"))))
    except (TypeError, ValueError):
        return 2048


def _build_client():
    """Build google.genai Client from env (API key or Vertex AI)."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")

    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("BQ_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            raise ValueError("Vertex AI requires GOOGLE_CLOUD_PROJECT or BQ_PROJECT")
        return genai.Client(vertexai=True, project=project, location=location)
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client()


def make_gemini_copilot_client() -> Callable[[str], str]:
    """
    Return a callable(prompt: str) -> str that uses Gemini for Copilot.
    Uses GEMINI_API_KEY / GOOGLE_API_KEY (Gemini API) or Vertex AI env vars.
    On LLM errors, returns a minimal JSON so the API does not 500.
    """
    client = _build_client()
    model = _get_model()

    max_tokens = _get_max_output_tokens()

    def _call(prompt: str) -> str:
        t0 = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": max_tokens},
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Empty response from Gemini")
            elapsed_ms = (time.perf_counter() - t0) * 1000
            usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
            logger.info(
                "copilot_llm latency_ms=%.0f max_output_tokens=%s prompt_len=%d",
                elapsed_ms, max_tokens, len(prompt),
                extra={"usage": str(usage) if usage else None},
            )
            return text
        except Exception as e:
            return json.dumps({
                "summary": "Analysis temporarily unavailable.",
                "explanation": f"The model could not complete the request: {str(e)[:200]}.",
                "business_reasoning": "Please try again or use the insight data above.",
                "action_steps": [],
                "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
                "provenance": "analytics_insights, decision_history, supporting_metrics_snapshot",
                "confidence": 0.3,
                "tldr": "Request failed; see explanation.",
            })

    return _call


def _tools_to_gemini_declarations(tools: list[dict]):
    """Convert COPILOT_TOOLS format to Gemini FunctionDeclaration list."""
    from google.genai import types
    decls = []
    for t in tools:
        decl = types.FunctionDeclaration(
            name=t["name"],
            description=t.get("description") or "",
            parameters=t.get("input_schema") or {"type": "object", "properties": {}},
        )
        decls.append(decl)
    return decls


def chat_completion_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    system: str | None = None,
) -> dict:
    """
    Multi-turn chat with tool use. messages = [{"role": "user"|"assistant", "content": "..." or list}, ...].
    Builds a single prompt from messages; passes tools to Gemini. Returns {"text": "..."} or {"tool_calls": [...], "content_blocks": [...]}.
    """
    if not messages:
        return {"text": ""}
    try:
        from google.genai.types import GenerateContentConfig, Content, Part

        client = _build_client()
        model = _get_model()
        max_tokens = _get_max_output_tokens()

        # Build conversation as prompt string for Gemini
        prompt_parts = []
        if system:
            prompt_parts.append(f"[System]\n{system}\n\n")
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = (m.get("role") or "user").capitalize()
            content = m.get("content") or ""
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        prompt_parts.append(f"{role}: {block.get('text', '')}\n\n")
                    elif isinstance(block, dict) and block.get("type") == "tool_result":
                        prompt_parts.append(f"[Tool result]\n{block.get('content', '')}\n\n")
            else:
                prompt_parts.append(f"{role}: {content}\n\n")
        prompt_parts.append("Assistant:")
        prompt_str = "".join(prompt_parts)

        config = GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=max_tokens,
            tools=_tools_to_gemini_declarations(tools),
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt_str,
            config=config,
        )

        # Parse response for text or function_call
        text_parts = []
        tool_calls = []
        content_blocks = []
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                    content_blocks.append({"type": "text", "text": part.text})
                fc = getattr(part, "function_call", None)
                if fc:
                    name = getattr(fc, "name", None) or ""
                    raw_args = getattr(fc, "args", None)
                    if isinstance(raw_args, dict):
                        args = raw_args
                    elif isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args) if raw_args else {}
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    else:
                        # Protobuf Struct or other: try to get dict
                        try:
                            args = dict(raw_args) if raw_args else {}
                        except (TypeError, ValueError):
                            args = {}
                    if not isinstance(args, dict):
                        args = {}
                    tool_calls.append({"id": name, "name": name, "arguments": args})
                    content_blocks.append({"type": "tool_use", "id": name, "name": name, "input": args})

        if tool_calls:
            return {"tool_calls": tool_calls, "content_blocks": content_blocks}
        return {"text": "".join(text_parts).strip()}
    except Exception as e:
        logger.warning(
            "Gemini chat with tools failed | error=%s | type=%s",
            str(e)[:400],
            type(e).__name__,
            exc_info=False,
        )
        return {"text": "I couldn't complete that. Please try again."}


def is_gemini_configured() -> bool:
    """True if Gemini API key or Vertex AI is configured so we can use Gemini for Copilot."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return True
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes"):
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("BQ_PROJECT")
        return bool(project)
    return False


def stream_gemini(prompt: str):
    """
    Yield text chunks from Gemini (streaming). Falls back to non-streaming then yield full text if stream not supported.
    Uses COPILOT_MAX_OUTPUT_TOKENS for max_output_tokens guard.
    """
    max_tokens = _get_max_output_tokens()
    t0 = time.perf_counter()
    try:
        client = _build_client()
        model = _get_model()
        if hasattr(client.models, "generate_content_stream"):
            response = client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": max_tokens},
            )
            for chunk in response:
                if chunk and getattr(chunk, "text", None):
                    yield chunk.text
        else:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": max_tokens},
            )
            text = (response.text or "").strip()
            if text:
                yield text
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("copilot_llm_stream latency_ms=%.0f max_output_tokens=%s prompt_len=%d", elapsed_ms, max_tokens, len(prompt))
    except Exception as e:
        yield json.dumps({
            "summary": "Analysis temporarily unavailable.",
            "explanation": f"The model could not complete the request: {str(e)[:200]}.",
            "business_reasoning": "Please try again or use the insight data above.",
            "action_steps": [],
            "expected_impact": {"metric": "revenue", "estimate": 0.0, "units": "currency"},
            "provenance": "analytics_insights, decision_history, supporting_metrics_snapshot",
            "confidence": 0.3,
            "tldr": "Request failed; see explanation.",
        })
