"""
In-memory log ring buffer.

Installs a logging.Handler that keeps the last MAX_RECORDS log records
across all loggers at WARNING level and above.  Call install() once at
app startup; call get_records() to retrieve them for display.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import TypedDict

MAX_RECORDS = 200


class LogRecord(TypedDict):
    ts:      str
    level:   str
    logger:  str
    message: str


_buffer: deque[LogRecord] = deque(maxlen=MAX_RECORDS)


class _MemoryHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _buffer.append(LogRecord(
                ts=datetime.fromtimestamp(record.created, tz=timezone.utc)
                          .strftime("%Y-%m-%d %H:%M:%S"),
                level=record.levelname,
                logger=record.name,
                message=self.format(record),
            ))
        except Exception:
            pass


_handler: _MemoryHandler | None = None


def install(level: int = logging.WARNING) -> None:
    """Attach the memory handler to the root logger.  Safe to call multiple times."""
    global _handler
    if _handler is not None:
        return
    _handler = _MemoryHandler(level=level)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(_handler)


def get_records() -> list[LogRecord]:
    """Return log records newest-first."""
    return list(reversed(_buffer))


def clear() -> None:
    """Clear the buffer (e.g. for tests)."""
    _buffer.clear()
