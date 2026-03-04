#!/usr/bin/env python3
"""
Read copilot_sessions from Firestore (proof that chats are in the DB).
Uses same Firebase/Firestore config as the backend. Run from repo root:
  PYTHONPATH=. python -m backend.scripts.read_copilot_sessions_from_firestore
"""
from __future__ import annotations

import os
import sys
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
        print("Firestore not available (Firebase not initialized or credentials missing).")
        return 1

    print("Collection: %s" % COPLIOT_SESSIONS_COLLECTION)
    print("-" * 60)
    docs = list(db.collection(COPLIOT_SESSIONS_COLLECTION).limit(50).stream())
    if not docs:
        print("No documents found.")
        return 0

    for doc in docs:
        d = doc.to_dict() or {}
        msgs = d.get("messages") or []
        print("session_id: %s" % doc.id)
        print("  organization_id: %s" % d.get("organization_id"))
        print("  title: %s" % (d.get("title") or "—"))
        print("  updated_at: %s" % d.get("updated_at"))
        print("  messages: %d" % len(msgs))
        for i, m in enumerate(msgs[:8]):
            if isinstance(m, dict):
                print("    [%d] %s: %s" % (i, m.get("role", ""), (m.get("content") or "")[:70]))
        if len(msgs) > 8:
            print("    ... and %d more" % (len(msgs) - 8))
        print()
    print("Total documents: %d" % len(docs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
