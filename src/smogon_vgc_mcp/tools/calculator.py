"""Calculator tools for MCP server (stats, speed tiers, types)."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.calculator.speed_tiers import (
    compare_speeds,
    find_speed_benchmarks,
    get_speed_stat,
)
from smogon_vgc_mcp.calculator.stats import calculate_all_stats, format_stats
from smogon_vgc_mcp.calculator.types import (
    analyze_team_types,
    get_offensive_coverage,
)
from smogon_vgc_mcp.data.pokemon_data import get_base_stats
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    validate_ev_spread,
    validate_iv_spread,
    validate_level,
    validate_nature,
    validate_pokemon_list,
    validate_pokemon_name,
    validate_type_list,
)


def register_calculator_tools(mcp: FastMCP) -> None:
    """Register calculator tools with the MCP server."""

    @mcp.tool()
    async def calculate_pokemon_stats(
        pokemon: str,
        evs: str,
        nature: str = "Hardy",
        ivs: str = "31/31/31/31/31/31",
        level: int = 50,
    ) -> dict:
        """Calculate actual stat values for a Pokemon at Level 50.

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane")
            evs: EV spread as "HP/Atk/Def/SpA/SpD/Spe" (e.g., "252/4/0/0/0/252").
                Each stat: 0-252. Total must not exceed 510.
            nature: Nature name (e.g., "Adamant" +Atk/-SpA, "Timid" +Spe/-Atk).
                Use "Hardy" for neutral (no stat changes).
            ivs: IV spread as "HP/Atk/Def/SpA/SpD/Spe". Each stat: 0-31.
                Default 31/31/31/31/31/31 (perfect IVs).
            level: Pokemon level (default 50 for VGC)

        Returns:
            Calculated stats for HP, Atk, Def, SpA, SpD, Spe
        """
        try:
            validate_pokemon_name(pokemon)
            validate_ev_spread(evs)
            validate_iv_spread(ivs)
            validate_nature(nature)
            validate_level(level)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        base = get_base_stats(pokemon)
        if not base:
            return make_error_response(
                f"Pokemon '{pokemon}' not found",
                hint="Check spelling or try the full name",
            )

        stats = calculate_all_stats(pokemon, evs, ivs, nature, level)
        if not stats:
            return make_error_response("Failed to calculate stats")

        return {
            "pokemon": pokemon,
            "level": level,
            "nature": nature,
            "evs": evs,
            "ivs": ivs,
            "base_stats": base,
            "calculated_stats": stats,
            "formatted": format_stats(stats),
        }

    @mcp.tool()
    async def compare_pokemon_speeds(
        pokemon1: str,
        evs1: str,
        nature1: str,
        pokemon2: str,
        evs2: str,
        nature2: str,
    ) -> dict:
        """Compare speed stats between two Pokemon to see who outspeeds.

        Args:
            pokemon1: First Pokemon name
            evs1: First Pokemon's EV spread (e.g., "252/0/0/0/0/252")
            nature1: First Pokemon's nature
            pokemon2: Second Pokemon name
            evs2: Second Pokemon's EV spread
            nature2: Second Pokemon's nature

        Returns:
            Speed comparison with values and result
        """
        try:
            validate_pokemon_name(pokemon1)
            validate_ev_spread(evs1)
            validate_nature(nature1)
            validate_pokemon_name(pokemon2)
            validate_ev_spread(evs2)
            validate_nature(nature2)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        return compare_speeds(pokemon1, evs1, nature1, pokemon2, evs2, nature2)

    @mcp.tool()
    async def get_speed_benchmarks(
        pokemon: str,
        evs: str,
        nature: str = "Hardy",
    ) -> dict:
        """Find what notable Pokemon a given speed stat outspeeds or underspeeds.

        Args:
            pokemon: Pokemon name
            evs: EV spread (e.g., "0/0/0/0/0/252")
            nature: Nature name

        Returns:
            Lists of Pokemon this speed beats and loses to
        """
        try:
            validate_pokemon_name(pokemon)
            validate_ev_spread(evs)
            validate_nature(nature)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        speed = get_speed_stat(pokemon, evs, None, nature)
        if speed is None:
            return make_error_response(f"Could not calculate speed for '{pokemon}'")

        return find_speed_benchmarks(pokemon, speed)

    @mcp.tool()
    async def analyze_team_type_coverage(pokemon_list: list[str]) -> dict:
        """Analyze type weaknesses and coverage for a team of Pokemon.

        Args:
            pokemon_list: List of 1-6 Pokemon names on the team
                (e.g., ["Incineroar", "Flutter Mane", "Rillaboom", "Urshifu"])

        Returns:
            Team type analysis including shared weaknesses and unresisted types
        """
        try:
            validate_pokemon_list(pokemon_list, min_size=1, max_size=6)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        return analyze_team_types(pokemon_list)

    @mcp.tool()
    async def analyze_move_coverage(move_types: list[str]) -> dict:
        """Analyze offensive type coverage of a moveset.

        Args:
            move_types: List of move types (e.g., ["Fire", "Fighting", "Dark"])

        Returns:
            Coverage analysis showing what types are hit super-effectively
        """
        try:
            validate_type_list(move_types, min_size=1, max_size=4)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        return get_offensive_coverage(move_types)
