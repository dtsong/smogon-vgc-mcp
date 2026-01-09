"""Unified EV and IV string parsing.

This module consolidates EV/IV parsing from:
- calculator/stats.py
- calculator/damage.py
- fetcher/pokepaste.py

Supports two formats:
1. Compact: "252/4/0/252/0/0" (HP/Atk/Def/SpA/SpD/Spe order)
2. Showdown: "252 HP / 4 Def / 252 SpA"
"""

import re

from smogon_vgc_mcp.utils.stat_names import (
    SHOWDOWN_STAT_MAP,
    STAT_NAME_MAP,
    STAT_ORDER,
)


def default_evs() -> dict[str, int]:
    """Return default EV spread (all zeros)."""
    return {stat: 0 for stat in STAT_ORDER}


def default_ivs() -> dict[str, int]:
    """Return default IV spread (all 31s)."""
    return {stat: 31 for stat in STAT_ORDER}


def _parse_compact_spread(spread: str) -> dict[str, int] | None:
    """Parse compact format like '252/4/0/252/0/0'.

    Args:
        spread: Slash-separated numeric spread

    Returns:
        Dict with stat values, or None if not in compact format
    """
    if "/" not in spread:
        return None

    parts = spread.split("/")
    if len(parts) != 6:
        return None

    # Check if first part is purely numeric (compact format indicator)
    first_part = parts[0].strip()
    if any(c.isalpha() for c in first_part):
        return None

    try:
        return {STAT_ORDER[i]: int(parts[i].strip()) for i in range(6)}
    except ValueError:
        return None


def _parse_showdown_spread(spread: str, default_value: int) -> dict[str, int]:
    """Parse Showdown format like '252 HP / 4 Def / 252 SpA'.

    Args:
        spread: Showdown-format spread string
        default_value: Default value for unspecified stats (0 for EVs, 31 for IVs)

    Returns:
        Dict with stat values
    """
    result = {stat: default_value for stat in STAT_ORDER}

    # Handle optional "EVs:" or "IVs:" prefix
    spread = re.sub(r"^(EVs?|IVs?):\s*", "", spread, flags=re.IGNORECASE)

    for part in spread.split("/"):
        part = part.strip()
        if not part:
            continue

        # Match "252 HP" or "4 Def" pattern
        match = re.match(r"(\d+)\s+(\S+)", part)
        if match:
            value = int(match.group(1))
            stat_name = match.group(2)

            # Try Showdown format first (case-sensitive)
            if stat_name in SHOWDOWN_STAT_MAP:
                result[SHOWDOWN_STAT_MAP[stat_name]] = value
            else:
                # Try lowercase matching for other variants
                normalized = stat_name.lower().replace(" ", "")
                if normalized in STAT_NAME_MAP:
                    result[STAT_NAME_MAP[normalized]] = value

    return result


def parse_ev_string(evs: str) -> dict[str, int]:
    """Parse EV string in either compact or Showdown format.

    Supports:
    - Compact: "252/4/0/252/0/0"
    - Showdown: "252 HP / 4 Def / 252 SpA"
    - With prefix: "EVs: 252 HP / 4 Def / 252 SpA"

    Args:
        evs: EV spread string

    Returns:
        Dict with hp, atk, def, spa, spd, spe keys

    Examples:
        >>> parse_ev_string("252/4/0/252/0/0")
        {'hp': 252, 'atk': 4, 'def': 0, 'spa': 252, 'spd': 0, 'spe': 0}
        >>> parse_ev_string("252 HP / 4 Def / 252 SpA")
        {'hp': 252, 'atk': 0, 'def': 4, 'spa': 252, 'spd': 0, 'spe': 0}
    """
    if not evs or not evs.strip():
        return default_evs()

    # Try compact format first
    result = _parse_compact_spread(evs)
    if result is not None:
        return result

    # Fall back to Showdown format (default to 0 for EVs)
    return _parse_showdown_spread(evs, default_value=0)


def parse_iv_string(ivs: str | None) -> dict[str, int]:
    """Parse IV string, defaulting to 31 for unspecified stats.

    Supports:
    - None: Returns all 31s
    - Compact: "31/31/31/31/31/31"
    - Showdown: "0 Atk" (unspecified stats default to 31)
    - With prefix: "IVs: 0 Atk"

    Args:
        ivs: IV spread string or None

    Returns:
        Dict with hp, atk, def, spa, spd, spe keys

    Examples:
        >>> parse_iv_string(None)
        {'hp': 31, 'atk': 31, 'def': 31, 'spa': 31, 'spd': 31, 'spe': 31}
        >>> parse_iv_string("31/0/31/31/31/31")
        {'hp': 31, 'atk': 0, 'def': 31, 'spa': 31, 'spd': 31, 'spe': 31}
        >>> parse_iv_string("0 Atk")
        {'hp': 31, 'atk': 0, 'def': 31, 'spa': 31, 'spd': 31, 'spe': 31}
    """
    if ivs is None or not ivs.strip():
        return default_ivs()

    # Try compact format first
    result = _parse_compact_spread(ivs)
    if result is not None:
        return result

    # Fall back to Showdown format (default to 31 for IVs)
    return _parse_showdown_spread(ivs, default_value=31)
