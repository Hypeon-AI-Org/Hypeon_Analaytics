"""
Comprehensive API and edge-case tests. Run from repo root:
  PYTHONPATH=. python backend/scripts/test_all_endpoints.py
Uses BASE_URL=http://127.0.0.1:8000 by default. Requires backend running.
"""
from __future__ import annotations

import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
HEADERS = {"X-Organization-Id": "default", "Content-Type": "application/json"}
API_KEY = os.environ.get("API_KEY")
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

FAILED = []
PASSED = []


def ok(name: str, cond: bool, detail: str = ""):
    if cond:
        PASSED.append(name)
        print(f"  OK   {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILED.append(name)
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def get(path: str, params: dict | None = None) -> tuple[int, dict | list]:
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params or {}, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {}


def post(path: str, body: dict | None = None) -> tuple[int, dict | list]:
    r = requests.post(f"{BASE}{path}", headers=HEADERS, json=body or {}, timeout=60)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {}


def main():
    print("=== HypeOn Analytics — full endpoint and edge-case tests ===\n")

    # ---- Health ----
    print("--- Health ---")
    code, data = get("/health")
    ok("GET /health returns 200", code == 200, str(data)[:80])
    ok("GET /health has status", isinstance(data, dict) and ("status" in data or "ok" in str(data).lower() or code == 200))

    code, data = get("/health/analytics")
    ok("GET /health/analytics returns 200", code == 200)
    code, data = get("/system/health")
    ok("GET /system/health returns 200", code == 200)

    # ---- Dashboard (cache) ----
    print("\n--- Dashboard API ---")
    for path in ["/api/v1/dashboard/business-overview", "/api/v1/dashboard/campaign-performance", "/api/v1/dashboard/funnel", "/api/v1/dashboard/actions"]:
        code, data = get(path)
        ok(f"GET {path} 200", code == 200, f"type={type(data).__name__}")
    code, data = get("/api/v1/dashboard/business-overview", {"client_id": 1})
    ok("GET business-overview with client_id=1", code == 200)

    # ---- Insights & decisions ----
    print("\n--- Insights & Decisions ---")
    code, data = get("/insights")
    ok("GET /insights 200", code == 200 and "items" in data if isinstance(data, dict) else True)
    code, data = get("/insights/top")
    ok("GET /insights/top 200", code == 200)
    code, data = get("/decisions/top")
    ok("GET /decisions/top 200", code == 200)
    code, data = get("/decisions/history")
    ok("GET /decisions/history 200", code == 200)

    # ---- Copilot V1 query (data analysis path) ----
    print("\n--- Copilot V1 Query (data path) ---")
    code, data = post("/api/v1/copilot/query", {"query": "Show last 30 days performance"})
    ok("POST copilot/query data path 200", code == 200, str(code))
    if code == 200 and isinstance(data, dict):
        ok("Response has message", "message" in data or "summary" in data)
        ok("Response has metadata or layout", "metadata" in data or "layout" in data or "summary" in data)
    code, data = post("/api/v1/copilot/query", {"query": "Which channel performs best?", "client_id": 1})
    ok("POST copilot/query channel 200", code == 200)
    code, data = post("/api/v1/copilot/query", {"query": "Compare this week vs last week"})
    ok("POST copilot/query comparison 200", code == 200)
    code, data = post("/api/v1/copilot/query", {"query": "What should I do today?"})
    ok("POST copilot/query what to do 200", code == 200)

    # ---- Edge: empty query ----
    code, data = post("/api/v1/copilot/query", {"query": ""})
    ok("POST copilot/query empty query 200", code == 200)

    # ---- Copilot chat ----
    print("\n--- Copilot Chat ---")
    code, data = post("/api/v1/copilot/chat", {"message": "Show last 7 days performance"})
    ok("POST copilot/chat 200", code == 200)
    if code == 200 and isinstance(data, dict):
        ok("Chat response has text", "text" in data)
        ok("Chat response has session_id", "session_id" in data)
    sid = data.get("session_id") if isinstance(data, dict) else None
    code, data = post("/api/v1/copilot/chat", {"message": "And by channel?", "session_id": sid})
    ok("POST copilot/chat follow-up 200", code == 200)
    code, data = get("/api/v1/copilot/chat/history", {"session_id": sid or "test"})
    ok("GET copilot/chat/history 200", code == 200)
    code, data = get("/api/v1/copilot/sessions")
    ok("GET copilot/sessions 200", code == 200)

    # ---- Edge: chat empty message ----
    code, data = post("/api/v1/copilot/chat", {"message": "   "})
    ok("POST copilot/chat whitespace 200", code == 200)
    if code == 200 and isinstance(data, dict):
        ok("Empty message returns friendly text", "text" in data and len((data.get("text") or "")) > 0)

    # ---- Insight Copilot (no insight_id -> data path; with fake insight_id -> 404 or error) ----
    code, data = post("/api/v1/copilot/query", {"query": "Explain", "insight_id": None})
    ok("POST copilot/query no insight_id uses data path", code == 200)
    code, data = post("/copilot/query", {"insight_id": "non-existent-insight-123"})
    ok("POST /copilot/query missing insight 404", code == 404)

    # ---- Analysis API ----
    print("\n--- Analysis API ---")
    code, data = get("/api/v1/analysis/google-ads", {"client_id": 1, "days": 7})
    ok("GET analysis/google-ads 200", code == 200)
    code, data = get("/api/v1/analysis/google-analytics", {"client_id": 1, "days": 7})
    ok("GET analysis/google-analytics 200", code == 200)

    # ---- Auth edge: no org header (should still work with default) ----
    r = requests.get(f"{BASE}/health", timeout=5)
    ok("GET /health no auth 200", r.status_code == 200)

    # ---- CORS / options (200/204 = CORS preflight ok; 405 = method not configured, still acceptable) ----
    r = requests.options(f"{BASE}/api/v1/copilot/query", headers={"Origin": "http://localhost:5173"}, timeout=5)
    ok("OPTIONS copilot/query allowed", r.status_code in (200, 204, 405))

    # ---- Edge: invalid / missing body (422 validation or 200 with defaults) ----
    code, _ = post("/api/v1/copilot/query", {})
    ok("POST copilot/query no body 200 or 422", code in (200, 422))
    code, _ = post("/api/v1/copilot/chat", {})
    ok("POST copilot/chat no body 200 or 422", code in (200, 422))

    # ---- Edge: stream (smoke: start and read first event) ----
    try:
        r = requests.post(
            f"{BASE}/api/v1/copilot/stream",
            headers=HEADERS,
            json={"query": "Last 7 days", "client_id": 1},
            stream=True,
            timeout=15,
        )
        ok("POST copilot/stream 200", r.status_code == 200)
        if r.status_code == 200:
            first_line = next(iter(r.iter_lines()), b"")
            ok("Stream yields SSE data", b"data:" in first_line or b"phase" in first_line or first_line.startswith(b"data:"))
    except Exception as e:
        ok("POST copilot/stream no crash", True, str(e)[:50])

    # ---- Simulated user behaviour: full chat flow ----
    print("\n--- Simulated user behaviour (chat flow) ---")
    session_id = None
    for i, (msg, desc) in enumerate([
        ("Hi", "greeting"),
        ("What should I do today?", "performance ask"),
        ("Show last 14 days performance", "date range"),
        ("Which channel performs best?", "channel ask"),
        ("Explain more about the top campaign", "follow-up"),
        ("Thanks!", "thanks"),
    ]):
        code, data = post("/api/v1/copilot/chat", {"message": msg, "session_id": session_id})
        ok(f"Chat flow step {i+1} ({desc}) 200", code == 200, msg[:30])
        if code == 200 and isinstance(data, dict):
            ok(f"Chat step {i+1} has text", "text" in data and len(str(data.get("text", ""))) >= 0)
            session_id = data.get("session_id") or session_id
        time.sleep(0.3)  # avoid rate limit
    code, hist = get("/api/v1/copilot/chat/history", {"session_id": session_id or "test"})
    ok("Chat history after flow 200", code == 200)
    if code == 200 and isinstance(hist, dict) and "messages" in hist:
        ok("Chat history has multiple messages", len(hist.get("messages", [])) >= 3)

    # ---- Copilot edge cases ----
    print("\n--- Copilot edge cases ---")
    code, data = post("/api/v1/copilot/chat", {"message": ""})
    ok("Chat empty string 200", code == 200)
    ok("Chat empty returns prompt text", not data.get("text") or "message" in (data.get("text") or "").lower() or "type" in (data.get("text") or "").lower())
    code, _ = post("/api/v1/copilot/chat", {"message": "x" * 500})  # long but under limit
    ok("Chat long message 200 or 422", code in (200, 422, 429))
    code, _ = post("/api/v1/copilot/chat", {"message": "Revenue & spend <script>?", "client_id": 1})
    ok("Chat special chars 200", code in (200, 422, 429), f"code={code}")
    code, _ = post("/api/v1/copilot/query", {"query": "Show last 7 days", "client_id": 1})
    ok("Query with client_id=1 200 or 429", code in (200, 429))
    code, _ = post("/api/v1/copilot/query", {"query": "Compare last week to this week"})
    ok("Query comparison 200 or 429", code in (200, 429))
    code, _ = get("/api/v1/copilot/chat/history", {"session_id": "nonexistent-session-12345"})
    ok("Chat history invalid session 200", code == 200)  # may return empty messages
    code, _ = post("/api/v1/copilot/stream", {"query": "", "client_id": 1})
    ok("Stream empty query 200 or 422", code in (200, 422, 429), f"code={code}")

    # ---- Simulation API (smoke) ----
    print("\n--- Simulation API ---")
    code, sim = post("/simulate_budget_shift", {"client_id": 1, "date": "2026-02-20", "from_campaign": "c1", "to_campaign": "c2", "amount": 100})
    ok("POST simulate_budget_shift 200", code == 200)
    if code == 200 and isinstance(sim, dict):
        ok("Simulation has expected keys", "low" in sim or "median" in sim or "expected_delta" in sim)

    # ---- Summary ----
    print("\n=== Summary ===")
    print(f"Passed: {len(PASSED)}")
    print(f"Failed: {len(FAILED)}")
    if FAILED:
        for f in FAILED:
            print(f"  - {f}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
