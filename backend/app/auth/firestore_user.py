"""
Firestore reads: users/{uid}, organizations/{organization_id}.
Used to resolve organization_id and role from authenticated user.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_firestore():
    """Return Firestore client if Firebase is initialized."""
    try:
        from .firebase import is_initialized
        if not is_initialized():
            return None
        from firebase_admin import firestore
        return firestore.client()
    except Exception as e:
        logger.debug("Firestore client unavailable: %s", e)
        return None


def get_user(uid: str) -> Optional[dict[str, Any]]:
    """
    Read users/{uid} from Firestore.
    Expected fields: email, displayName, organization_id, role (optional).
    """
    db = _get_firestore()
    if not db:
        return None
    try:
        doc = db.collection("users").document(uid).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.warning("Firestore get_user(%s) failed: %s", uid, e)
        return None


def get_organization(organization_id: str) -> Optional[dict[str, Any]]:
    """
    Read organizations/{organization_id} from Firestore.
    Expected fields: name, ad_channels (or datasets) for client/dataset config.
    """
    db = _get_firestore()
    if not db:
        return None
    try:
        doc = db.collection("organizations").document(organization_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.warning("Firestore get_organization(%s) failed: %s", organization_id, e)
        return None
