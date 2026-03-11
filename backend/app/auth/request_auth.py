"""
Resolve organization_id and role from request: Firebase token + Firestore when Bearer present, else headers/API key.
Require auth (Bearer or API key) for all protected routes including local.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from starlette.requests import Request

from .firebase import verify_id_token
from .firestore_user import get_user

# Lazy import to avoid circular dependency
def _get_api_key():
    from ..config import get_api_key
    return get_api_key()


def _is_production() -> bool:
    """True when ENV is production or prod (deploy-ready: reject dev key)."""
    env = (os.environ.get("ENV") or "").strip().lower()
    return env in ("production", "prod")


def _is_localhost_dev_key(request: Request) -> bool:
    """True when X-API-Key=dev-local-secret (local dev only)."""
    req_key = (request.headers.get("X-API-Key") or "").strip()
    return req_key == "dev-local-secret"


def _is_dev_key_allowed(request: Request) -> bool:
    """True when request uses dev-local-secret and we are not in production."""
    return _is_localhost_dev_key(request) and not _is_production()


def is_dev_key_allowed(request: Request) -> bool:
    """Public: True when X-API-Key is dev-local-secret and ENV is not production (for _has_any_auth)."""
    return _is_dev_key_allowed(request)


def require_any_auth(request: Request) -> None:
    """
    Raise 401 if request has no valid auth (X-API-Key or Bearer token).
    In production, dev-local-secret is rejected; set API_KEY and use it or Bearer.
    """
    if _is_dev_key_allowed(request):
        return
    api_key = _get_api_key()
    req_key = (request.headers.get("X-API-Key") or "").strip()
    if api_key and req_key and api_key == req_key:
        return
    if (request.headers.get("Authorization") or "").strip().startswith("Bearer "):
        return
    from fastapi import HTTPException
    raise HTTPException(
        401,
        detail={"code": "UNAUTHORIZED", "message": "Authentication required. Use Bearer token (Firebase) or X-API-Key."},
    )


def _get_firebase_context(request: Request) -> Tuple[Optional[str], Optional[dict]]:
    """
    Verify Bearer token and load user from Firestore; cache on request.state.
    Returns (uid, user_doc) or (None, None).
    """
    if hasattr(request.state, "_firebase_user"):
        return getattr(request.state, "_firebase_uid", None), getattr(request.state, "_firebase_user", None)

    request.state._firebase_uid = None
    request.state._firebase_user = None

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None, None

    token = auth[7:].strip()
    if not token:
        return None, None

    decoded = verify_id_token(token)
    if not decoded:
        return None, None

    uid = decoded.get("uid") or decoded.get("user_id") or decoded.get("sub")
    if not uid:
        import logging
        logging.getLogger(__name__).debug("Firebase token decoded but no uid/user_id; keys=%s", list(decoded.keys()))
        return None, None

    user = get_user(uid)
    request.state._firebase_uid = uid
    request.state._firebase_user = user
    return uid, user


def get_organization_id(request: Request) -> str:
    """
    When Bearer token is present and valid, return organization_id from Firestore user doc (preferred).
    When X-API-Key only, return X-Organization-Id or X-Org-Id header. No fallback; empty when no org.
    """
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.startswith("Bearer "):
        _, user = _get_firebase_context(request)
        if user and isinstance(user.get("organization_id"), str) and user["organization_id"].strip():
            return user["organization_id"].strip()
    if _is_dev_key_allowed(request):
        return (request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "").strip()
    api_key = _get_api_key()
    req_key = (request.headers.get("X-API-Key") or "").strip()
    if api_key and req_key and api_key == req_key:
        return (request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "").strip()
    return (request.headers.get("X-Organization-Id") or request.headers.get("X-Org-Id") or "").strip()


def get_user_id(request: Request) -> Optional[str]:
    """
    When Bearer token is present and valid, return Firebase uid (preferred).
    When X-API-Key only, return None.
    """
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.startswith("Bearer "):
        uid, _ = _get_firebase_context(request)
        return uid
    if _is_dev_key_allowed(request):
        return None
    api_key = _get_api_key()
    req_key = (request.headers.get("X-API-Key") or "").strip()
    if api_key and req_key and api_key == req_key:
        return None
    return None


def get_role_from_token(request: Request, get_api_key_fn=None) -> str:
    """
    When Bearer token is present and valid, return role from Firestore user doc (preferred).
    Otherwise: X-API-Key match or localhost dev key -> "admin", else "viewer".
    """
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.startswith("Bearer "):
        uid, user = _get_firebase_context(request)
        if uid and user:
            role = (user.get("role") or "analyst").strip().lower()
            if role in ("admin", "analyst", "viewer"):
                return role
            return "analyst"
        return "analyst"
    if _is_dev_key_allowed(request):
        return "admin"
    if get_api_key_fn:
        api_key = get_api_key_fn()
        req_key = (request.headers.get("X-API-Key") or "").strip()
        if api_key and req_key and api_key == req_key:
            return "admin"
    return "viewer"
