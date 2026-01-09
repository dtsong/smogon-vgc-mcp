"""Response formatting utilities for consistent data presentation."""


def round_percent(value: float, decimals: int = 1) -> float:
    """Round a percentage value for display.

    Args:
        value: The percentage value to round
        decimals: Number of decimal places (default 1)

    Returns:
        Rounded percentage value

    Examples:
        >>> round_percent(45.678)
        45.7
        >>> round_percent(45.678, 2)
        45.68
    """
    return round(value, decimals)
