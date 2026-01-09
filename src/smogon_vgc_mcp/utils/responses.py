"""Standardized response builders for MCP tools."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from smogon_vgc_mcp.resilience import ServiceError


def make_error_response(
    message: str,
    hint: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Create a standardized error response dictionary.

    Args:
        message: The error message to display
        hint: Optional hint for resolving the error
        **extra: Additional key-value pairs to include in response

    Returns:
        Error response dictionary with "error" key and optional "hint"

    Examples:
        >>> make_error_response("Pokemon not found")
        {'error': 'Pokemon not found'}

        >>> make_error_response("Pokemon not found", hint="Try find_pokemon")
        {'error': 'Pokemon not found', 'hint': 'Try find_pokemon'}

        >>> make_error_response("Not found", query="pikachu")
        {'error': 'Not found', 'query': 'pikachu'}
    """
    result: dict[str, Any] = {"error": message}
    if hint:
        result["hint"] = hint
    result.update(extra)
    return result


def make_degraded_response(
    data: dict[str, Any],
    stale_since: str | None = None,
    errors: list["ServiceError"] | None = None,
) -> dict[str, Any]:
    """Create a response with stale data warning.

    Use when returning cached data because external services are unavailable.

    Args:
        data: The stale data to return
        stale_since: ISO timestamp of when data was last refreshed
        errors: Optional list of ServiceError objects describing what failed

    Returns:
        Data dictionary with _warning field added
    """
    warning: dict[str, Any] = {
        "type": "stale_data",
        "message": "Data may be outdated. External service unavailable.",
    }
    if stale_since:
        warning["stale_since"] = stale_since
    if errors:
        warning["errors"] = [e.to_dict() for e in errors]

    return {
        **data,
        "_warning": warning,
    }
