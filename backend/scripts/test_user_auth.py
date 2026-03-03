#!/usr/bin/env python3
"""
Test Firebase user auth: sign in with email/password, call backend with Bearer token.
Requires: Firestore + dummy users (run seed_firestore_dummy_users first), or a user
created in Firebase Console. Backend must be running on port 8000.

Set in .env (or env): VITE_FIREBASE_API_KEY (Firebase Web API key).
Optional: TEST_USER_EMAIL, TEST_USER_PASSWORD (default: test@hypeon.example.com / TestPass123!)

Run from repo root: python -m backend.scripts.test_user_auth
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
    load_dotenv(ROOT / "frontend" / ".env")
except Exception:
    pass

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("VITE_FIREBASE_API_KEY") or os.environ.get("FIREBASE_API_KEY")
EMAIL = os.environ.get("TEST_USER_EMAIL", "test@hypeon.example.com")
PASSWORD = os.environ.get("TEST_USER_PASSWORD", "TestPass123!")

FIREBASE_SIGN_IN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"


def get_firebase_id_token(api_key: str, email: str, password: str) -> str | None:
    """Sign in with email/password via Firebase Auth REST API; return idToken."""
    r = requests.post(
        f"{FIREBASE_SIGN_IN_URL}?key={api_key}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("idToken")


def main():
    print("Testing Firebase user auth (Bearer token)...")
    if not API_KEY:
        print("  SKIP: Set VITE_FIREBASE_API_KEY in .env (Firebase Web API key).")
        sys.exit(0)

    token = get_firebase_id_token(API_KEY, EMAIL, PASSWORD)
    if not token:
        print("  FAIL: Firebase sign-in failed (user may not exist).")
        print("  1. Create Firestore: Firebase Console > Build > Firestore Database > Create database (Native).")
        print("  2. Run: python -m backend.scripts.seed_firestore_dummy_users")
        print("  Or create a user in Firebase Console (Authentication > Add user) and set TEST_USER_EMAIL / TEST_USER_PASSWORD.")
        sys.exit(1)
    print("  Firebase sign-in OK (got idToken)")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = requests.get(f"{BASE}/api/v1/dashboard/ping", headers=headers, timeout=5)
    except requests.RequestException as e:
        print(f"  FAIL: Backend request failed: {e}")
        print("        Start backend: cd backend && uvicorn app.main:app --port 8000")
        sys.exit(1)

    if r.status_code != 200:
        print(f"  FAIL: GET /api/v1/dashboard/ping -> {r.status_code}")
        print("        Response:", r.text[:500])
        sys.exit(1)
    print("  GET /api/v1/dashboard/ping with Bearer token -> 200 OK")
    print("  User auth flow OK.")


if __name__ == "__main__":
    main()
