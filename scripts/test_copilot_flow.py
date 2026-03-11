#!/usr/bin/env python3
"""
Test Copilot flow: (1) which datasets Copilot will use, (2) discovery + one question.
Usage (backend running on 8001, use --dev if backend has no API_KEY in env):
  python scripts/test_copilot_flow.py [--api-base http://localhost:8001] [--dev]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def _load_api_key():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip().replace("\r", "")
            if line.startswith("API_KEY=") and not line.startswith("API_KEY=#"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'").replace("\r", "")
                return v
    return (os.environ.get("API_KEY") or "").strip().replace("\r", "")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests

API_BASE = os.environ.get("COPILOT_API_BASE", "http://localhost:8001")
ORG_ID = os.environ.get("COPILOT_ORG_ID", "org_test")


def _load_firebase_api_key():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip().replace("\r", "")
            if line.startswith("VITE_FIREBASE_API_KEY=") and "=" in line:
                v = line.split("=", 1)[1].strip().strip('"').strip("'").replace("\r", "")
                return v or None
    return os.environ.get("VITE_FIREBASE_API_KEY") or None


def _firebase_sign_in(email: str, password: str) -> str | None:
    """Sign in with Firebase Auth REST API; return idToken or None."""
    api_key = _load_firebase_api_key()
    if not api_key:
        return None
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    try:
        r = requests.post(
            url,
            json={"email": email, "password": password, "returnSecureToken": True},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("idToken") or "").strip() or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default="", help="Override API base URL")
    ap.add_argument("--dev", action="store_true", help="Use dev key (dev-local-secret)")
    ap.add_argument("--email", default="", help="Firebase email (e.g. test@hypeon.ai); use with --password for Bearer auth")
    ap.add_argument("--password", default="", help="Firebase password (e.g. test@123)")
    ap.add_argument("--skip-copilot", action="store_true", help="Only test datasets endpoint, do not run a question")
    ap.add_argument("--skip-discovery", action="store_true", help="Skip BQ discovery (include_tables); only test datasets list + one Copilot question")
    args = ap.parse_args()
    base = (args.api_base or API_BASE).rstrip("/")

    headers = {}
    if args.email and args.password:
        print("Signing in with Firebase (email/password)...")
        token = _firebase_sign_in(args.email.strip(), args.password)
        if not token:
            print("Firebase sign-in failed. Check VITE_FIREBASE_API_KEY in .env and email/password.", file=sys.stderr)
            return 1
        headers["Authorization"] = f"Bearer {token}"
        print("   Signed in successfully.")
    else:
        key = "dev-local-secret" if args.dev else _load_api_key()
        if not key:
            print("Set API_KEY in .env, use --dev, or use --email and --password for Firebase auth.", file=sys.stderr)
            return 1
        headers["X-API-Key"] = key
        headers["X-Organization-Id"] = ORG_ID

    # --- 1) Which datasets will Copilot use? ---
    print("1) Testing which datasets Copilot will use...")
    r = requests.get(f"{base}/api/v1/copilot/datasets", headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    datasets = data.get("datasets") or []
    print(f"   Organization: {data.get('organization_id')}")
    print(f"   Datasets configured: {len(datasets)}")
    for i, ds in enumerate(datasets, 1):
        print(f"     {i}. {ds.get('bq_project')}.{ds.get('bq_dataset')} ({ds.get('bq_location') or 'europe-north2'})")
    if data.get("message"):
        print(f"   Message: {data['message']}")
        if not datasets:
            return 0

    # --- 2) With include_tables: run discovery (parallel BQ) ---
    if args.skip_discovery:
        print("\n2) Skipping BQ discovery (--skip-discovery).")
    else:
        print("\n2) Running BQ discovery (include_tables=true)...")
        start = time.perf_counter()
        try:
            r2 = requests.get(f"{base}/api/v1/copilot/datasets", params={"include_tables": "true"}, headers=headers, timeout=180)
            r2.raise_for_status()
            elapsed = time.perf_counter() - start
            data2 = r2.json()
            tables_count = data2.get("tables_count") or 0
            tables = data2.get("tables") or []
            print(f"   Tables found: {tables_count} (discovery took {elapsed:.1f}s)")
            for t in tables[:15]:
                print(f"     - {t.get('project')}.{t.get('dataset')}.{t.get('table_name')} ({t.get('column_count')} cols)")
            if tables_count > 15:
                print(f"     ... and {tables_count - 15} more")
            if tables_count == 0 and datasets:
                print("   WARNING: No tables returned. Check BQ permissions and dataset names.")
        except requests.exceptions.Timeout:
            print(f"   Discovery timed out after {time.perf_counter() - start:.0f}s (continuing to Copilot step)")
        except requests.exceptions.RequestException as e:
            print(f"   Discovery request failed: {e} (continuing to Copilot step)")

    if args.skip_copilot:
        print("\nDone (--skip-copilot).")
        return 0

    # --- 3) One Copilot question (understanding + fetch) ---
    print("\n3) Sending one Copilot question (understanding + BQ fetch)...")
    msg = "How many rows are in the first available table? Just give a number."
    start = time.perf_counter()
    r3 = requests.post(
        f"{base}/api/v1/copilot/chat/stream",
        json={"message": msg},
        headers={**headers, "Content-Type": "application/json"},
        stream=True,
        timeout=300,
    )
    r3.raise_for_status()
    answer = None
    for line in r3.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        try:
            ev = json.loads(line[6:])
            if ev.get("phase") == "done":
                answer = ev.get("answer") or ""
                break
            if ev.get("phase") == "error":
                print(f"   Error: {ev.get('error')}")
                return 1
        except Exception:
            continue
    elapsed = time.perf_counter() - start
    print(f"   Response in {elapsed:.1f}s")
    if answer:
        print(f"   Answer (first 300 chars): {answer[:300]}...")
    else:
        print("   No answer in stream.")
        return 1

    print("\nAll steps OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
