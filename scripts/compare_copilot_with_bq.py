#!/usr/bin/env python3
"""
Compare Copilot answers with direct BigQuery results.
Uses Application Default Credentials (run: gcloud auth application-default login).

Usage (from repo root):
  python scripts/compare_copilot_with_bq.py
  python scripts/compare_copilot_with_bq.py --copilot-file docs/ai-tasks/copilot_answers.md --out docs/ai-tasks/copilot_validation_report.md

Reads copilot_answers.md, extracts key metrics, runs equivalent BQ queries,
and writes a comparison report.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPILOT_FILE = ROOT / "docs" / "ai-tasks" / "copilot_answers.md"
OUT_FILE = ROOT / "docs" / "ai-tasks" / "copilot_validation_report.md"

# Projects/datasets used by org_test (from Copilot context)
BQ_PROJECT_PINTEREST = "hypeon-ai-prod"
BQ_DATASET_PINTEREST = "pinterest"
BQ_TABLE_PINTEREST = "metrics_2025_01_01_to_2026_03_08"
BQ_PROJECT_META = "hypeon-ai-prod"
BQ_DATASET_META = "meta_ads"
BQ_TABLE_CAMPAIGNS = "campaigns"
BQ_PROJECT_GA4 = "braided-verve-459208-i6"
BQ_DATASET_GA4 = "analytics_444259275"


def ensure_gcloud_auth() -> bool:
    """Check that Application Default Credentials are available. Return True if OK."""
    try:
        import google.auth
        credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/bigquery.readonly"])
        return credentials is not None
    except Exception:
        return False


def parse_copilot_answers(path: Path) -> dict:
    """Parse copilot_answers.md and extract key metrics per question. Returns dict of Qn -> {key: value}."""
    text = path.read_text(encoding="utf-8")
    # Split by ## Q1:, ## Q2:, ... and keep question number
    parts = re.split(r"\n## Q(\d+):", text)
    out = {}
    for i in range(1, len(parts), 2):
        if i + 1 > len(parts):
            break
        qnum = int(parts[i])
        content = parts[i + 1]
        metrics = {}
        # Q1: total revenue ($22,754.37) and top-10 revenue ($10,811.42)
        m = re.search(r"representing [\d.]+% of total revenue\*\* \([\$]?([\d,]+\.?\d*)\)", content)
        if m:
            metrics["total_revenue"] = float(m.group(1).replace(",", ""))
        m = re.search(r"(\d+) campaigns show perfect alignment", content)
        if m:
            metrics["campaign_count"] = int(m.group(1))
        m = re.search(r"Total campaigns analyzed \| (\d+)", content)
        if m:
            metrics["campaign_count"] = int(m.group(1))
        # Q3: sessions, add-to-cart rate
        m = re.search(r"generated \*\*([\d,]+) sessions\*\*", content)
        if m:
            metrics["sessions"] = m.group(1).replace(",", "")
        m = re.search(r"(\d+\.?\d*)% add-to-cart rate", content, re.IGNORECASE)
        if m:
            metrics["add_to_cart_rate_pct"] = m.group(1)
        m = re.search(r"\*\*\$([\d,]+\.?\d*) in total revenue\*\*", content)
        if m:
            metrics["total_revenue_usd"] = m.group(1).replace(",", "")
        out[f"Q{qnum}"] = metrics
    return out


def run_bq_query(project: str, query: str, location: str | None = None) -> list[dict] | None:
    """Run a read-only BQ query; return list of row dicts or None on error."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project, location=location or "europe-north2")
        job = client.query(query)
        rows = list(job.result())
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"BQ error: {e}", file=sys.stderr)
        return None


