"""Limit validation utilities.

This module consolidates limit capping patterns used throughout tool files.
"""

# Default maximum limits for different query types
DEFAULT_MAX_LIMIT = 20
RANKINGS_MAX_LIMIT = 50

# Display limits for tool response data
# These control how many items are shown in each category
MAX_ABILITIES_DISPLAY = 5
MAX_ITEMS_DISPLAY = 10
MAX_MOVES_DISPLAY = 10
MAX_TEAMMATES_DISPLAY = 8
MAX_SPREADS_DISPLAY = 5
MAX_TERA_TYPES_DISPLAY = 5
MAX_COUNTERS_DISPLAY = 5


def cap_limit(limit: int, max_limit: int = DEFAULT_MAX_LIMIT) -> int:
    """Cap a limit value to a maximum.

    Args:
        limit: The requested limit
        max_limit: Maximum allowed value (default 20)

    Returns:
        The capped limit value

    Examples:
        >>> cap_limit(100)
        20
        >>> cap_limit(10)
        10
        >>> cap_limit(100, max_limit=50)
        50
    """
    return min(limit, max_limit)
