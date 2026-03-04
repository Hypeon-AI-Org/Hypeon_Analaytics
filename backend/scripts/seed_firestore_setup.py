#!/usr/bin/env python3
"""
One-time Firestore setup: create organizations/default and organizations/org_test (Option B).
Uses FIRESTORE_DATABASE_ID from .env (e.g. hypeon-analytics). No user docs; add those after creating Auth users.

Run from repo root:
  python -m backend.scripts.seed_firestore_setup
"""
from __future__ import annotations

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
            print("Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT in .env")
            sys.exit(1)
        firebase_admin.initialize_app(options={"projectId": project_id})

database_id = os.environ.get("FIRESTORE_DATABASE_ID", "hypeon-analytics")
db = firestore.client(database_id=database_id)

# 1) organizations/default (simple, for GET /api/v1/me and env-based BQ)
db.collection("organizations").document("default").set(
    {
        "name": "Default Org",
        "ad_channels": [
            {"client_id": 1, "description": "Primary client dataset"},
        ],
    },
    merge=True,
)
print("Created or updated organizations/default")

# 2) organizations/org_test (Option B: two projects, unique dataset locations)
OPTION_B_ORG = {
    "name": "Testing (test@hypeon.ai)",
    "projects": [
        {
            "bq_project": "hypeon-ai-prod",
            "project_type": "organization",
            "datasets": [
                {"bq_dataset": "hypeon_marts", "bq_location": "europe-north2"},
                {"bq_dataset": "hypeon_marts_ads", "bq_location": "EU"},
            ],
        },
        {
            "bq_project": "braided-verve-459208-i6",
            "project_type": "individual",
            "datasets": [
                {"bq_dataset": "146568", "bq_location": "EU"},
                {"bq_dataset": "analytics_444259275", "bq_location": "europe-north2"},
            ],
        },
    ],
}
db.collection("organizations").document("org_test").set(OPTION_B_ORG, merge=True)
print("Created or updated organizations/org_test (Option B)")

print("Firestore setup done (database=%s)." % database_id)
print("Next: create a user in Firebase Authentication, then run:")
print("  python -m backend.scripts.seed_firestore_example")
print("and enter the user UID to create users/{uid} with organization_id=default (or org_test).")
