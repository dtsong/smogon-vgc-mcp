"""Tests for resilience patterns (circuit breaker, error types)."""

from datetime import timedelta
from unittest.mock import MagicMock

import httpx

from smogon_vgc_mcp.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    ErrorCategory,
    FetchResult,
    ServiceError,
)
from smogon_vgc_mcp.utils.http_client import _classify_error


class TestErrorCategory:
    def test_all_categories_defined(self):
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.HTTP_CLIENT_ERROR.value == "http_client_error"
        assert ErrorCategory.HTTP_SERVER_ERROR.value == "http_server_error"
        assert ErrorCategory.CIRCUIT_OPEN.value == "circuit_open"
        assert ErrorCategory.PARSE_ERROR.value == "parse_error"


class TestServiceError:
    def test_create_service_error(self):
        error = ServiceError(
            category=ErrorCategory.TIMEOUT,
            service="smogon",
            message="Request timed out",
            retries_attempted=3,
        )
        assert error.category == ErrorCategory.TIMEOUT
        assert error.service == "smogon"
        assert error.message == "Request timed out"
        assert error.retries_attempted == 3
        assert error.is_recoverable is True

    def test_to_dict(self):
        error = ServiceError(
            category=ErrorCategory.HTTP_CLIENT_ERROR,
            service="showdown",
            message="HTTP 404",
            status_code=404,
            is_recoverable=False,
        )
        result = error.to_dict()
        assert result["category"] == "http_client_error"
        assert result["service"] == "showdown"
        assert result["status_code"] == 404
        assert result["is_recoverable"] is False


class TestFetchResult:
    def test_ok_result(self):
        result = FetchResult.ok({"data": "test"})
        assert result.success is True
        assert result.data == {"data": "test"}
        assert result.error is None

    def test_fail_result(self):
        error = ServiceError(
            category=ErrorCategory.TIMEOUT,
            service="test",
            message="timed out",
        )
        result = FetchResult.fail(error)
        assert result.success is False
        assert result.data is None
        assert result.error == error

    def test_stale_result(self):
        result = FetchResult.stale(
            {"cached": True},
            warning="Data is 24h old",
        )
        assert result.success is True
        assert result.data == {"cached": True}
        assert result.from_cache is True
        assert result.stale_warning == "Data is 24h old"


class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    def test_opens_after_threshold_failures(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

    def test_success_resets_failure_count(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()

        assert breaker._failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self):
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=timedelta(seconds=0),
        )
        breaker = CircuitBreaker("test", config)

        breaker.record_failure()
        breaker.record_failure()
        # With 0-second timeout, checking state immediately transitions to HALF_OPEN
        # The internal state was OPEN, but the property checks recovery timeout
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.can_execute() is True

    def test_closes_after_success_in_half_open(self):
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=timedelta(seconds=0),
            success_threshold=2,
        )
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Should be half-open now
        assert breaker.state == CircuitState.HALF_OPEN

        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN  # Need 2 successes

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens(self):
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=timedelta(hours=1),  # Long timeout so state stays OPEN
        )
        breaker = CircuitBreaker("test", config)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker._state == CircuitState.OPEN  # Check internal state

        # Manually set to half-open to test the transition
        breaker._state = CircuitState.HALF_OPEN

        breaker.record_failure()
        assert breaker._state == CircuitState.OPEN

    def test_get_state_info(self):
        breaker = CircuitBreaker("test")
        breaker.record_failure()

        info = breaker.get_state_info()
        assert info["state"] == "closed"
        assert info["failure_count"] == 1
        assert "last_failure" in info

    def test_reset(self):
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0


class TestCircuitBreakerRegistry:
    def test_singleton(self):
        registry1 = CircuitBreakerRegistry()
        registry2 = CircuitBreakerRegistry()
        assert registry1 is registry2

    def test_get_breaker_creates_if_not_exists(self):
        registry = CircuitBreakerRegistry()
        registry.reset_all()

        breaker = registry.get_breaker("new_service")
        assert breaker.name == "new_service"
        assert breaker.state == CircuitState.CLOSED

    def test_get_breaker_returns_same_instance(self):
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get_breaker("test_service")
        breaker2 = registry.get_breaker("test_service")
        assert breaker1 is breaker2

    def test_get_all_states(self):
        registry = CircuitBreakerRegistry()
        registry.reset_all()

        registry.get_breaker("service_a")
        registry.get_breaker("service_b")

        states = registry.get_all_states()
        assert "service_a" in states
        assert "service_b" in states


class TestClassifyError:
    def test_timeout_exception(self):
        exc = httpx.TimeoutException("Connection timed out")
        error = _classify_error(exc, "test", retries=2)

        assert error.category == ErrorCategory.TIMEOUT
        assert error.service == "test"
        assert error.retries_attempted == 2
        assert error.is_recoverable is True

    def test_network_error(self):
        exc = httpx.NetworkError("DNS lookup failed")
        error = _classify_error(exc, "test")

        assert error.category == ErrorCategory.NETWORK
        assert error.is_recoverable is True

    def test_http_client_error(self):
        response = MagicMock()
        response.status_code = 404
        exc = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=response)
        error = _classify_error(exc, "test")

        assert error.category == ErrorCategory.HTTP_CLIENT_ERROR
        assert error.status_code == 404
        assert error.is_recoverable is False

    def test_http_server_error(self):
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=response)
        error = _classify_error(exc, "test")

        assert error.category == ErrorCategory.HTTP_SERVER_ERROR
        assert error.status_code == 503
        assert error.is_recoverable is True

    def test_unknown_exception(self):
        exc = ValueError("Something went wrong")
        error = _classify_error(exc, "test")

        assert error.category == ErrorCategory.NETWORK
        assert error.is_recoverable is True
