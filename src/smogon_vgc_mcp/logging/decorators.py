"""Logging decorators for tools, HTTP requests, and database operations."""

import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from smogon_vgc_mcp.logging.config import get_logger
from smogon_vgc_mcp.logging.context import correlation_context
from smogon_vgc_mcp.logging.redaction import redact_sensitive

P = ParamSpec("P")
T = TypeVar("T")


def log_tool_call(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to log MCP tool invocations with timing and error handling."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        logger = get_logger(func.__module__)
        tool_name = func.__name__
        redacted_kwargs = redact_sensitive(dict(kwargs))

        with correlation_context():
            logger.info(
                f"Tool invoked: {tool_name}",
                extra={"extra_data": {"tool": tool_name, "params": redacted_kwargs}},
            )
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    f"Tool completed: {tool_name}",
                    extra={
                        "extra_data": {
                            "tool": tool_name,
                            "duration_ms": round(duration_ms, 2),
                        }
                    },
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"Tool failed: {tool_name}",
                    extra={
                        "extra_data": {
                            "tool": tool_name,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "duration_ms": round(duration_ms, 2),
                        }
                    },
                    exc_info=True,
                )
                raise

    return wrapper  # type: ignore[return-value]


def log_http_request(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to log HTTP requests with URL, status, and timing."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        logger = get_logger(func.__module__)
        url = args[0] if args else kwargs.get("url", "unknown")

        logger.debug(f"HTTP request starting: {url}")
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "HTTP request completed",
                extra={
                    "extra_data": {
                        "url": str(url),
                        "duration_ms": round(duration_ms, 2),
                        "success": result is not None,
                    }
                },
            )
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "HTTP request failed",
                extra={
                    "extra_data": {
                        "url": str(url),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration_ms": round(duration_ms, 2),
                    }
                },
                exc_info=True,
            )
            raise

    return wrapper  # type: ignore[return-value]


def log_database_operation(operation_name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator factory to log database operations with timing.

    Args:
        operation_name: Name of the database operation for logging.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger = get_logger(func.__module__)

            logger.debug(f"Database operation starting: {operation_name}")
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.debug(
                    f"Database operation completed: {operation_name}",
                    extra={
                        "extra_data": {
                            "operation": operation_name,
                            "duration_ms": round(duration_ms, 2),
                        }
                    },
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"Database operation failed: {operation_name}",
                    extra={
                        "extra_data": {
                            "operation": operation_name,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "duration_ms": round(duration_ms, 2),
                        }
                    },
                    exc_info=True,
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
