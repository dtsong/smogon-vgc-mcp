"""Circuit breaker pattern implementation for external service resilience."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any


class CircuitState(Enum):
    """States of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    success_threshold: int = 2


SERVICE_CONFIGS: dict[str, CircuitBreakerConfig] = {
    "smogon": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=timedelta(seconds=60),
    ),
    "showdown": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=timedelta(seconds=60),
    ),
    "sheets": CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=timedelta(seconds=120),
    ),
    "pokepaste": CircuitBreakerConfig(
        failure_threshold=10,
        recovery_timeout=timedelta(seconds=30),
    ),
}


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or SERVICE_CONFIGS.get(name, CircuitBreakerConfig())
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout."""
        with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time:
                if datetime.now() - self._last_failure_time >= self.config.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
            return self._state

    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        return self.state != CircuitState.OPEN

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._success_count = 0
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN

    def get_state_info(self) -> dict[str, Any]:
        """Get current state information."""
        current_state = self.state
        with self._lock:
            info: dict[str, Any] = {
                "state": current_state.value,
                "failure_count": self._failure_count,
            }
            if self._last_failure_time:
                info["last_failure"] = self._last_failure_time.isoformat()
                if current_state == CircuitState.OPEN:
                    recovery_at = self._last_failure_time + self.config.recovery_timeout
                    info["recovery_at"] = recovery_at.isoformat()
            return info

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None


class CircuitBreakerRegistry:
    """Registry of circuit breakers per service."""

    _instance: "CircuitBreakerRegistry | None" = None
    _lock = Lock()
    _breakers: dict[str, CircuitBreaker]
    _breaker_lock: Lock

    def __new__(cls) -> "CircuitBreakerRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._breakers = {}
                cls._instance._breaker_lock = Lock()
            return cls._instance

    def get_breaker(self, service: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        with self._breaker_lock:
            if service not in self._breakers:
                self._breakers[service] = CircuitBreaker(service)
            return self._breakers[service]

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get state information for all circuit breakers."""
        with self._breaker_lock:
            return {name: breaker.get_state_info() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._breaker_lock:
            for breaker in self._breakers.values():
                breaker.reset()


def get_circuit_breaker(service: str) -> CircuitBreaker:
    """Convenience function to get a circuit breaker for a service."""
    return CircuitBreakerRegistry().get_breaker(service)


def get_all_circuit_states() -> dict[str, dict[str, Any]]:
    """Convenience function to get all circuit breaker states."""
    return CircuitBreakerRegistry().get_all_states()
