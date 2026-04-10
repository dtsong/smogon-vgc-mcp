"""Champions format calculator tools for MCP server (stats, speed, SP optimizer)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.calculator.champions_sp_optimizer import (
    HpThresholdGoal,
    MaximizeGoal,
    SpeedGoal,
    optimize_champions_sp,
)
from smogon_vgc_mcp.calculator.champions_speed import (
    compare_champions_speeds as _compare_speeds,
)
from smogon_vgc_mcp.calculator.champions_speed import (
    find_champions_speed_benchmarks,
    get_champions_speed,
)
from smogon_vgc_mcp.calculator.champions_stats import (
    MAX_SP_PER_STAT,
    MAX_TOTAL_SP,
    STAT_ORDER,
    calculate_all_champions_stats,
    format_champions_stats,
)
from smogon_vgc_mcp.database.models import ChampionsDexPokemon
from smogon_vgc_mcp.database.queries import get_champions_pokemon
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    normalize_pokemon_id,
    validate_nature,
)


async def _get_champions_base_stats(pokemon_id: str) -> ChampionsDexPokemon | None:
    """Look up a Champions Pokemon from the dex database."""
    return await get_champions_pokemon(pokemon_id)


def _parse_sp_spread(sp_string: str) -> dict[str, int] | str:
    """Parse 'HP/Atk/Def/SpA/SpD/Spe' SP string into dict.

    Returns dict on success, error string on failure.
    Validates: 6 values, all integers, each 0-32, total <= 66.
    """
    parts = sp_string.split("/")
    if len(parts) != 6:
        return f"SP spread must have 6 values separated by '/', got {len(parts)}"

    values: list[int] = []
    for i, part in enumerate(parts):
        part = part.strip()
        try:
            val = int(part)
        except ValueError:
            return f"SP value '{part}' at position {i + 1} is not an integer"
        if val < 0 or val > MAX_SP_PER_STAT:
            return f"SP value {val} at position {i + 1} must be 0-{MAX_SP_PER_STAT}"
        values.append(val)

    total = sum(values)
    if total > MAX_TOTAL_SP:
        return f"Total SP ({total}) exceeds maximum ({MAX_TOTAL_SP})"

    return dict(zip(STAT_ORDER, values))


def register_champions_calculator_tools(mcp: FastMCP) -> None:
    """Register Champions format calculator tools with the MCP server."""

    @mcp.tool()
    async def calculate_champions_stats(
        pokemon: str,
        sp_spread: str,
        nature: str = "Hardy",
        level: int = 50,
    ) -> dict:
        """Calculate stats for a Pokemon in Champions format using SP (Skill Points).

        Champions uses SP instead of EVs: 0-32 per stat, 66 total budget.

        Returns: pokemon, level, nature, sp_spread, base_stats, calculated_stats, formatted.

        Examples:
        - "What are Venusaur's stats with 0/0/0/32/0/2 Modest in Champions?"
        - "Calculate Incineroar Champions stats with 10/0/10/0/10/0"

        Args:
            pokemon: Pokemon name (e.g., "Venusaur", "Mega Charizard X").
            sp_spread: SP spread "HP/Atk/Def/SpA/SpD/Spe" (e.g., "0/0/0/32/0/2").
                Max 32 each, 66 total.
            nature: Nature name (e.g., "Modest", "Timid"). "Hardy" for neutral.
            level: Pokemon level. Default 50 (Champions standard).
        """
        parsed = _parse_sp_spread(sp_spread)
        if isinstance(parsed, str):
            return make_error_response(
                parsed,
                hint="Format: 'HP/Atk/Def/SpA/SpD/Spe', e.g. '0/0/0/32/0/2'",
            )

        pokemon_id = normalize_pokemon_id(pokemon)
        dex_entry = await _get_champions_base_stats(pokemon_id)
        if not dex_entry:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Champions dex",
                hint="Check spelling or try the full name (e.g., 'Mega Charizard X')",
            )

        stats = calculate_all_champions_stats(dex_entry.base_stats, parsed, nature, level)
        if stats is None:
            return make_error_response(
                f"Invalid nature '{nature}'",
                hint="Use a valid nature name like 'Adamant', 'Modest', or 'Hardy' for neutral",
            )

        return {
            "pokemon": dex_entry.name,
            "level": level,
            "nature": nature,
            "sp_spread": sp_spread,
            "base_stats": dex_entry.base_stats,
            "calculated_stats": stats,
            "formatted": format_champions_stats(stats),
        }

    @mcp.tool()
    async def compare_champions_speeds(
        pokemon1: str,
        sp1: int,
        nature1: str,
        pokemon2: str,
        sp2: int,
        nature2: str,
    ) -> dict:
        """Compare speeds of two Pokemon in Champions format.

        Returns: pokemon1 {name, speed}, pokemon2 {name, speed}, result, difference.

        Examples:
        - "Does max speed Mega Gengar outspeed Dragapult in Champions?"
        - "Compare Jolly Dragonite +10 SP vs Timid Hydreigon +5 SP"

        Args:
            pokemon1: First Pokemon name.
            sp1: First Pokemon's Speed SP (0-32).
            nature1: First Pokemon's nature.
            pokemon2: Second Pokemon name.
            sp2: Second Pokemon's Speed SP (0-32).
            nature2: Second Pokemon's nature.
        """
        # Validate inputs before DB lookups
        for label, sp_val in [("sp1", sp1), ("sp2", sp2)]:
            if sp_val < 0 or sp_val > MAX_SP_PER_STAT:
                return make_error_response(
                    f"{label} must be 0-{MAX_SP_PER_STAT}, got {sp_val}",
                )
        try:
            validate_nature(nature1)
            validate_nature(nature2)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        pokemon1_id = normalize_pokemon_id(pokemon1)
        pokemon2_id = normalize_pokemon_id(pokemon2)

        dex1 = await _get_champions_base_stats(pokemon1_id)
        if not dex1:
            return make_error_response(
                f"Pokemon '{pokemon1}' not found in Champions dex",
                hint="Check spelling or try the full name",
            )

        dex2 = await _get_champions_base_stats(pokemon2_id)
        if not dex2:
            return make_error_response(
                f"Pokemon '{pokemon2}' not found in Champions dex",
                hint="Check spelling or try the full name",
            )

        return _compare_speeds(
            dex1.name,
            dex1.base_stats["spe"],
            sp1,
            nature1,
            dex2.name,
            dex2.base_stats["spe"],
            sp2,
            nature2,
        )

    @mcp.tool()
    async def get_champions_speed_benchmarks(
        pokemon: str,
        sp: int = 0,
        nature: str = "Hardy",
    ) -> dict:
        """Find what Champions meta Pokemon a speed stat outspeeds or underspeeds.

        Returns: pokemon, speed, outspeeds[], underspeeds[], speed_ties[].

        Examples:
        - "What does max speed Mega Lucario outspeed in Champions?"
        - "Where does Incineroar sit in Champions speed tiers?"

        Args:
            pokemon: Pokemon name.
            sp: Speed SP allocation (0-32). Default 0.
            nature: Nature name (e.g., "Jolly" for +Spe). Default "Hardy".
        """
        # Validate inputs before DB lookup
        if sp < 0 or sp > MAX_SP_PER_STAT:
            return make_error_response(f"SP must be 0-{MAX_SP_PER_STAT}, got {sp}")
        try:
            validate_nature(nature)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        pokemon_id = normalize_pokemon_id(pokemon)
        dex_entry = await _get_champions_base_stats(pokemon_id)
        if not dex_entry:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Champions dex",
                hint="Check spelling or try the full name",
            )

        speed = get_champions_speed(dex_entry.base_stats["spe"], sp, nature)
        return find_champions_speed_benchmarks(dex_entry.name, speed)

    @mcp.tool()
    async def suggest_champions_sp_spread(
        pokemon: str,
        nature: str,
        goals: list[dict[str, Any]],
        item: str | None = None,
    ) -> dict:
        """Generate an optimized SP spread based on priority-ordered goals.

        Goals are processed in order. Each goal type:
        - Speed: {"type": "speed", "target_speed": int, "mode": "outspeed"|"underspeed"}
        - HP threshold: {"type": "hp", "item": "Leftovers"|"Life Orb"|"Sitrus Berry"}
        - Maximize stat: {"type": "maximize", "stat": "spa"|"atk"|"spe"|etc.}

        Returns: success, sp_spread, remaining_sp, total_sp,
        goal_results, calculated_stats, formatted.

        Examples:
        - "Optimize Venusaur to outspeed 150, then maximize SpA"
        - "Spread for Incineroar with Sitrus Berry HP, then max Def"

        Args:
            pokemon: Pokemon name.
            nature: Nature name.
            goals: List of goal dicts processed in priority order.
            item: Optional held item for HP threshold calculations.
        """
        pokemon_id = normalize_pokemon_id(pokemon)
        dex_entry = await _get_champions_base_stats(pokemon_id)
        if not dex_entry:
            return make_error_response(
                f"Pokemon '{pokemon}' not found in Champions dex",
                hint="Check spelling or try the full name",
            )

        parsed_goals: list[SpeedGoal | HpThresholdGoal | MaximizeGoal] = []
        for i, g in enumerate(goals):
            goal_type = g.get("type")
            if goal_type == "speed":
                target = g.get("target_speed")
                if target is None:
                    return make_error_response(
                        f"Goal {i + 1}: speed goal requires 'target_speed'",
                    )
                mode = g.get("mode", "outspeed")
                parsed_goals.append(SpeedGoal(target_speed=int(target), mode=mode))
            elif goal_type == "hp":
                hp_item = g.get("item", item)
                if hp_item is None:
                    return make_error_response(
                        f"Goal {i + 1}: hp goal requires 'item' (in goal or tool arg)",
                    )
                parsed_goals.append(HpThresholdGoal(item=hp_item))
            elif goal_type == "maximize":
                stat = g.get("stat")
                if stat is None or stat not in STAT_ORDER:
                    return make_error_response(
                        f"Goal {i + 1}: maximize goal requires 'stat' (one of {STAT_ORDER})",
                    )
                parsed_goals.append(MaximizeGoal(stat=stat))
            else:
                return make_error_response(
                    f"Goal {i + 1}: unknown goal type '{goal_type}'",
                    hint="Valid types: 'speed', 'hp', 'maximize'",
                )

        result = optimize_champions_sp(dex_entry.base_stats, nature, parsed_goals)

        # Calculate final stats with the optimized spread
        final_stats = calculate_all_champions_stats(
            dex_entry.base_stats,
            result["sp_spread"],
            nature,
        )

        result["pokemon"] = dex_entry.name
        result["nature"] = nature
        if final_stats:
            result["calculated_stats"] = final_stats
            result["formatted"] = format_champions_stats(final_stats)

        return result
