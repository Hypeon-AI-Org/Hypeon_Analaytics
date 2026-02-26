"""
Central logging configuration for the backend.
- Readable terminal format: timestamp, level, logger name, message.
- LOG_LEVEL from env (default INFO). Quiet third-party loggers (google.*, uvicorn.access).
- Suppress BigQuery Storage module UserWarning (optional dependency not installed).
- Unbuffered stream so logs appear live in terminal (Windows/uvicorn).
"""
from __future__ import annotations

import logging
import os
import sys
import warnings


class UnbufferedStream:
    """Wraps a stream so every write() is followed by flush() for live terminal output."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, s):
        self._stream.write(s)
        self._stream.flush()

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class FlushingStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes after each record so logs appear immediately (e.g. under uvicorn)."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def configure_logging() -> None:
    """Configure root and app loggers. Call once at startup (e.g. in lifespan)."""
    # Force stderr line-buffered so logs appear live when running under uvicorn
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(line_buffering=True)
        except Exception:
            pass
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Format: timestamp level name message (one line)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Use unbuffered stderr so logs show up live in terminal (critical on Windows/uvicorn)
    stderr_unbuffered = UnbufferedStream(sys.stderr)
    handler = FlushingStreamHandler(stderr_unbuffered)
    handler.setFormatter(formatter)

    # Root logger: so app.main, app.llm_claude, etc. all get this format
    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn loggers use the same handler/format
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.handlers = []
        log.addHandler(handler)
        log.setLevel(level)

    # Reduce noise from third-party libs (unless DEBUG)
    if level > logging.DEBUG:
        logging.getLogger("google.auth").setLevel(logging.WARNING)
        logging.getLogger("google.cloud").setLevel(logging.WARNING)
        logging.getLogger("google.cloud.bigquery").setLevel(logging.WARNING)
        logging.getLogger("google.cloud.bigquery.table").setLevel(logging.WARNING)
    # Optional: hide uvicorn access logs (every 200) unless UVICORN_ACCESS_LOG=1
    access_log = os.environ.get("UVICORN_ACCESS_LOG", "1").lower() in ("1", "true", "yes")
    if not access_log:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Suppress BigQuery Storage module not found (REST fallback is used; no need to warn)
    warnings.filterwarnings(
        "ignore",
        message="BigQuery Storage module not found",
        module="google.cloud.bigquery.table",
    )
