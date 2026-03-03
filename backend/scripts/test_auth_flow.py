#!/usr/bin/env python3
"""
Quick test that backend auth and Firebase wiring work.
- Without Firebase credentials: header-based auth (X-Organization-Id, X-API-Key) still works.
- With backend running: GET /health and GET /api/v1/dashboard/ping with headers.

Run from repo root with backend running on port 8000 (or set BASE_URL):
  python -m backend.scripts.test_auth_flow
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
HEADERS = {"X-Organization-Id": "default", "Content-Type": "application/json"}
if os.environ.get("API_KEY"):
    HEADERS["X-API-Key"] = os.environ.get("API_KEY")

def main():
    print("Testing auth flow (header-based fallback)...")
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        ok = r.status_code == 200
        print(f"  GET /health -> {r.status_code}" + (" OK" if ok else " FAIL"))
        if not ok:
            sys.exit(1)
    except requests.RequestException as e:
        print(f"  GET /health failed: {e}")
        print("  Start the backend (e.g. uvicorn app.main:app --port 8000) and retry.")
        sys.exit(1)

    try:
        r = requests.get(f"{BASE}/api/v1/dashboard/ping", headers=HEADERS, timeout=5)
        ok = r.status_code == 200
        print(f"  GET /api/v1/dashboard/ping (X-Organization-Id=default) -> {r.status_code}" + (" OK" if ok else " FAIL"))
        if not ok:
            sys.exit(1)
        data = r.json() if r.content else {}
        if data.get("ok"):
            print("  Backend and auth wiring OK.")
        else:
            print("  Unexpected response:", data)
    except requests.RequestException as e:
        print(f"  GET /api/v1/dashboard/ping failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
