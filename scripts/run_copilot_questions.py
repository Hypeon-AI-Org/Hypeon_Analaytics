#!/usr/bin/env python3
"""
Run a list of Copilot questions via API (X-API-Key + X-Organization-Id) and write answers to a file.
Usage: from repo root, with backend running on 8001:
  python scripts/run_copilot_questions.py [--limit N] [--out copilot_answers.md]
  python scripts/run_copilot_questions.py --from 1 --limit 1   # run one question at a time (Q1)
  python scripts/run_copilot_questions.py --from 2 --limit 1   # then Q2, appends to file
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
    """Load API_KEY from repo root .env so it matches backend (strip CR like backend config)."""
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

API_BASE = os.environ.get("COPILOT_API_BASE", "http://localhost:8001")
API_KEY = _load_api_key()
ORG_ID = os.environ.get("COPILOT_ORG_ID", "org_test")


def ask_copilot(message: str, api_base: str | None = None, api_key: str | None = None) -> tuple[str | None, list, str | None]:
    """POST to chat/stream; return (answer_text, data_rows, error)."""
    base = (api_base or API_BASE).rstrip("/")
    url = f"{base}/api/v1/copilot/chat/stream"
    key = api_key if api_key is not None else API_KEY
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": key or "",
        "X-Organization-Id": ORG_ID,
    }
    payload = {"message": message}
    answer = None
    data = []
    err = None
    try:
        r = requests.post(url, json=payload, headers=headers, stream=True, timeout=900)
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if ev.get("phase") == "done":
                answer = ev.get("answer") or ""
                data = ev.get("data") or []
                break
            if ev.get("phase") == "error":
                err = ev.get("error") or "Unknown error"
                break
    except requests.exceptions.RequestException as e:
        err = str(e)
    return answer, data, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_index", type=int, default=1, help="Start from question index (1-based). Use with --limit 1 to run one question at a time.")
    ap.add_argument("--limit", type=int, default=0, help="Max questions to run (0 = all from --from)")
    ap.add_argument("--out", default="copilot_answers.md", help="Output markdown file")
    ap.add_argument("--api-base", default="", help="Override API base URL (e.g. http://localhost:8002)")
    ap.add_argument("--dev", action="store_true", help="Use dev key (dev-local-secret) for backend without API_KEY in .env")
    args = ap.parse_args()
    api_base = (args.api_base or os.environ.get("COPILOT_API_BASE") or "http://localhost:8001").rstrip("/")
    key = "dev-local-secret" if args.dev else API_KEY
    if not key:
        print("Set API_KEY in .env or environment", file=sys.stderr)
        return 1
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    from_index = max(1, args.from_index)
    slice_questions = QUESTIONS[(from_index - 1) :]
    if args.limit:
        slice_questions = slice_questions[: args.limit]
    if not slice_questions:
        print("No questions to run (--from/--limit out of range).", file=sys.stderr)
        return 0
    # When starting from 1, write header; when from > 1 and file exists, keep content before this run and append
    prefix_lines: list[str] = []
    if from_index == 1 or not out_path.exists():
        prefix_lines = [
            "# Copilot answers",
            "",
            f"Org: {ORG_ID} | API: {api_base}",
            "",
            "---",
            "",
        ]
    else:
        try:
            existing = out_path.read_text(encoding="utf-8")
            marker = f"\n## Q{from_index}:"
            if marker in existing:
                existing = existing[: existing.index(marker)].rstrip()
            prefix_lines = [existing + "\n\n"] if existing else []
        except Exception:
            prefix_lines = []
    lines = list(prefix_lines)
    for idx, q in enumerate(slice_questions):
        i = from_index + idx
        print(f"[{i}/{len(QUESTIONS)}] {q[:60]}...")
        start = time.time()
        answer, data, err = ask_copilot(q, api_base=api_base, api_key=key)
        elapsed = time.time() - start
        if err:
            print(f"  Error: {err[:80]}")
            lines.append(f"## Q{i}: {q}\n\n**Error:** {err}\n\n")
        else:
            print(f"  OK ({elapsed:.1f}s) | answer len={len(answer or '')} data rows={len(data)}")
            lines.append(f"## Q{i}: {q}\n\n")
            if answer:
                lines.append(answer.strip() + "\n\n")
            if data:
                lines.append(f"*Data: {len(data)} rows*\n\n")
        lines.append("---\n\n")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Saved.")
    print(f"Done. All answers in {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
