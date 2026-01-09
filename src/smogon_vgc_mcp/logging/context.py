"""Correlation ID context management for request tracing."""

import uuid
from contextlib import contextmanager
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(cid: str | None = None) -> str:
    """Set a correlation ID in context. Generates one if not provided."""
    cid = cid or str(uuid.uuid4())[:8]
    _correlation_id.set(cid)
    return cid


@contextmanager
def correlation_context(cid: str | None = None):
    """Context manager that sets a correlation ID for the duration of the block."""
    new_cid = cid or str(uuid.uuid4())[:8]
    token = _correlation_id.set(new_cid)
    try:
        yield new_cid
    finally:
        _correlation_id.reset(token)
