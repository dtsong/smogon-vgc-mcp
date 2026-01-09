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
        """Calculate exact stat values for a Pokemon with specific EVs, IVs, nature, and level.

        Use this when you need actual stat numbers (e.g., "what's my Incineroar's HP?").
        For base stats only, use dex_pokemon. For damage calculations, use calculate_damage.

        Returns: pokemon, level, nature, evs, ivs, base_stats{}, calculated_stats{hp/atk/def/
        spa/spd/spe}, formatted (string summary).

        Examples:
        - "What are Flutter Mane's stats with 252 SpA / 252 Spe Timid?"
        - "Calculate Incineroar's HP with 244 HP EVs"

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane").
            evs: EV spread "HP/Atk/Def/SpA/SpD/Spe" (e.g., "252/4/0/0/0/252"). Max 252 each.
            nature: Nature name (e.g., "Adamant", "Timid"). "Hardy" for neutral.
            ivs: IV spread "HP/Atk/Def/SpA/SpD/Spe". Default "31/31/31/31/31/31".
            level: Pokemon level. Default 50 (VGC standard).
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
        """Compare speed stats between two specific Pokemon builds to see who outspeeds.

        Use this for head-to-head speed comparisons with known spreads. For finding what
        Pokemon a speed stat beats in general, use get_speed_benchmarks. For finding Speed
        EVs needed to outspeed a target, use find_speed_evs.

        Returns: pokemon1 name/speed, pokemon2 name/speed, result (faster/slower/tie),
        speed_difference.

        Examples:
        - "Does max speed Flutter Mane outspeed Adamant Urshifu?"
        - "Compare Modest Torkoal speed vs Jolly Arcanine"

        Args:
            pokemon1: First Pokemon name.
            evs1: First Pokemon's EV spread (e.g., "252/0/0/0/0/252").
            nature1: First Pokemon's nature.
            pokemon2: Second Pokemon name.
            evs2: Second Pokemon's EV spread.
            nature2: Second Pokemon's nature.
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
        """Find what notable VGC Pokemon a given speed stat outspeeds or underspeeds.

        Use this to see where a speed stat fits in the metagame. For comparing two specific
        Pokemon, use compare_pokemon_speeds. For finding EVs to outspeed a target, use
        find_speed_evs.

        Returns: pokemon, speed_stat, outspeeds[] (Pokemon you're faster than),
        underspeeds[] (Pokemon faster than you), speed_ties[].

        Examples:
        - "What does 150 speed outspeed in VGC?"
        - "What can max speed Kingambit outspeed?"

        Args:
            pokemon: Pokemon name.
            evs: EV spread (e.g., "0/0/0/0/0/252" for max speed).
            nature: Nature name (e.g., "Jolly" for +Spe).
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
        """Analyze a team's shared type weaknesses and resistances to find defensive holes.

        Use this to identify team weaknesses (e.g., "team is 4x weak to Ground"). For a
        single Pokemon's weaknesses, use dex_pokemon_weaknesses. For offensive move
        coverage, use analyze_move_coverage.

        Returns: team[], shared_weaknesses{type: count}, shared_resistances{},
        unresisted_types[], pokemon_details[] with individual weaknesses.

        Examples:
        - "What are my team's shared weaknesses?"
        - "Does my team have good defensive coverage?"

        Args:
            pokemon_list: List of 1-6 Pokemon names (e.g., ["Incineroar", "Flutter Mane"]).
        """
        try:
            validate_pokemon_list(pokemon_list, min_size=1, max_size=6)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        return analyze_team_types(pokemon_list)

    @mcp.tool()
    async def analyze_move_coverage(move_types: list[str]) -> dict:
        """Analyze what types a set of move types hits super-effectively.

        Use this to evaluate offensive coverage of a moveset. For defensive analysis
        (weaknesses/resistances), use dex_pokemon_weaknesses or analyze_team_type_coverage.
        For actual damage numbers, use calculate_damage.

        Returns: move_types[], super_effective_against[], not_very_effective_against[],
        no_effect_against[], coverage_score.

        Examples:
        - "What does Fire/Fighting/Dark coverage hit?"
        - "How good is Urshifu's type coverage with Water/Fighting/Dark?"

        Args:
            move_types: List of 1-4 move types (e.g., ["Fire", "Fighting", "Dark"]).
        """
        try:
            validate_type_list(move_types, min_size=1, max_size=4)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        return get_offensive_coverage(move_types)
