"""Unified async HTTP client utilities.

This module consolidates HTTP fetching patterns from:
- fetcher/smogon.py
- fetcher/pokedex.py
- fetcher/moveset.py
- fetcher/sheets.py
- fetcher/pokepaste.py
"""

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from smogon_vgc_mcp.logging import get_logger, log_http_request
from smogon_vgc_mcp.resilience import (
    ErrorCategory,
    FetchResult,
    ServiceError,
    get_circuit_breaker,
)

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3
BACKOFF_MIN = 1
BACKOFF_MAX = 4


@log_http_request
async def fetch_json(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict | None:
    """Fetch and parse JSON from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default 60)

    Returns:
        Parsed JSON as dict, or None if fetch failed
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch JSON from %s: %s", url, e)
            return None


@log_http_request
async def fetch_text(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> str | None:
    """Fetch text content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default 60)
        verify: Whether to verify SSL certificates (default True)

    Returns:
        Response text, or None if fetch failed
    """
    async with httpx.AsyncClient(timeout=timeout, verify=verify) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.error("Failed to fetch text from %s: %s", url, e)
            return None


def _classify_error(exc: Exception, service: str, retries: int = 0) -> ServiceError:
    """Classify an exception into a structured ServiceError."""
    if isinstance(exc, httpx.TimeoutException):
        return ServiceError(
            category=ErrorCategory.TIMEOUT,
            service=service,
            message=f"Request timed out: {exc}",
            retries_attempted=retries,
            is_recoverable=True,
        )
    elif isinstance(exc, httpx.NetworkError):
        return ServiceError(
            category=ErrorCategory.NETWORK,
            service=service,
            message=f"Network error: {exc}",
            retries_attempted=retries,
            is_recoverable=True,
        )
    elif isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if 400 <= status < 500:
            return ServiceError(
                category=ErrorCategory.HTTP_CLIENT_ERROR,
                service=service,
                message=f"HTTP {status}: {exc}",
                status_code=status,
                retries_attempted=retries,
                is_recoverable=False,
            )
        else:
            return ServiceError(
                category=ErrorCategory.HTTP_SERVER_ERROR,
                service=service,
                message=f"HTTP {status}: {exc}",
                status_code=status,
                retries_attempted=retries,
                is_recoverable=True,
            )
    else:
        return ServiceError(
            category=ErrorCategory.NETWORK,
            service=service,
            message=str(exc),
            retries_attempted=retries,
            is_recoverable=True,
        )


def _create_retry_decorator():
    """Create a retry decorator with exponential backoff."""
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=BACKOFF_MIN, max=BACKOFF_MAX),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )


@log_http_request
async def fetch_json_resilient(
    url: str,
    service: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> FetchResult[dict]:
    """Fetch JSON with retry logic and circuit breaker protection.

    Args:
        url: The URL to fetch
        service: Service name for circuit breaker (smogon, showdown, sheets, pokepaste)
        timeout: Request timeout in seconds

    Returns:
        FetchResult with parsed JSON data or error information
    """
    circuit = get_circuit_breaker(service)

    if not circuit.can_execute():
        return FetchResult.fail(
            ServiceError(
                category=ErrorCategory.CIRCUIT_OPEN,
                service=service,
                message=f"Circuit breaker open for {service}",
                is_recoverable=True,
            )
        )

    retries = 0

    @_create_retry_decorator()
    async def _fetch() -> dict:
        nonlocal retries
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    try:
        data = await _fetch()
        circuit.record_success()
        return FetchResult.ok(data)
    except RetryError as e:
        retries = MAX_RETRIES
        original = e.last_attempt.exception() if e.last_attempt else e
        circuit.record_failure()
        return FetchResult.fail(_classify_error(original, service, retries))
    except httpx.HTTPStatusError as e:
        if 500 <= e.response.status_code < 600:
            circuit.record_failure()
        return FetchResult.fail(_classify_error(e, service, retries))
    except Exception as e:
        circuit.record_failure()
        return FetchResult.fail(_classify_error(e, service, retries))


@log_http_request
async def fetch_text_resilient(
    url: str,
    service: str,
    timeout: float = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> FetchResult[str]:
    """Fetch text with retry logic and circuit breaker protection.

    Args:
        url: The URL to fetch
        service: Service name for circuit breaker (smogon, showdown, sheets, pokepaste)
        timeout: Request timeout in seconds
        verify: Whether to verify SSL certificates

    Returns:
        FetchResult with response text or error information
    """
    circuit = get_circuit_breaker(service)

    if not circuit.can_execute():
        return FetchResult.fail(
            ServiceError(
                category=ErrorCategory.CIRCUIT_OPEN,
                service=service,
                message=f"Circuit breaker open for {service}",
                is_recoverable=True,
            )
        )

    retries = 0

    @_create_retry_decorator()
    async def _fetch() -> str:
        nonlocal retries
        async with httpx.AsyncClient(timeout=timeout, verify=verify) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    try:
        data = await _fetch()
        circuit.record_success()
        return FetchResult.ok(data)
    except RetryError as e:
        retries = MAX_RETRIES
        original = e.last_attempt.exception() if e.last_attempt else e
        circuit.record_failure()
        return FetchResult.fail(_classify_error(original, service, retries))
    except httpx.HTTPStatusError as e:
        if 500 <= e.response.status_code < 600:
            circuit.record_failure()
        return FetchResult.fail(_classify_error(e, service, retries))
    except Exception as e:
        circuit.record_failure()
        return FetchResult.fail(_classify_error(e, service, retries))
