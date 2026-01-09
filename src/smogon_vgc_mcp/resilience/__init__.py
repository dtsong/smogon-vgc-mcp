"""Resilience patterns for external service calls."""

from smogon_vgc_mcp.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_all_circuit_states,
    get_circuit_breaker,
)
from smogon_vgc_mcp.resilience.errors import (
    BatchFetchResult,
    ErrorCategory,
    FetchResult,
    ServiceError,
)

__all__ = [
    "BatchFetchResult",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
    "ErrorCategory",
    "FetchResult",
    "ServiceError",
    "get_all_circuit_states",
    "get_circuit_breaker",
]
