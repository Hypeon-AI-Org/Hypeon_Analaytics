"""
Firebase Auth + Firestore for user/org context.
Exposes init_firebase, verify_id_token, get_organization_id, get_role_from_token.
"""
from __future__ import annotations

from .firebase import init_firebase, verify_id_token
from .firestore_user import get_user, get_organization
from .request_auth import get_organization_id, get_role_from_token, require_any_auth

__all__ = [
    "init_firebase",
    "verify_id_token",
    "get_user",
    "get_organization",
    "get_organization_id",
    "get_role_from_token",
    "require_any_auth",
]
