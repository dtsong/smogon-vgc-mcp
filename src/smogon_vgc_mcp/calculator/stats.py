"""Pokemon stat calculator using VGC Level 50 formulas."""

import math

from smogon_vgc_mcp.data.pokemon_data import (
    get_base_stats,
    get_nature_multiplier,
)
from smogon_vgc_mcp.utils import parse_ev_string, parse_iv_string


def calculate_hp(base: int, iv: int, ev: int, level: int = 50) -> int:
    """Calculate HP stat.

    HP = floor((2 * Base + IV + floor(EV/4)) * Level/100) + Level + 10

    For Shedinja, HP is always 1.
    """
    return math.floor((2 * base + iv + math.floor(ev / 4)) * level / 100) + level + 10


def calculate_stat(
    base: int,
    iv: int,
    ev: int,
    nature_multiplier: float = 1.0,
    level: int = 50,
) -> int:
    """Calculate a non-HP stat.

    Stat = floor((floor((2 * Base + IV + floor(EV/4)) * Level/100) + 5) * Nature)
    """
    raw = math.floor((2 * base + iv + math.floor(ev / 4)) * level / 100) + 5
    return math.floor(raw * nature_multiplier)


def calculate_all_stats(
    pokemon: str,
    evs: str | dict,
    ivs: str | dict | None = None,
    nature: str = "Hardy",
    level: int = 50,
) -> dict | None:
    """Calculate all stats for a Pokemon.

    Args:
        pokemon: Pokemon name
        evs: EV spread as string '252/4/0/252/0/0' or dict
        ivs: IV spread (defaults to 31s if not specified)
        nature: Nature name
        level: Pokemon level (default 50 for VGC)

    Returns:
        Dict with hp, atk, def, spa, spd, spe calculated values
        or None if Pokemon not found
    """
    base = get_base_stats(pokemon)
    if not base:
        return None

    # Parse EVs and IVs
    if isinstance(evs, str):
        evs = parse_ev_string(evs)
    if ivs is None:
        ivs = {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}
    elif isinstance(ivs, str):
        ivs = parse_iv_string(ivs)

    # Calculate each stat
    stats = {}

    # HP
    stats["hp"] = calculate_hp(base["hp"], ivs["hp"], evs["hp"], level)

    # Other stats with nature modifiers
    for stat in ["atk", "def", "spa", "spd", "spe"]:
        nature_mult = get_nature_multiplier(nature, stat)
        stats[stat] = calculate_stat(
            base[stat],
            ivs[stat],
            evs[stat],
            nature_mult,
            level,
        )

    return stats


def format_stats(stats: dict) -> str:
    """Format stats dict as a readable string."""
    return (
        f"HP: {stats['hp']} | "
        f"Atk: {stats['atk']} | "
        f"Def: {stats['def']} | "
        f"SpA: {stats['spa']} | "
        f"SpD: {stats['spd']} | "
        f"Spe: {stats['spe']}"
    )
