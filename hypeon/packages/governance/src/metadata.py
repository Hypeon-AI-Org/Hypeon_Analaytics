"""
Engine run metadata store. Bounded in-memory store using deque(maxlen=100).
Never expose the deque; always return a copy when queried.
"""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from packages.governance.src.versions import MTA_VERSION, MMM_VERSION, DATA_SNAPSHOT_ID

_MAX_RECENT_RUNS = 100
_recent_runs: deque = deque(maxlen=_MAX_RECENT_RUNS)


@dataclass
class EngineRunMetadata:
    """Metadata for one engine run."""

    run_id: str
    timestamp: datetime
    mta_version: str
    mmm_version: str
    data_snapshot_id: str


def record_run(
    run_id: str,
    mta_version: Optional[str] = None,
    mmm_version: Optional[str] = None,
    data_snapshot_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Record an engine run. Appends to bounded deque (maxlen=100).
    Never expose the deque itself.
    """
    meta = EngineRunMetadata(
        run_id=run_id,
        timestamp=timestamp or datetime.utcnow(),
        mta_version=mta_version or MTA_VERSION,
        mmm_version=mmm_version or MMM_VERSION,
        data_snapshot_id=data_snapshot_id or DATA_SNAPSHOT_ID,
    )
    _recent_runs.append(meta)


def get_recent_runs() -> List[EngineRunMetadata]:
    """Return a copy of recent runs (never the deque)."""
    return list(_recent_runs)


def get_latest_run() -> Optional[EngineRunMetadata]:
    """Return the most recent run, or None. Returns a copy of the metadata."""
    if not _recent_runs:
        return None
    last = _recent_runs[-1]
    return EngineRunMetadata(
        run_id=last.run_id,
        timestamp=last.timestamp,
        mta_version=last.mta_version,
        mmm_version=last.mmm_version,
        data_snapshot_id=last.data_snapshot_id,
    )
