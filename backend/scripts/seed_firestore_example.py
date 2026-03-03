#!/usr/bin/env python3
"""
Seed Firestore with an example organization and optionally a user document.
Requires GOOGLE_APPLICATION_CREDENTIALS (or gcloud auth) and a Firebase project with Firestore enabled.

Create a user in Firebase Console (Authentication > Users > Add user) first, then run:
  From repo root: python -m backend.scripts.seed_firestore_example
  Or from backend: python scripts/seed_firestore_example.py

You will be prompted for the Firebase Auth UID to create the users/{uid} document.
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
except Exception:
    pass

# Initialize Firebase (same as app)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.isfile(cred_path):
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        else:
            firebase_admin.initialize_app()
except Exception as e:
    print("Firebase init failed:", e)
    print("Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path.")
    sys.exit(1)

db = firestore.client()

# Create or update organizations/default
org_ref = db.collection("organizations").document("default")
org_ref.set(
    {
        "name": "Default Org",
        "ad_channels": [
            {"client_id": 1, "description": "Primary client dataset"},
        ],
    },
    merge=True,
)
print("Created or updated organizations/default")

# Optionally create users/{uid}
uid = input("Enter Firebase Auth UID to create users doc (or press Enter to skip): ").strip()
if uid:
    email = input("Email for this user (optional): ").strip()
    role = input("Role (admin/analyst/viewer) [analyst]: ").strip() or "analyst"
    db.collection("users").document(uid).set(
        {
            "email": email or "",
            "displayName": email.split("@")[0] if email else "",
            "organization_id": "default",
            "role": role if role in ("admin", "analyst", "viewer") else "analyst",
        },
        merge=True,
    )
    print(f"Created or updated users/{uid}")
else:
    print("Skipped user document. Create users/{uid} manually in Firestore with organization_id and role.")
