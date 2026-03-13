"""Simple in-process metrics for Copilot V2 (planner attempts, fallback success, empty results, latency histograms)."""
from __future__ import annotations

import threading
from typing import List

_metrics = {
    "copilot.planner_attempts_total": 0,
    "copilot.fallback_success_total": 0,
    "copilot.query_empty_results_total": 0,
}
_timings: dict[str, List[float]] = {}
_lock = threading.Lock()


def increment(name: str, value: int = 1) -> None:
    if name in _metrics:
        with _lock:
            _metrics[name] += value


def timing(name: str, elapsed_ms: float) -> None:
    """Record a latency sample for a phase (e.g. copilot.planner_ms, copilot.bq_execution_ms)."""
    with _lock:
        if name not in _timings:
            _timings[name] = []
        _timings[name].append(elapsed_ms)
        # Keep last 1000 samples per key
        if len(_timings[name]) > 1000:
            _timings[name] = _timings[name][-1000:]


def get_timings(name: str) -> List[float]:
    """Return list of recorded latencies for a key (for P50/P95 etc)."""
    with _lock:
        return list(_timings.get(name, []))


def get(name: str) -> int:
    with _lock:
        return _metrics.get(name, 0)


def reset() -> None:
    with _lock:
        for k in _metrics:
            _metrics[k] = 0
        _timings.clear()
