#!/usr/bin/env python3
"""Check Firebase and Firestore connectivity. Run from repo root: python -m backend.scripts.check_firebase_firestore"""
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

def main():
    print("Checking Firebase & Firestore...")
    failed = False
    # 1) Firebase Admin init
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        print("  [FAIL] firebase-admin not installed. Run: pip install firebase-admin")
        return 1
    if not firebase_admin._apps:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and not os.path.isabs(cred_path):
            cred_path = str(ROOT / cred_path)
        project_id = (
            os.environ.get("FIREBASE_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("BQ_PROJECT")
        )
        try:
            if cred_path and os.path.isfile(cred_path):
                firebase_admin.initialize_app(credentials.Certificate(cred_path))
                print("  [OK] Firebase initialized (GOOGLE_APPLICATION_CREDENTIALS)")
            elif project_id:
                firebase_admin.initialize_app(options={"projectId": project_id})
                print("  [OK] Firebase initialized (gcloud ADC, project=%s)" % project_id)
            else:
                print("  [FAIL] Set FIREBASE_PROJECT_ID or GOOGLE_APPLICATION_CREDENTIALS")
                return 1
        except Exception as e:
            print("  [FAIL] Firebase init: %s" % e)
            return 1
    else:
        print("  [OK] Firebase already initialized")
    # 2) Firestore read (try default db, then FIRESTORE_DATABASE_ID or hypeon-analytics)
    from firebase_admin import firestore
    db_id = os.environ.get("FIRESTORE_DATABASE_ID", "hypeon-analytics")
    for try_id in [db_id, "(default)"]:
        try:
            db = firestore.client(database_id=try_id)
            colls = db.collections()
            count = 0
            for _ in colls:
                count += 1
                if count >= 10:
                    break
            print("  [OK] Firestore responding (database=%s, collections reachable)" % try_id)
            failed = False
            break
        except Exception as e:
            err = str(e)
            if "404" in err and "does not exist" in err and try_id == db_id:
                # try (default) next
                continue
            if "404" in err and "does not exist" in err:
                print("  [FAIL] Firestore: database not created for this project.")
                print("         Create it at: https://console.firebase.google.com/ -> Project -> Firestore Database -> Create database")
            else:
                print("  [FAIL] Firestore: %s" % e)
            failed = True
    else:
        failed = True
    # 3) Firebase Auth (list_users)
    try:
        from firebase_admin import auth
        page = auth.list_users(max_results=1)
        print("  [OK] Firebase Auth responding (list_users succeeded)")
    except Exception as e:
        print("  [WARN] Firebase Auth list_users: %s" % e)
    if failed:
        print("Done. Firebase is OK; Firestore needs to be created.")
        return 1
    print("Done. Firebase and Firestore are working.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
