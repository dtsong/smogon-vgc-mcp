"""Pokemon reference data for stat calculations and type analysis."""

from __future__ import annotations

import json
from pathlib import Path

ALL_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
]

TYPE_CHART: dict[str, dict[str, float]] = {
    "Normal": {"Rock": 0.5, "Ghost": 0, "Steel": 0.5},
    "Fire": {
        "Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 2,
        "Bug": 2, "Rock": 0.5, "Dragon": 0.5, "Steel": 2,
    },
    "Water": {"Fire": 2, "Water": 0.5, "Grass": 0.5, "Ground": 2, "Rock": 2, "Dragon": 0.5},
    "Electric": {
        "Water": 2, "Electric": 0.5, "Grass": 0.5,
        "Ground": 0, "Flying": 2, "Dragon": 0.5,
    },
    "Grass": {
        "Fire": 0.5, "Water": 2, "Grass": 0.5, "Poison": 0.5, "Ground": 2,
        "Flying": 0.5, "Bug": 0.5, "Rock": 2, "Dragon": 0.5, "Steel": 0.5,
    },
    "Ice": {
        "Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 0.5,
        "Ground": 2, "Flying": 2, "Dragon": 2, "Steel": 0.5,
    },
    "Fighting": {
        "Normal": 2, "Ice": 2, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5,
        "Bug": 0.5, "Rock": 2, "Ghost": 0, "Dark": 2, "Steel": 2, "Fairy": 0.5,
    },
    "Poison": {
        "Grass": 2, "Poison": 0.5, "Ground": 0.5,
        "Rock": 0.5, "Ghost": 0.5, "Steel": 0, "Fairy": 2,
    },
    "Ground": {
        "Fire": 2, "Electric": 2, "Grass": 0.5, "Poison": 2,
        "Flying": 0, "Bug": 0.5, "Rock": 2, "Steel": 2,
    },
    "Flying": {"Electric": 0.5, "Grass": 2, "Fighting": 2, "Bug": 2, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2, "Poison": 2, "Psychic": 0.5, "Dark": 0, "Steel": 0.5},
    "Bug": {
        "Fire": 0.5, "Grass": 2, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5,
        "Psychic": 2, "Ghost": 0.5, "Dark": 2, "Steel": 0.5, "Fairy": 0.5,
    },
    "Rock": {
        "Fire": 2, "Ice": 2, "Fighting": 0.5,
        "Ground": 0.5, "Flying": 2, "Bug": 2, "Steel": 0.5,
    },
    "Ghost": {"Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": 0.5},
    "Dragon": {"Dragon": 2, "Steel": 0.5, "Fairy": 0},
    "Dark": {"Fighting": 0.5, "Psychic": 2, "Ghost": 2, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {
        "Fire": 0.5, "Water": 0.5, "Electric": 0.5,
        "Ice": 2, "Rock": 2, "Steel": 0.5, "Fairy": 2,
    },
    "Fairy": {"Fire": 0.5, "Fighting": 2, "Poison": 0.5, "Dragon": 2, "Dark": 2, "Steel": 0.5},
}

NATURE_MODIFIERS: dict[str, tuple[str, str] | None] = {
    "hardy": None,
    "lonely": ("atk", "def"),
    "brave": ("atk", "spe"),
    "adamant": ("atk", "spa"),
    "naughty": ("atk", "spd"),
    "bold": ("def", "atk"),
    "docile": None,
    "relaxed": ("def", "spe"),
    "impish": ("def", "spa"),
    "lax": ("def", "spd"),
    "timid": ("spe", "atk"),
    "hasty": ("spe", "def"),
    "serious": None,
    "jolly": ("spe", "spa"),
    "naive": ("spe", "spd"),
    "modest": ("spa", "atk"),
    "mild": ("spa", "def"),
    "quiet": ("spa", "spe"),
    "bashful": None,
    "rash": ("spa", "spd"),
    "calm": ("spd", "atk"),
    "gentle": ("spd", "def"),
    "sassy": ("spd", "spe"),
    "careful": ("spd", "spa"),
    "quirky": None,
}

_base_stats: dict[str, dict[str, int]] | None = None
_types: dict[str, list[str]] | None = None


def _get_data_path() -> Path:
    return Path(__file__).parent


def _load_base_stats() -> dict[str, dict[str, int]]:
    global _base_stats
    if _base_stats is not None:
        return _base_stats

    path = _get_data_path() / "base_stats.json"
    with open(path) as f:
        _base_stats = json.load(f)
    return _base_stats


def _load_types() -> dict[str, list[str]]:
    global _types
    if _types is not None:
        return _types

    path = _get_data_path() / "types.json"
    with open(path) as f:
        _types = json.load(f)
    return _types


def normalize_pokemon_name(name: str) -> str:
    """Normalize Pokemon name for lookup (lowercase, no spaces/hyphens)."""
    return name.lower().replace(" ", "").replace("-", "")


def get_base_stats(pokemon: str) -> dict[str, int] | None:
    """Get base stats for a Pokemon.

    Returns dict with hp, atk, def, spa, spd, spe keys, or None if not found.
    """
    stats = _load_base_stats()
    normalized = normalize_pokemon_name(pokemon)
    return stats.get(normalized)


def get_pokemon_types(pokemon: str) -> list[str] | None:
    """Get types for a Pokemon.

    Returns list of 1-2 type strings, or None if not found.
    """
    types = _load_types()
    normalized = normalize_pokemon_name(pokemon)
    return types.get(normalized)


def get_nature_modifiers(nature: str) -> tuple[str, str] | None:
    """Get nature stat modifiers.

    Returns (boosted_stat, reduced_stat) tuple, or None for neutral natures.
    """
    return NATURE_MODIFIERS.get(nature.lower())


def get_nature_multiplier(nature: str, stat: str) -> float:
    """Get nature multiplier for a specific stat.

    Returns 1.1 for boosted, 0.9 for reduced, 1.0 for neutral.
    """
    mods = get_nature_modifiers(nature)
    if mods is None:
        return 1.0

    boosted, reduced = mods
    if stat == boosted:
        return 1.1
    if stat == reduced:
        return 0.9
    return 1.0


def get_type_effectiveness(attack_type: str, defending_types: list[str]) -> float:
    """Calculate type effectiveness multiplier.

    Args:
        attack_type: The attacking move's type
        defending_types: List of defending Pokemon's types

    Returns:
        Multiplier (0, 0.25, 0.5, 1, 2, or 4)
    """
    attack_normalized = attack_type.title()
    if attack_normalized not in TYPE_CHART:
        return 1.0

    chart = TYPE_CHART[attack_normalized]
    multiplier = 1.0

    for def_type in defending_types:
        def_normalized = def_type.title()
        mult = chart.get(def_normalized, 1.0)
        multiplier *= mult

    return multiplier


def get_weaknesses(pokemon: str) -> list[tuple[str, float]]:
    """Get types that deal super-effective damage to a Pokemon.

    Returns list of (type, multiplier) tuples sorted by multiplier descending.
    """
    types = get_pokemon_types(pokemon)
    if not types:
        return []

    weaknesses = []
    for attack_type in ALL_TYPES:
        mult = get_type_effectiveness(attack_type, types)
        if mult > 1:
            weaknesses.append((attack_type, mult))

    return sorted(weaknesses, key=lambda x: -x[1])


def get_resistances(pokemon: str) -> list[tuple[str, float]]:
    """Get types that deal reduced or no damage to a Pokemon.

    Returns list of (type, multiplier) tuples sorted by multiplier ascending.
    Includes immunities (0x), 4x resistances (0.25x), and 2x resistances (0.5x).
    """
    types = get_pokemon_types(pokemon)
    if not types:
        return []

    resistances = []
    for attack_type in ALL_TYPES:
        mult = get_type_effectiveness(attack_type, types)
        if mult < 1:
            resistances.append((attack_type, mult))

    return sorted(resistances, key=lambda x: x[1])
