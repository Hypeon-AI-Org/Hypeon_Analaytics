"""Statistical helpers and serialization for MMM/rules."""
import json
from typing import Any, Dict


def safe_float(x: Any) -> float:
    """Coerce to float or 0."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def serialize_coefficients(coefs: Dict[str, float]) -> str:
    """JSON-serialize coefficient map."""
    return json.dumps(coefs)
