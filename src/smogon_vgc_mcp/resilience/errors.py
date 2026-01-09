"""Structured error types for resilience patterns."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ErrorCategory(Enum):
    """Categories of errors that can occur during external service calls."""

    TIMEOUT = "timeout"
    NETWORK = "network"
    HTTP_CLIENT_ERROR = "http_client_error"
    HTTP_SERVER_ERROR = "http_server_error"
    CIRCUIT_OPEN = "circuit_open"
    PARSE_ERROR = "parse_error"


@dataclass
class ServiceError:
    """Structured error from an external service call."""

    category: ErrorCategory
    service: str
    message: str
    status_code: int | None = None
    retries_attempted: int = 0
    is_recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category.value,
            "service": self.service,
            "message": self.message,
            "status_code": self.status_code,
            "retries_attempted": self.retries_attempted,
            "is_recoverable": self.is_recoverable,
        }


@dataclass
class FetchResult(Generic[T]):
    """Result of a fetch operation with success/failure information."""

    success: bool
    data: T | None = None
    error: ServiceError | None = None
    from_cache: bool = False
    stale_warning: str | None = None

    @classmethod
    def ok(cls, data: T, from_cache: bool = False) -> "FetchResult[T]":
        """Create a successful result."""
        return cls(success=True, data=data, from_cache=from_cache)

    @classmethod
    def fail(cls, error: ServiceError) -> "FetchResult[T]":
        """Create a failed result."""
        return cls(success=False, error=error)

    @classmethod
    def stale(cls, data: T, warning: str, error: ServiceError | None = None) -> "FetchResult[T]":
        """Create a result with stale data."""
        return cls(
            success=True,
            data=data,
            from_cache=True,
            stale_warning=warning,
            error=error,
        )


@dataclass
class BatchFetchResult:
    """Result of a batch fetch operation."""

    successful: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ServiceError] = field(default_factory=list)
    circuit_states: dict[str, str] = field(default_factory=dict)

    @property
    def all_succeeded(self) -> bool:
        """Check if all fetches succeeded."""
        return len(self.failed) == 0

    @property
    def partial_success(self) -> bool:
        """Check if some but not all fetches succeeded."""
        return len(self.successful) > 0 and len(self.failed) > 0

    @property
    def all_failed(self) -> bool:
        """Check if all fetches failed."""
        return len(self.successful) == 0 and len(self.failed) > 0
