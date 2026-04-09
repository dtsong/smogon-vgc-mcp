"""Pokemon Champions format stat calculator using SP (Skill Points) system."""

import math

from smogon_vgc_mcp.data.pokemon_data import NATURE_MODIFIERS, get_nature_multiplier

MAX_SP_PER_STAT = 32
MAX_TOTAL_SP = 66

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
STAT_NAMES = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}


def _validate_sp(sp: int) -> None:
    if sp < 0 or sp > MAX_SP_PER_STAT:
        raise ValueError(f"SP must be 0-{MAX_SP_PER_STAT}, got {sp}")


def calculate_champions_hp(base: int, sp: int, level: int = 50) -> int:
    """Calculate Champions HP stat.

    HP = floor((2 * base) * level / 100) + level + 10 + sp
    """
    _validate_sp(sp)
    return math.floor((2 * base) * level / 100) + level + 10 + sp


def calculate_champions_stat(
    base: int,
    sp: int,
    nature_multiplier: float = 1.0,
    level: int = 50,
) -> int:
    """Calculate a Champions non-HP stat.

    Stat = floor((floor((2 * base) * level / 100) + 5) * nature_multiplier) + sp

    SP is added AFTER the nature multiplier, not before.
    """
    _validate_sp(sp)
    raw = math.floor((2 * base) * level / 100) + 5
    return math.floor(raw * nature_multiplier) + sp


def calculate_all_champions_stats(
    base_stats: dict[str, int],
    sp_spread: dict[str, int],
    nature: str = "Hardy",
    level: int = 50,
) -> dict[str, int] | None:
    """Calculate all 6 stats for a Pokemon in Champions format.

    Returns None for invalid nature. Raises ValueError if total SP > 66
    or any individual SP is out of range.
    """
    # Validate nature
    if nature.lower() not in NATURE_MODIFIERS:
        return None

    # Validate total SP
    total_sp = sum(sp_spread.get(s, 0) for s in STAT_ORDER)
    if total_sp > MAX_TOTAL_SP:
        raise ValueError(f"Total SP ({total_sp}) exceeds maximum ({MAX_TOTAL_SP})")

    stats: dict[str, int] = {}

    stats["hp"] = calculate_champions_hp(base_stats["hp"], sp_spread.get("hp", 0), level)

    for stat in STAT_ORDER[1:]:
        nature_mult = get_nature_multiplier(nature, stat)
        stats[stat] = calculate_champions_stat(
            base_stats[stat], sp_spread.get(stat, 0), nature_mult, level
        )

    return stats


def format_champions_stats(stats: dict[str, int]) -> str:
    """Format stats dict as 'HP: X / Atk: Y / ...' string."""
    parts = [f"{STAT_NAMES[s]}: {stats[s]}" for s in STAT_ORDER]
    return " / ".join(parts)
