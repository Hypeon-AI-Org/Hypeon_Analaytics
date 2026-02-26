#!/usr/bin/env python3
"""
Verify ANTHROPIC_API_KEY is set and valid. Loads .env from repo root, then calls Claude API once.
Run from repo root: python backend/scripts/check_anthropic_key.py
Or from backend: python scripts/check_anthropic_key.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    loaded = load_dotenv(ROOT / ".env")
    if loaded:
        print("Loaded .env from", ROOT / ".env")
except Exception as e:
    print("Could not load .env:", e)

key = os.environ.get("ANTHROPIC_API_KEY")
if not key or not key.strip():
    print("ANTHROPIC_API_KEY is not set or empty. Add it to .env (repo root).")
    sys.exit(1)

key = key.strip()
masked = key[:10] + "..." + key[-4:] if len(key) > 14 else "***"
print("ANTHROPIC_API_KEY is set:", masked)

try:
    from anthropic import Anthropic
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
        max_tokens=50,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )
    text = (resp.content[0].text if resp.content else "").strip()
    print("API call succeeded. Response:", text[:80])
    sys.exit(0)
except Exception as e:
    print("API call failed:", type(e).__name__, str(e)[:300])
    if "401" in str(e) or "invalid" in str(e).lower() or "api_key" in str(e).lower():
        print("-> This looks like an auth problem. Check the key at https://console.anthropic.com/")
    sys.exit(1)
