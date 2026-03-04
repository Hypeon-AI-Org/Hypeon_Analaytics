#!/usr/bin/env python3
"""
Delete all users from Firebase Authentication.
Uses Firebase Admin SDK with gcloud ADC or GOOGLE_APPLICATION_CREDENTIALS.

Run from repo root:
  gcloud auth application-default login
  gcloud config set project YOUR_FIREBASE_PROJECT_ID
  python -m backend.scripts.delete_firebase_users
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
    from firebase_admin import credentials, auth
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
        print("Using credentials from GOOGLE_APPLICATION_CREDENTIALS")
    else:
        if not project_id:
            print(
                "Set FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT in .env "
                "(or run: gcloud config set project YOUR_PROJECT_ID)"
            )
            sys.exit(1)
        firebase_admin.initialize_app(options={"projectId": project_id})
        print("Using gcloud Application Default Credentials (project=%s)" % project_id)

def main():
    deleted = 0
    page = auth.list_users()
    while page:
        for user in page.users:
            try:
                auth.delete_user(user.uid)
                deleted += 1
                print("Deleted: %s (uid=%s)" % (user.email or "(no email)", user.uid))
            except Exception as e:
                print("Failed to delete %s: %s" % (user.uid, e))
        page = page.get_next_page()
    if deleted == 0:
        print("No users found in Firebase Authentication.")
    else:
        print("Deleted %d user(s)." % deleted)

if __name__ == "__main__":
    main()
