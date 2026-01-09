"""Unified stat name mappings for the project.

This module consolidates all stat name variations used throughout the codebase
into a single source of truth.
"""

# Canonical stat keys used throughout the codebase (order matches standard format)
STAT_ORDER: list[str] = ["hp", "atk", "def", "spa", "spd", "spe"]

# Comprehensive mapping from various input formats to canonical keys
# Includes: lowercase variants, full names, abbreviated forms
STAT_NAME_MAP: dict[str, str] = {
    # HP variants
    "hp": "hp",
    # Attack variants
    "atk": "atk",
    "attack": "atk",
    # Defense variants
    "def": "def",
    "defense": "def",
    # Special Attack variants
    "spa": "spa",
    "spatk": "spa",
    "sp.atk": "spa",
    "specialattack": "spa",
    "special attack": "spa",
    # Special Defense variants
    "spd": "spd",
    "spdef": "spd",
    "sp.def": "spd",
    "specialdefense": "spd",
    "special defense": "spd",
    # Speed variants
    "spe": "spe",
    "speed": "spe",
}

# Showdown format stat names (used in EVs:/IVs: lines from pokepaste)
# These are case-sensitive as they appear in Showdown exports
SHOWDOWN_STAT_MAP: dict[str, str] = {
    "HP": "hp",
    "Atk": "atk",
    "Def": "def",
    "SpA": "spa",
    "SpD": "spd",
    "Spe": "spe",
}


def normalize_stat_name(name: str) -> str | None:
    """Normalize any stat name variant to canonical form.

    Args:
        name: Stat name in any supported format

    Returns:
        Canonical stat key (hp/atk/def/spa/spd/spe) or None if not recognized

    Examples:
        >>> normalize_stat_name("HP")
        'hp'
        >>> normalize_stat_name("Special Attack")
        'spa'
        >>> normalize_stat_name("Spe")
        'spe'
    """
    # Try Showdown format first (case-sensitive)
    if name in SHOWDOWN_STAT_MAP:
        return SHOWDOWN_STAT_MAP[name]

    # Try lowercase matching
    return STAT_NAME_MAP.get(name.lower().replace(" ", ""))
