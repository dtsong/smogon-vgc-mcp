"""Standardized response builders for MCP tools."""

from typing import Any


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
