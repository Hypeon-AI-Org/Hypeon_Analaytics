#!/usr/bin/env python3
"""
Test Copilot chat + sessions + history (Firestore-backed) with test@hypeon.ai / test@123.
Backend must be running on port 8001. Requires VITE_FIREBASE_API_KEY in .env.

  python -m backend.scripts.test_copilot_sessions_firestore
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / "frontend" / ".env")
except Exception:
    pass

import requests

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
API_KEY = os.environ.get("VITE_FIREBASE_API_KEY") or os.environ.get("FIREBASE_API_KEY")
EMAIL = os.environ.get("TEST_USER_EMAIL", "test@hypeon.ai")
PASSWORD = os.environ.get("TEST_USER_PASSWORD", "test@123")


def get_token():
    r = requests.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + API_KEY,
        json={"email": EMAIL, "password": PASSWORD, "returnSecureToken": True},
        timeout=15,
    )
    if r.status_code != 200:
        print("Firebase sign-in failed:", r.status_code, r.text[:300])
        return None
    return r.json().get("idToken")


def main():
    print("Testing Copilot (chat, sessions, history) on", BASE)
    print("User:", EMAIL)

    if not API_KEY:
        print("ERROR: Set VITE_FIREBASE_API_KEY in .env (or FIREBASE_API_KEY)")
        return 1

    # Health
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            print("ERROR: Backend health check failed:", r.status_code)
            return 1
        print("  Backend health OK")
    except requests.RequestException as e:
        print("ERROR: Backend not reachable at", BASE, "-", e)
        return 1

    token = get_token()
    if not token:
        return 1
    print("  Firebase auth OK")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1) Send first message (new session) — use "Hi" for fast response (no LLM/BQ)
    print("\n1) POST /api/v1/copilot/chat (new session)...")
    r = requests.post(
        f"{BASE}/api/v1/copilot/chat",
        json={"message": "Hi", "client_id": 1},
        headers=headers,
        timeout=60,
    )
    if r.status_code != 200:
        print("   FAIL:", r.status_code, r.text[:400])
        return 1
    out = r.json()
    sid = out.get("session_id")
    text = (out.get("text") or out.get("answer") or "").strip()
    print("   session_id:", sid)
    print("   answer (first 200 chars):", (text[:200] + "..." if len(text) > 200 else text))

    if not sid:
        print("   FAIL: No session_id in response")
        return 1

    # 2) List sessions
    print("\n2) GET /api/v1/copilot/sessions...")
    r = requests.get(f"{BASE}/api/v1/copilot/sessions", headers=headers, timeout=10)
    if r.status_code != 200:
        print("   FAIL:", r.status_code, r.text[:300])
        return 1
    sessions = (r.json() or {}).get("sessions") or []
    print("   sessions count:", len(sessions))
    if sessions:
        print("   first session:", sessions[0].get("session_id"), sessions[0].get("title"))
    elif sid:
        print("   (0 sessions: if using Firestore, create composite index on copilot_sessions: organization_id asc, updated_at desc)")

    # 3) Get history for this session
    print("\n3) GET /api/v1/copilot/chat/history?session_id=...")
    r = requests.get(
        f"{BASE}/api/v1/copilot/chat/history",
        params={"session_id": sid},
        headers=headers,
        timeout=10,
    )
    if r.status_code != 200:
        print("   FAIL:", r.status_code, r.text[:300])
        return 1
    hist = r.json() or {}
    messages = hist.get("messages") or []
    print("   messages count:", len(messages))
    for i, m in enumerate(messages[:4]):
        print(f"     [{i}] {m.get('role')}: {(m.get('content') or '')[:80]}...")

    # 4) Send second message in same session (optional; may timeout if LLM/BQ slow)
    print("\n4) POST /api/v1/copilot/chat (same session)...")
    try:
        r = requests.post(
            f"{BASE}/api/v1/copilot/chat",
            json={"message": "Hello again", "session_id": sid, "client_id": 1},
            headers=headers,
            timeout=90,
        )
        if r.status_code == 200:
            out2 = r.json()
            sid2 = out2.get("session_id")
            print("   session_id:", sid2, "(same as before:" + str(sid2 == sid) + ")")
            # 5) Get history again
            r = requests.get(
                f"{BASE}/api/v1/copilot/chat/history",
                params={"session_id": sid},
                headers=headers,
                timeout=10,
            )
            messages2 = (r.json() or {}).get("messages") or []
            print("   History after 2nd message: messages count =", len(messages2))
        else:
            print("   Status:", r.status_code)
    except requests.RequestException as e:
        print("   (request timed out or failed:", str(e)[:80] + ")")

    if len(sessions) == 0 or len(messages) == 0:
        print("\nNote: sessions or history were empty. If using Firestore, ensure:")
        print("  - Firebase is initialized (GOOGLE_APPLICATION_CREDENTIALS or ADC) and FIRESTORE_DATABASE_ID if needed.")
        print("  - Composite index on copilot_sessions: organization_id (asc), updated_at (desc). Create when Firestore prompts.")

    print("\nDone. Chat (and auth) OK. Sessions/history depend on Firestore config.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
