#!/usr/bin/env python3
"""
Fetch all user data for a given email from Firebase Auth + Firestore.
Password is not stored or readable; only profile and auth metadata are returned.

Usage (from repo root):
  python -m backend.scripts.get_user_data_firestore
  # uses default test@hypeon.ai

  python -m backend.scripts.get_user_data_firestore your@email.com
"""
from __future__ import annotations

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
    print("Run: pip install firebase-admin")
    sys.exit(1)

EMAIL = (sys.argv[1] if len(sys.argv) > 1 else "test@hypeon.ai").strip()
if not EMAIL:
    print("Usage: python -m backend.scripts.get_user_data_firestore [email]")
    sys.exit(1)

# Initialize Firebase
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
            print("Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT (or BQ_PROJECT) in .env")
            sys.exit(1)
    firebase_admin.initialize_app(options={"projectId": project_id})

database_id = os.environ.get("FIRESTORE_DATABASE_ID", "hypeon-analytics")
db = firestore.client(database_id=database_id)

out = {"email": EMAIL, "firebase_auth": None, "firestore_user": None, "organization": None}

uid = None

# 1) Try Firebase Auth first (uid, email, display_name; password is never readable)
try:
    user = auth.get_user_by_email(EMAIL)
    out["firebase_auth"] = {
        "uid": user.uid,
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": user.email_verified,
        "disabled": user.disabled,
        "provider_id": user.provider_id,
    }
    uid = user.uid
except auth.UserNotFoundError:
    out["firebase_auth"] = None
    print("No Firebase Auth user for email:", EMAIL, "(trying Firestore by email)", file=sys.stderr)
except Exception as e:
    out["firebase_auth"] = {"_error": str(e)}
    print("Firebase Auth skipped:", str(e)[:120], "(trying Firestore by email)", file=sys.stderr)

# 2) Firestore users: by uid if we have it, else query by email
if uid:
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        out["firestore_user"] = doc.to_dict()
    else:
        out["firestore_user"] = None
else:
    # Fallback: query users collection by email (if email is stored in Firestore)
    users_ref = db.collection("users")
    query = users_ref.where("email", "==", EMAIL).limit(1)
    snapshots = list(query.stream())
    if snapshots:
        out["firestore_user"] = snapshots[0].to_dict()
        uid = snapshots[0].id
    else:
        out["firestore_user"] = None

# 3) Organization doc if present
org_id = (out.get("firestore_user") or {}).get("organization_id")
if org_id:
    org_doc = db.collection("organizations").document(org_id).get()
    if org_doc.exists:
        out["organization"] = org_doc.to_dict()
    else:
        out["organization"] = {"_note": "organization_id set but document not found", "organization_id": org_id}

# Print (password is never stored or returned)
print(json.dumps(out, indent=2, default=str))
print("\nNote: Password is not stored or readable; it is only in Firebase Auth (hashed).", file=sys.stderr)
