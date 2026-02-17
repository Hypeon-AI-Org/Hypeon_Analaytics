"""Standard API envelope for /api/v1 responses."""
from typing import Any, List, Optional

from pydantic import BaseModel


class ApiEnvelope(BaseModel):
    """Standard envelope: success, data, meta, errors. Used for all /api/v1 JSON responses."""
    success: bool = True
    data: Optional[Any] = None
    meta: Optional[dict] = None
    errors: List[str] = []


def envelope_success(data: Any, meta: Optional[dict] = None) -> dict:
    """Build success envelope."""
    return {
        "success": True,
        "data": data,
        "meta": meta or {},
        "errors": [],
    }


def envelope_error(errors: List[str], meta: Optional[dict] = None) -> dict:
    """Build error envelope. Do not include stack traces."""
    return {
        "success": False,
        "data": None,
        "meta": meta or {},
        "errors": list(errors),
    }
