#!/usr/bin/env python3
"""
Seed Firestore with organizations/default and dummy test users (Auth + Firestore docs).
Creates Firebase Auth users and their users/{uid} documents so you can log in and test.

Dev: use gcloud auth (no key file required):
  gcloud auth application-default login
  gcloud config set project YOUR_FIREBASE_PROJECT_ID
  python -m backend.scripts.seed_firestore_dummy_users

Or set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON path.
Run from repo root: python -m backend.scripts.seed_firestore_dummy_users
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
    project_id = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("BQ_PROJECT")
    if cred_path and os.path.isfile(cred_path):
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
        print("Using credentials from GOOGLE_APPLICATION_CREDENTIALS")
    else:
        # Use gcloud Application Default Credentials (gcloud auth application-default login)
        if not project_id:
            print("Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT in .env (or run: gcloud config set project YOUR_PROJECT_ID)")
            sys.exit(1)
        firebase_admin.initialize_app(options={"projectId": project_id})
        print("Using gcloud Application Default Credentials (project=%s)" % project_id)

db = firestore.client(database_id="(default)")
firestore_ok = False
try:
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
    firestore_ok = True
except Exception as e:
    if "does not exist" in str(e) or "NotFound" in type(e).__name__:
        pid = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("BQ_PROJECT", "")
        print("Firestore not reachable for this project (will create Auth users only).")
        print("  Ensure the database is in project:", pid or "(set FIREBASE_PROJECT_ID in .env)")
    else:
        raise

DUMMY_USERS = [
    {"email": "test@hypeon.example.com", "password": "TestPass123!", "role": "admin"},
    {"email": "analyst@hypeon.example.com", "password": "TestPass123!", "role": "analyst"},
]

for u in DUMMY_USERS:
    email = u["email"]
    password = u["password"]
    role = u["role"]
    try:
        existing = auth.get_user_by_email(email)
        uid = existing.uid
        print(f"Auth user already exists: {email} (uid={uid})")
    except auth.UserNotFoundError:
        try:
            user_record = auth.create_user(email=email, password=password, display_name=email.split("@")[0])
            uid = user_record.uid
            print(f"Created Auth user: {email} (uid={uid})")
        except Exception as e:
            print(f"Failed to create Auth user {email}: {e}")
            continue
    except Exception as e:
        print(f"Error looking up {email}: {e}")
        continue

    if firestore_ok:
        db.collection("users").document(uid).set(
            {
                "email": email,
                "displayName": email.split("@")[0],
                "organization_id": "default",
                "role": role,
            },
            merge=True,
        )
        print(f"  -> Firestore users/{uid} (organization_id=default, role={role})")
    else:
        print(f"  -> uid={uid} (add users/{uid} in Firestore with organization_id=default, role={role})")

print("\nDone. You can log in with:")
for u in DUMMY_USERS:
    print(f"  {u['email']} / {u['password']} (role={u['role']})")
if not firestore_ok:
    print("\nBackend will use X-Organization-Id header until users/{uid} exist in Firestore.")
