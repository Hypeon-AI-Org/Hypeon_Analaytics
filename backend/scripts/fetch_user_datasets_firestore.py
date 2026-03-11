#!/usr/bin/env python3
"""
Fetch the available BigQuery datasets for a user from Firestore.

Resolves user → organization_id from Firestore (users/{uid}.organization_id),
then reads organizations/{organization_id} and flattens the "projects" array
into a list of (bq_project, bq_dataset, bq_location, type). Same data the Copilot uses.

Usage (from repo root):
  python -m backend.scripts.fetch_user_datasets_firestore
  # default: test@hypeon.ai → org_test → datasets

  python -m backend.scripts.fetch_user_datasets_firestore --email user@example.com
  python -m backend.scripts.fetch_user_datasets_firestore --org org_test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
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

try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
except ImportError:
    print("Run: pip install firebase-admin", file=sys.stderr)
    sys.exit(1)


def _flatten_org_datasets(org_doc: dict) -> list[dict]:
    """Flatten Option B projects into list of { bq_project, bq_dataset, bq_location, type }."""
    out = []
    projects = org_doc.get("projects") or []
    if not isinstance(projects, list):
        return out
    for p in projects:
        if not isinstance(p, dict) or not p.get("bq_project"):
            continue
        bq_project = (p.get("bq_project") or "").strip()
        for d in p.get("datasets") or []:
            if not isinstance(d, dict) or not d.get("bq_dataset"):
                continue
            bq_dataset = (d.get("bq_dataset") or "").strip()
            bq_location = (d.get("bq_location") or "").strip() or "europe-north2"
            ds_type = d.get("type") or ""
            out.append({
                "bq_project": bq_project,
                "bq_dataset": bq_dataset,
                "bq_location": bq_location,
                "type": ds_type,
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch available BigQuery datasets for a user from Firestore")
    ap.add_argument("--email", default="", help="User email (resolves to org via Firestore users doc)")
    ap.add_argument("--org", default="", help="Organization ID (skip user lookup)")
    ap.add_argument("--json", action="store_true", help="Output raw JSON only")
    args = ap.parse_args()

    if not firebase_admin._apps:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and not os.path.isabs(cred_path):
            cred_path = str(ROOT / cred_path)
        project_id = (
            os.environ.get("FIREBASE_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("BQ_PROJECT")
        )
        if cred_path and os.path.isfile(cred_path):
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        else:
            if not project_id:
                print("Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT (or BQ_PROJECT) in .env", file=sys.stderr)
                return 1
            firebase_admin.initialize_app(options={"projectId": project_id})

    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "hypeon-analytics")
    db = firestore.client(database_id=database_id)

    org_id = (args.org or "").strip()
    email = (args.email or "").strip()

    if not org_id and not email:
        email = "test@hypeon.ai"

    if not org_id and email:
        uid = None
        try:
            user = auth.get_user_by_email(email)
            uid = user.uid
        except auth.UserNotFoundError:
            print(f"No Firebase Auth user for email: {email}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Firebase Auth error: {e}", file=sys.stderr)
            return 1
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            print(f"No Firestore users/{uid} document", file=sys.stderr)
            return 1
        org_id = (user_doc.to_dict() or {}).get("organization_id") or ""
        if not org_id:
            print(f"User has no organization_id in Firestore", file=sys.stderr)
            return 1

    if not org_id:
        print("Provide --email or --org", file=sys.stderr)
        return 1

    org_doc_ref = db.collection("organizations").document(org_id)
    org_doc = org_doc_ref.get()
    if not org_doc.exists:
        print(f"Organization {org_id} not found in Firestore", file=sys.stderr)
        return 1

    org_data = org_doc.to_dict() or {}
    datasets = _flatten_org_datasets(org_data)

    result = {
        "organization_id": org_id,
        "organization_name": org_data.get("name") or "",
        "datasets": datasets,
        "count": len(datasets),
    }
    if email and not args.org:
        result["email"] = email

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(f"Organization: {result['organization_name']} ({org_id})")
    print(f"Datasets: {result['count']}")
    print()
    for i, ds in enumerate(datasets, 1):
        t = f" [{ds['type']}]" if ds.get("type") else ""
        print(f"  {i}. {ds['bq_project']}.{ds['bq_dataset']}{t}  (location: {ds.get('bq_location') or 'europe-north2'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
