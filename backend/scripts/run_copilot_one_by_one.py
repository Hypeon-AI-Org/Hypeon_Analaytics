#!/usr/bin/env python3
"""POST one Copilot question at a time to the API and print each response. Run from repo root."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Windows: avoid UnicodeEncodeError when printing to console
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Load .env
_env = REPO_ROOT / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("'\"").strip()
            if k and v and k not in os.environ:
                os.environ[k] = v

QUESTIONS = [
    "Top 10 product IDs driving 50% of revenue — pareto/cumulative revenue ranking",
    "High volume vs high profit products — units sold vs revenue per order, two-axis sort",
    "New product launch performance — sessions, add-to-cart rate, revenue vs existing catalogue",
    "Products that spiked in last 14 days vs 14 days before — period-over-period delta",
    "Which two products are most often bought together? — basket analysis, co-purchase pairs",
    "True last-click ROAS vs what Google/Meta claim — the double-counting reality check",
    "Which channels actually bring new customers vs recycled buyers — is_new_customer by channel",
    "Most common channel path before first purchase — multi-touch journey mapping",
    "Days from first visit to first purchase by channel — time lag analysis",
    "Which Google campaigns to scale vs pause right now — campaign-level ROAS with threshold flags",
    "Which channel acquires customers with the highest 90-day LTV — not first order, total 90-day spend",
    "Repeat purchase rate + what did they first buy — cohort repurchase analysis",
    "Customers who used to buy every 3–4 weeks but went quiet 45–90 days ago — churn risk list",
    "Profile of the top 10% spenders — channel, first product, purchase frequency",
    "Top 5 cities by revenue vs cities with traffic but no conversions — geo funnel gap",
    "Countries adding to cart but abandoning checkout — signals friction or shipping/pricing issues",
    "Mobile vs desktop conversion rate gap — confirm the suspicion most founders have",
    "Which landing pages generate revenue, not just traffic — entry page → order attribution",
    "Where exactly do people drop off in checkout — paid vs organic — funnel step comparison",
]

def main():
    try:
        import requests
    except ImportError:
        print("pip install requests", file=sys.stderr)
        return 1
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    url = f"{base}/api/v1/copilot/chat"
    headers = {"Content-Type": "application/json", "X-Organization-Id": "default"}
    api_key = os.environ.get("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n--- Question {i}/{len(QUESTIONS)} ---")
        print(q[:80] + ("..." if len(q) > 80 else ""))
        try:
            r = requests.post(url, json={"message": q, "session_id": f"one-by-one-{i}", "client_id": 1}, headers=headers, timeout=120)
            r.raise_for_status()
            out = r.json()
            data = out.get("data") or []
            text = (out.get("text") or out.get("answer") or "")[:500]
            print(f"  Status: {r.status_code} | Data rows: {len(data)}")
            print(f"  Answer: {text}...")
        except Exception as e:
            print(f"  Error: {e}")
    print("\nDone.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