def run_checks(copilot_metrics: dict) -> list[dict]:
    """Run BigQuery checks and return list of {question, check_name, expected, actual, match}."""
    results = []
    # --- Q6: Campaign count (Meta + Pinterest campaigns) ---
    q6_expected = copilot_metrics.get("Q6", {}).get("campaign_count")
    if q6_expected is not None:
        # Meta campaigns count
        meta_sql = f"""
        SELECT COUNT(*) AS cnt FROM `{BQ_PROJECT_META}.{BQ_DATASET_META}.{BQ_TABLE_CAMPAIGNS}`
        """
        meta_rows = run_bq_query(BQ_PROJECT_META, meta_sql)
        meta_cnt = int(meta_rows[0]["cnt"]) if meta_rows and len(meta_rows) > 0 else None
        # Pinterest: one row per campaign name or date/campaign combo - we approximate by distinct campaigns
        pin_cnt = None
        try:
            pin_rows = run_bq_query(BQ_PROJECT_PINTEREST, f"SELECT COUNT(DISTINCT Campaign_name) AS cnt FROM `{BQ_PROJECT_PINTEREST}.{BQ_DATASET_PINTEREST}.{BQ_TABLE_PINTEREST}`")
            if pin_rows and pin_rows[0].get("cnt") is not None:
                pin_cnt = int(pin_rows[0]["cnt"])
        except Exception:
            pass
        actual = (meta_cnt or 0) + (pin_cnt or 0) if (meta_cnt is not None or pin_cnt is not None) else None
        if actual is not None:
            results.append({
                "question": "Q6",
                "check": "campaign_count",
                "expected": q6_expected,
                "actual": actual,
                "match": actual == q6_expected,
                "detail": f"Meta={meta_cnt} Pinterest={pin_cnt}",
            })
        elif meta_cnt is not None:
            results.append({
                "question": "Q6",
                "check": "campaign_count_meta_only",
                "expected": q6_expected,
                "actual": meta_cnt,
                "match": meta_cnt == q6_expected,
                "detail": "Meta only (Pinterest schema may differ)",
            })

    # --- Q1-style: Total revenue from Copilot ($22,754.37). Compare to Pinterest order value if same source. ---
    q1_metrics = copilot_metrics.get("Q1") or {}
    q1_total = q1_metrics.get("total_revenue")
    if q1_total is not None:
        pinterest_sum_sql = f"""
        SELECT SUM(Total_order_value_Checkout) AS total
        FROM `{BQ_PROJECT_PINTEREST}.{BQ_DATASET_PINTEREST}.{BQ_TABLE_PINTEREST}`
        """
        sum_rows = run_bq_query(BQ_PROJECT_PINTEREST, pinterest_sum_sql)
        if sum_rows and sum_rows[0].get("total") is not None:
            bq_total = float(sum_rows[0]["total"])
            results.append({
                "question": "Q1 (Pinterest order value)",
                "check": "total_revenue_pinterest",
                "expected": round(q1_total, 2),
                "actual": round(bq_total, 2),
                "match": abs(bq_total - q1_total) < 1.0,
                "detail": "Pinterest Total_order_value_Checkout sum",
            })

    # --- Q3: Sessions / revenue (GA4 would be needed; skip if no GA4 table list) ---
    return results


def main():
    ap = argparse.ArgumentParser(description="Compare Copilot answers with BigQuery results")
    ap.add_argument("--copilot-file", type=Path, default=COPILOT_FILE, help="Path to copilot_answers.md")
    ap.add_argument("--out", type=Path, default=OUT_FILE, help="Output report path")
    ap.add_argument("--skip-auth-check", action="store_true", help="Skip gcloud auth check (e.g. running in CI)")
    args = ap.parse_args()

    if not args.skip_auth_check and not ensure_gcloud_auth():
        print(
            "BigQuery credentials not found. Run:\n  gcloud auth application-default login\n",
            file=sys.stderr,
        )
        return 1

    if not args.copilot_file.is_file():
        print(f"Copilot file not found: {args.copilot_file}", file=sys.stderr)
        return 1

    copilot_metrics = parse_copilot_answers(args.copilot_file)
    checks = run_checks(copilot_metrics)

    lines = [
        "# Copilot vs BigQuery validation",
        "",
        f"Source: `{args.copilot_file.name}`",
        "",
        "## Extracted Copilot metrics (sample)",
        "",
    ]
    for q, m in list(copilot_metrics.items())[:5]:
        if m:
            lines.append(f"- **{q}**: {m}")
    lines.extend(["", "## Comparison results", ""])
    if not checks:
        lines.append("No checks run (missing expected values or BQ schema). Add queries in `scripts/compare_copilot_with_bq.py`.")
    else:
        for r in checks:
            status = "✓ match" if r["match"] else "✗ mismatch"
            lines.append(f"- **{r['question']}** ({r['check']}): expected `{r['expected']}`, actual `{r['actual']}` — {status}")
            if r.get("detail"):
                lines.append(f"  - {r['detail']}")
        lines.append("")
        matched = sum(1 for r in checks if r["match"])
        lines.append(f"Summary: {matched}/{len(checks)} checks matched.")
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0 if (not checks or all(r["match"] for r in checks)) else 1


if __name__ == "__main__":
    sys.exit(main())
