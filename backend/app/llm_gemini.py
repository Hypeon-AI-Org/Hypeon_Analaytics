"""
Gemini LLM client for Copilot. Supports Gemini API (API key) or Vertex AI (GCP).
Returns a callable(prompt: str) -> str for use with copilot_synthesizer.set_llm_client().
"""
from __future__ import annotations

import json
import os
from typing import Callable

# Env: GEMINI_API_KEY or GOOGLE_API_KEY (Gemini API); or GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION (Vertex AI)
# Optional: GEMINI_MODEL (default gemini-2.0-flash)


def _get_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


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

    def _call(prompt: str) -> str:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": 2048},
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Empty response from Gemini")
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
    """
    try:
        client = _build_client()
        model = _get_model()
        if hasattr(client.models, "generate_content_stream"):
            response = client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": 2048},
            )
            for chunk in response:
                if chunk and getattr(chunk, "text", None):
                    yield chunk.text
        else:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": 2048},
            )
            text = (response.text or "").strip()
            if text:
                yield text
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
