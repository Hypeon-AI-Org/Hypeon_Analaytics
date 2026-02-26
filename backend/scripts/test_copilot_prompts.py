#!/usr/bin/env python3
"""
Test Copilot: one session, follow-ups, every use case.
Reports latency per turn and summary. Includes edge cases (empty, long message).
"""
import os
import sys
import time

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env = os.path.join(_root, ".env")
if os.path.isfile(_env):
    from dotenv import load_dotenv
    load_dotenv(_env)

import requests

BASE = os.environ.get("TEST_API_BASE", "http://127.0.0.1:8000")
HEADERS = {"Content-Type": "application/json", "X-Organization-Id": "default"}
TIMEOUT = 120


def safe_print(text: str, max_len: int = 500) -> None:
    preview = (text or "")[:max_len] + ("..." if len(text or "") > max_len else "")
    try:
        print(preview)
    except UnicodeEncodeError:
        print(preview.encode("ascii", "replace").decode("ascii"))


def send(session_id: str | None, message: str) -> tuple[str | None, str, bool, float]:
    """Send one message; return (session_id, reply_text, ok, latency_ms)."""
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    try:
        t0 = time.perf_counter()
        r = requests.post(f"{BASE}/api/v1/copilot/chat", json=body, headers=HEADERS, timeout=TIMEOUT)
        latency_ms = (time.perf_counter() - t0) * 1000
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        sid = data.get("session_id") or session_id
        text = (data.get("text") or "").strip()
        ok = r.ok and "Something went wrong" not in text and "couldn't complete" not in text.lower()
        return sid, text, ok, latency_ms
    except requests.exceptions.ConnectionError:
        print("  [FAIL] Connection refused. Is the backend running on 8000?")
        return session_id, "", False, 0.0
    except Exception as e:
        print(f"  [FAIL] {e}")
        return session_id, "", False, 0.0


# Full conversation + edge cases
CONVERSATION = [
    ("Greeting", "Hi, I need help with my marketing analytics."),
    ("Follow-up greeting", "What can you help me with?"),
    ("Business overview", "How am I doing overall? Show me the big picture."),
    ("Follow-up overview", "What about revenue and spend in particular?"),
    ("Campaigns", "Summarize my top campaigns. Which are performing best?"),
    ("Follow-up campaigns", "Which campaigns should I consider pausing or scaling?"),
    ("Funnel", "How does my conversion funnel look? Where do people drop off?"),
    ("Follow-up funnel", "What are the main drop-off points?"),
    ("Actions", "What should I do today? Any recommended actions?"),
    ("Follow-up actions", "Anything else I should look at?"),
    ("Google Ads", "Dive into Google Ads for me. How are my ads doing?"),
    ("Follow-up Ads", "Show me Google Ads performance for the last 7 days."),
    ("GA4", "How is my website performing? Give me Google Analytics or GA4 data."),
    ("Follow-up GA4", "What about sessions and conversions by device?"),
    ("Decision history", "What decisions have we applied recently? Show decision history."),
    ("Conceptual", "What is ROAS and why does it matter?"),
    ("Short reply", "Thanks, that helps."),
    ("Ambiguous ask", "Give me a quick summary of everything."),
    ("Request table", "Show me a table of campaign spend and revenue."),
    ("Final follow-up", "Based on all that, what are my top 3 priorities?"),
]

EDGE_CASES = [
    ("Empty message", ""),
    ("Whitespace only", "   \n\t  "),
]


def main():
    print("=" * 60)
    print("Copilot test: latency, tool usage, edge cases")
    print("=" * 60)
    session_id: str | None = None
    passed = 0
    failed = 0
    latencies: list[float] = []
    total_start = time.perf_counter()

    for i, (label, message) in enumerate(CONVERSATION):
        print(f"\n--- Turn {i + 1}/{len(CONVERSATION)} [{label}] ---")
        print(f"User: {message!r}")
        session_id, reply, ok, latency_ms = send(session_id, message)
        latencies.append(latency_ms)
        if not session_id and session_id is not None:
            pass
        if session_id:
            print(f"Session: {session_id[:8]}...")
        print(f"Latency: {latency_ms:.0f} ms")
        if reply:
            print("Reply:")
            safe_print(reply)
            if ok:
                print("  [OK]")
                passed += 1
            else:
                print("  [ERROR IN REPLY]")
                failed += 1
        else:
            print("  [FAIL] Empty reply.")
            failed += 1

    # Edge cases (no session continuity; expect specific behavior)
    print("\n--- Edge cases ---")
    for label, message in EDGE_CASES:
        print(f"\n[{label}] User: {message!r}")
        _, reply, _, latency_ms = send(None, message)
        latencies.append(latency_ms)
        print(f"Latency: {latency_ms:.0f} ms")
        if label == "Empty message" or label == "Whitespace only":
            if "Please type a message" in (reply or ""):
                print("  [OK] Empty/whitespace handled.")
                passed += 1
            else:
                print(f"  Reply: {reply[:200] if reply else '(empty)'}")
                failed += 1
        else:
            if reply and "Something went wrong" not in reply:
                passed += 1
            else:
                failed += 1

    total_elapsed = time.perf_counter() - total_start
    valid_latencies = [x for x in latencies if x > 0]
    avg_ms = sum(valid_latencies) / len(valid_latencies) if valid_latencies else 0
    total_turns = len(CONVERSATION) + len(EDGE_CASES)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Passed: {passed}  Failed: {failed}  Total: {total_turns}")
    print(f"Total time: {total_elapsed:.1f} s")
    if valid_latencies:
        print(f"Avg latency: {avg_ms:.0f} ms  Min: {min(valid_latencies):.0f} ms  Max: {max(valid_latencies):.0f} ms")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
