"""Pokemon reference data module."""

from smogon_vgc_mcp.data.pokemon_data import (
    ALL_TYPES,
    NATURE_MODIFIERS,
    TYPE_CHART,
    get_base_stats,
    get_nature_modifiers,
    get_nature_multiplier,
    get_pokemon_types,
    get_resistances,
    get_type_effectiveness,
    get_weaknesses,
    normalize_pokemon_name,
)

__all__ = [
    "ALL_TYPES",
    "NATURE_MODIFIERS",
    "TYPE_CHART",
    "get_base_stats",
    "get_nature_modifiers",
    "get_nature_multiplier",
    "get_pokemon_types",
    "get_resistances",
    "get_type_effectiveness",
    "get_weaknesses",
    "normalize_pokemon_name",
]
