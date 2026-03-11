"""
Firebase Admin SDK: initialize app and verify ID tokens.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Optional

logger = logging.getLogger(__name__)

FIREBASE_VERIFY_TIMEOUT_SEC = 50
# Single worker so prefetch and all verifications run in the same thread and share the auth library's HTTP cache.
_verify_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="firebase_verify")

_firebase_app = None


def init_firebase() -> None:
    """Initialize Firebase Admin SDK. Safe to call multiple times; uses default credentials or GOOGLE_APPLICATION_CREDENTIALS."""
    global _firebase_app
    if _firebase_app is not None:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            _firebase_app = firebase_admin.get_app()
            logger.info("Firebase already initialized")
            return

        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        project_id = (
            os.environ.get("FIREBASE_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("BQ_PROJECT", "")
        )
        project_id = (project_id or "").strip() or None
        if cred_path and os.path.isfile(cred_path):
            _firebase_app = firebase_admin.initialize_app(credentials.Certificate(cred_path))
        else:
            # gcloud Application Default Credentials (project required for Firestore)
            opts = {"projectId": project_id} if project_id else None
            _firebase_app = firebase_admin.initialize_app(options=opts)
        logger.info("Firebase Admin initialized")
    except Exception as e:
        logger.warning("Firebase Admin init skipped or failed: %s", e)
        _firebase_app = False  # mark as attempted


# Dummy JWT (valid structure, invalid sig) used to trigger SDK to fetch and cache public keys at startup.
_PREWARM_TOKEN = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InByZXdhcm0ifQ."
    "eyJzdWIiOiJwcmV3YXJtIn0.x"
)

PREFETCH_TIMEOUT_SEC = 35


def prefetch_firebase_public_keys() -> None:
    """
    Pre-fetch Firebase Auth public keys so the first real verify_id_token does not block on a slow
    HTTPS request to Google (which can take 20+ seconds and cause request timeouts).
    Call once after init_firebase() during app startup.
    """
    if not is_initialized():
        return
    try:
        future = _verify_executor.submit(_verify_id_token_impl, _PREWARM_TOKEN)
        future.result(timeout=PREFETCH_TIMEOUT_SEC)
    except FuturesTimeoutError:
        logger.warning(
            "Firebase public key prefetch timed out after %ss; first token verification may be slow.",
            PREFETCH_TIMEOUT_SEC,
        )
    except Exception:
        # Expected: verification fails (invalid token). Keys are still cached.
        logger.debug("Firebase public key prefetch completed (verification failed as expected)")
    else:
        logger.debug("Firebase public key prefetch completed")


def is_initialized() -> bool:
    return _firebase_app is not None and _firebase_app is not False


def _verify_id_token_impl(token: str) -> Optional[dict[str, Any]]:
    from firebase_admin import auth
    return auth.verify_id_token(token)


def verify_id_token(token: str) -> Optional[dict[str, Any]]:
    """
    Verify Firebase ID token and return decoded claims (uid, email, etc.).
    Uses timeout so auth does not hang on slow network.
    Returns None if Firebase not initialized, token invalid, or expired.
    """
    if not is_initialized():
        return None
    try:
        future = _verify_executor.submit(_verify_id_token_impl, token)
        return future.result(timeout=FIREBASE_VERIFY_TIMEOUT_SEC)
    except FuturesTimeoutError:
        logger.warning("Firebase verify_id_token timed out after %ss", FIREBASE_VERIFY_TIMEOUT_SEC)
        return None
    except Exception as e:
        logger.debug("Firebase token verification failed: %s", e)
        return None
