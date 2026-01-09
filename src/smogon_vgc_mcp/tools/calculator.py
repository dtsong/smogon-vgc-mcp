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
    get_pokemon_weaknesses,
)
from smogon_vgc_mcp.data.pokemon_data import get_base_stats, get_pokemon_types


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
            evs: EV spread as "HP/Atk/Def/SpA/SpD/Spe" (e.g., "252/4/0/0/0/252")
            nature: Nature name (e.g., "Adamant", "Timid")
            ivs: IV spread (default 31/31/31/31/31/31)
            level: Pokemon level (default 50 for VGC)

        Returns:
            Calculated stats for HP, Atk, Def, SpA, SpD, Spe
        """
        base = get_base_stats(pokemon)
        if not base:
            return {
                "error": f"Pokemon '{pokemon}' not found",
                "hint": "Check spelling or try the full name",
            }

        stats = calculate_all_stats(pokemon, evs, ivs, nature, level)
        if not stats:
            return {"error": "Failed to calculate stats"}

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
        speed = get_speed_stat(pokemon, evs, None, nature)
        if speed is None:
            return {"error": f"Could not calculate speed for '{pokemon}'"}

        return find_speed_benchmarks(pokemon, speed)

    @mcp.tool()
    async def get_type_weaknesses(pokemon: str) -> dict:
        """Get type weaknesses and resistances for a Pokemon.

        Args:
            pokemon: Pokemon name

        Returns:
            Detailed type matchup info (4x weak, 2x weak, resists, immunities)
        """
        return get_pokemon_weaknesses(pokemon)

    @mcp.tool()
    async def analyze_team_type_coverage(pokemon_list: list[str]) -> dict:
        """Analyze type weaknesses and coverage for a team of Pokemon.

        Args:
            pokemon_list: List of Pokemon names on the team

        Returns:
            Team type analysis including shared weaknesses and unresisted types
        """
        return analyze_team_types(pokemon_list)

    @mcp.tool()
    async def get_pokemon_base_stats(pokemon: str) -> dict:
        """Get base stats for a Pokemon.

        Args:
            pokemon: Pokemon name

        Returns:
            Base stats (HP, Atk, Def, SpA, SpD, Spe)
        """
        base = get_base_stats(pokemon)
        if not base:
            return {"error": f"Pokemon '{pokemon}' not found"}

        types = get_pokemon_types(pokemon)

        return {
            "pokemon": pokemon,
            "types": types,
            "base_stats": base,
            "bst": sum(base.values()),
        }

    @mcp.tool()
    async def analyze_move_coverage(move_types: list[str]) -> dict:
        """Analyze offensive type coverage of a moveset.

        Args:
            move_types: List of move types (e.g., ["Fire", "Fighting", "Dark"])

        Returns:
            Coverage analysis showing what types are hit super-effectively
        """
        return get_offensive_coverage(move_types)
