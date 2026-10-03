"""Structured logging setup.

Call ``configure_logging()`` once at process start to install JSON-ish
structlog-compatible log records.  In test environments plain text is used.
"""

from __future__ import annotations

import logging
import sys
from typing import Any


class _JobFilter(logging.Filter):
    """Injects job_id/document_id/attempt into every LogRecord if set on the thread-local."""

    def filter(self, record: logging.LogRecord) -> bool:
        # These are injected by processors; provide defaults if absent.
        if not hasattr(record, "job_id"):
            record.job_id = "-"  # type: ignore[attr-defined]
        if not hasattr(record, "document_id"):
            record.document_id = "-"  # type: ignore[attr-defined]
        if not hasattr(record, "attempt"):
            record.attempt = 0  # type: ignore[attr-defined]
        return True


_FMT = (
    "%(asctime)s %(levelname)-8s [%(name)s] "
    "job=%(job_id)s doc=%(document_id)s attempt=%(attempt)s | %(message)s"
)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with structured format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FMT))
    handler.addFilter(_JobFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    msg: str,
    *args: Any,
    job_id: str | None = None,
    document_id: str | None = None,
    attempt: int = 0,
    **kwargs: Any,
) -> None:
    """Emit a log record with injected structured fields."""
    extra: dict[str, Any] = {
        "job_id": job_id or "-",
        "document_id": document_id or "-",
        "attempt": attempt,
    }
    logger.log(level, msg, *args, extra=extra, **kwargs)
