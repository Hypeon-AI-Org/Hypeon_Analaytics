#!/usr/bin/env python3
"""
Create the copilot_sessions collection in Firestore with one sample document.
Run from repo root so the collection appears in Firebase Console (Build > Firestore > Data):
  PYTHONPATH=. python -m backend.scripts.seed_copilot_sessions_firestore

Uses same Firebase/Firestore config as the backend (ADC or GOOGLE_APPLICATION_CREDENTIALS).
If you use a named database, set FIRESTORE_DATABASE_ID in .env (e.g. hypeon-analytics)
and select that database in the Firebase Console dropdown to see the collection.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
for p in [REPO_ROOT / ".env", REPO_ROOT / "frontend" / ".env"]:
    try:
        from dotenv import load_dotenv
        load_dotenv(p)
    except Exception:
        pass


def main():
    try:
        from backend.app.auth.firebase import init_firebase
        from backend.app.auth.firestore_user import _get_firestore
        from backend.app.copilot.session_memory import COPLIOT_SESSIONS_COLLECTION
    except Exception as e:
        print("Import failed:", e)
        return 1

    init_firebase()
    db = _get_firestore()
    if not db:
        print("Firestore not available. Ensure Firebase is initialized:")
        print("  - Run: gcloud auth application-default login")
        print("  - Or set GOOGLE_APPLICATION_CREDENTIALS to a service account key.")
        print("  - Set FIREBASE_PROJECT_ID or BQ_PROJECT in .env if using ADC.")
        return 1

    db_id = os.environ.get("FIRESTORE_DATABASE_ID") or "(default)"
    doc_id = "seed-session-%d" % int(time.time())
    ref = db.collection(COPLIOT_SESSIONS_COLLECTION).document(doc_id)
    ref.set({
        "organization_id": "org_test",
        "title": "Seed document — copilot_sessions collection",
        "updated_at": time.time(),
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "This document was created by seed_copilot_sessions_firestore.py so the collection appears in Firebase Console."},
        ],
    })
    print("Created document: %s/%s" % (COPLIOT_SESSIONS_COLLECTION, doc_id))
    print("Database: %s" % db_id)
    print("In Firebase Console: Build > Firestore Database > Data")
    if db_id != "(default)":
        print("  Select database '%s' from the dropdown to see this collection." % db_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
