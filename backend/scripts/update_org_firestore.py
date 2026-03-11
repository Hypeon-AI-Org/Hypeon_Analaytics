#!/usr/bin/env python3
"""
Update an organization's Firestore document: set projects/datasets (e.g. add pinterest, meta_ads;
remove marts); omit project_type so all projects are treated the same.

Usage (from repo root):
  Set GOOGLE_CLOUD_PROJECT=hypeon-ai-prod (or FIREBASE_PROJECT_ID), then:
  python -m backend.scripts.update_org_firestore
  # updates org for test@hypeon.ai (org_test) with new datasets, no project_type

  python -m backend.scripts.update_org_firestore --org-id org_xyz
"""
from __future__ import annotations

import argparse
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
    from firebase_admin import credentials, firestore
except ImportError:
    print("Run: pip install firebase-admin")
    sys.exit(1)

# Target structure: no marts; add pinterest + meta_ads in hypeon-ai-prod; keep ga4 + ads in other project.
# No project_type — treat every project the same.
DEFAULT_ORG_PROJECTS = [
    {
        "bq_project": "hypeon-ai-prod",
        "datasets": [
            {"type": "pinterest", "bq_dataset": "pinterest", "bq_location": "europe-north2"},
            {"type": "meta_ads", "bq_dataset": "meta_ads", "bq_location": "europe-north2"},
        ],
    },
    {
        "bq_project": "braided-verve-459208-i6",
        "datasets": [
            {"type": "google_ads", "bq_dataset": "146568", "bq_location": "EU"},
            {"type": "ga4", "bq_dataset": "analytics_444259275", "bq_location": "europe-north2"},
        ],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Update organization Firestore doc with new datasets, no project_type")
    parser.add_argument("--org-id", default="org_test", help="Organization document ID")
    parser.add_argument("--email", default="test@hypeon.ai", help="User email to resolve org_id if needed")
    parser.add_argument("--dry-run", action="store_true", help="Print payload and exit without writing")
    args = parser.parse_args()

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
                print("Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT in .env or environment")
                return 1
            firebase_admin.initialize_app(options={"projectId": project_id})

    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "hypeon-analytics")
    db = firestore.client(database_id=database_id)

    org_id = args.org_id
    if org_id == "org_test":
        # Resolve org_id from user email
        users_ref = db.collection("users")
        snapshots = list(users_ref.where("email", "==", args.email).limit(1).stream())
        if snapshots:
            org_id = (snapshots[0].to_dict() or {}).get("organization_id") or org_id
        else:
            print("No user found for email:", args.email, "- using org_id:", org_id, file=sys.stderr)

    org_ref = db.collection("organizations").document(org_id)
    existing = org_ref.get()
    existing_data = existing.to_dict() if existing and existing.exists else {}

    # Merge: keep name and other fields, replace projects with new list (no project_type)
    new_data = {**existing_data, "projects": DEFAULT_ORG_PROJECTS}
    if args.dry_run:
        import json
        print("Would update organizations/%s with:", org_id)
        print(json.dumps({"projects": DEFAULT_ORG_PROJECTS}, indent=2))
        return 0

    org_ref.set(new_data, merge=True)
    print("Updated organizations/%s: projects set to %d entries (pinterest, meta_ads, ga4, ads; no project_type)" % (org_id, len(DEFAULT_ORG_PROJECTS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
