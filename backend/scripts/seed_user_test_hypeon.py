#!/usr/bin/env python3
"""
Create Firebase Auth user test@hypeon.ai (testing) and Firestore users/{uid} linked to org_test.
Org org_test has two projects: hypeon-ai-prod (hypeon_marts, hypeon_marts_ads) and braided-verve-459208-i6 (146568, analytics_444259275).
Uses FIRESTORE_DATABASE_ID from .env (e.g. hypeon-analytics).

Run from repo root: python -m backend.scripts.seed_user_test_hypeon
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
    from firebase_admin import credentials, auth, firestore
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

EMAIL = "test@hypeon.ai"
DISPLAY_NAME = "testing"
PASSWORD = "test@123"
ORG_ID = "org_test"

# Ensure org_test exists (Option B: two projects)
database_id = os.environ.get("FIRESTORE_DATABASE_ID", "hypeon-analytics")
db = firestore.client(database_id=database_id)

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
db.collection("organizations").document(ORG_ID).set(OPTION_B_ORG, merge=True)
print("Ensured organizations/%s exists (Option B, database=%s)" % (ORG_ID, database_id))

# Create or get Firebase Auth user
try:
    user = auth.get_user_by_email(EMAIL)
    print("Firebase Auth user already exists: %s (uid=%s)" % (EMAIL, user.uid))
    uid = user.uid
    # Optionally update password and display name
    auth.update_user(uid, password=PASSWORD, display_name=DISPLAY_NAME)
    print("Updated password and display_name for %s" % EMAIL)
except auth.UserNotFoundError:
    user = auth.create_user(
        email=EMAIL,
        password=PASSWORD,
        display_name=DISPLAY_NAME,
    )
    uid = user.uid
    print("Created Firebase Auth user: %s (uid=%s)" % (EMAIL, uid))

# Firestore users/{uid}
db.collection("users").document(uid).set(
    {
        "email": EMAIL,
        "displayName": DISPLAY_NAME,
        "organization_id": ORG_ID,
        "role": "admin",
    },
    merge=True,
)
print("Created or updated Firestore users/%s -> organization_id=%s" % (uid, ORG_ID))
print("Done. You can sign in with %s / %s" % (EMAIL, PASSWORD))
