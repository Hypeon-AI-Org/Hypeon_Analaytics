#!/usr/bin/env python3
"""
Run a list of Copilot questions via the API (X-API-Key + X-Organization-Id).
Saves answers to a markdown file. Use org_test for test@hypeon.ai.

Usage (backend running on 8001):
  From repo root: python -m backend.scripts.run_copilot_questions [--max N]
  Or: cd backend && python scripts/run_copilot_questions.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass
env_file = ROOT / ".env"
if env_file.exists() and not os.environ.get("API_KEY"):
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("API_KEY=") and "=" in line:
            os.environ["API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

import requests

BASE_URL = os.environ.get("COPILOT_SCRIPT_BASE_URL", "http://localhost:8001")
API_KEY = os.environ.get("API_KEY", "")
ORG_ID = os.environ.get("COPILOT_SCRIPT_ORG_ID", "org_test")
TIMEOUT_PER_QUESTION = int(os.environ.get("COPILOT_SCRIPT_TIMEOUT", "180"))

QUESTIONS = [
    ("Top 10 product IDs driving 50% of revenue — pareto/cumulative revenue ranking", "product_pareto"),
    ("High volume vs high profit products — units sold vs revenue per order, two-axis sort", "volume_vs_profit"),
    ("New product launch performance — sessions, add-to-cart rate, revenue vs existing catalogue", "new_product_launch"),
    ("Products that spiked in last 14 days vs 14 days before — period-over-period delta", "product_spike_14d"),
    ("Which two products are most often bought together? — basket analysis, co-purchase pairs", "basket_co_purchase"),
    ("True last-click ROAS vs what Google/Meta claim — the double-counting reality check", "true_roas"),
    ("Which channels actually bring new customers vs recycled buyers — is_new_customer by channel", "new_vs_recycled"),
    ("Most common channel path before first purchase — multi-touch journey mapping", "channel_path"),
    ("Days from first visit to first purchase by channel — time lag analysis", "days_to_purchase"),
    ("Which Google campaigns to scale vs pause right now — campaign-level ROAS with threshold flags", "campaign_scale_pause"),
    ("Which channel acquires customers with the highest 90-day LTV — not first order, total 90-day spend", "ltv_90d_by_channel"),
    ("Repeat purchase rate + what did they first buy — cohort repurchase analysis", "repeat_purchase_cohort"),
    ("Customers who used to buy every 3–4 weeks but went quiet 45–90 days ago — churn risk list", "churn_risk"),
    ("Profile of the top 10% spenders — channel, first product, purchase frequency", "top_10_percent_spenders"),
    ("Top 5 cities by revenue vs cities with traffic but no conversions — geo funnel gap", "geo_funnel_gap"),
    ("Countries adding to cart but abandoning checkout — signals friction or shipping/pricing issues", "checkout_abandon_countries"),
    ("Mobile vs desktop conversion rate gap — confirm the suspicion most founders have", "mobile_vs_desktop_cvr"),
    ("Which landing pages generate revenue, not just traffic — entry page → order attribution", "landing_revenue"),
    ("Where exactly do people drop off in checkout — paid vs organic — funnel step comparison", "checkout_dropoff"),
]


def run_one(session: requests.Session, question: str, session_id: str | None = None) -> tuple[str, list, str | None]:
    url = f"{BASE_URL}/api/v1/copilot/chat"
    headers = {
        "X-API-Key": API_KEY,
        "X-Organization-Id": ORG_ID,
        "Content-Type": "application/json",
    }
    body = {"message": question, "session_id": session_id, "client_id": 1}
    try:
        r = session.post(url, json=body, headers=headers, timeout=TIMEOUT_PER_QUESTION)
        r.raise_for_status()
        data = r.json()
        answer = (data.get("answer") or data.get("text") or "").strip()
        data_rows = data.get("data") or []
        return answer, data_rows, None
    except requests.exceptions.Timeout:
        return "", [], "Timeout"
    except requests.exceptions.RequestException as e:
        return "", [], str(e)
    except Exception as e:
        return "", [], str(e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=0, help="Max number of questions to run (0 = all)")
    args = parser.parse_args()
    if not API_KEY.strip():
        print("Set API_KEY in .env or environment (same as backend).", file=sys.stderr)
        return 1
    out_path = ROOT / "docs" / "ai-tasks" / "copilot_answers.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    questions = QUESTIONS[: args.max] if args.max else QUESTIONS
    session = requests.Session()
    lines = ["# Copilot Q&A (script run)\n", f"Org: {ORG_ID}\n", ""]
    errors = []
    for i, (q, slug) in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {slug}...", flush=True)
        start = time.time()
        answer, data_rows, err = run_one(session, q)
        elapsed = time.time() - start
        if err:
            errors.append((q, err))
            lines.append(f"## {slug}\n**Q:** {q}\n**Error:** {err}\n\n")
        else:
            lines.append(f"## {slug}\n**Q:** {q}\n\n**A:**\n{answer or '(no text)'}\n\n")
            if data_rows:
                lines.append(f"*Data rows: {len(data_rows)}*\n\n")
        print(f"  {elapsed:.1f}s" + (f" — {err}" if err else ""), flush=True)
        time.sleep(0.5)

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out_path}")
    if errors:
        print(f"Errors: {len(errors)}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
