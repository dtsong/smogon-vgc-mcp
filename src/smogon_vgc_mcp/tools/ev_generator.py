"""EV spread generation tools for MCP server."""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.calculator.ev_optimizer import (
    MaximizeGoal,
    OHKOGoal,
    OutspeedGoal,
    SurviveGoal,
    UnderspeedGoal,
    evs_to_string,
    find_ohko_evs,
    find_speed_evs_to_outspeed,
    find_speed_evs_to_underspeed,
    find_survival_evs,
    optimize_spread,
)
from smogon_vgc_mcp.calculator.stats import format_stats
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    validate_ev_spread,
    validate_nature,
    validate_pokemon_name,
    validate_terrain,
    validate_type_name,
    validate_weather,
)

Goal = SurviveGoal | OHKOGoal | OutspeedGoal | UnderspeedGoal | MaximizeGoal


def _parse_goal(goal_dict: dict[str, Any]) -> Goal | None:
    """Parse a goal dictionary into a Goal object."""
    goal_type = goal_dict.get("type", "").lower()

    if goal_type == "survive":
        return SurviveGoal(
            attacker=goal_dict.get("attacker", ""),
            move=goal_dict.get("move", ""),
            attacker_evs=goal_dict.get("attacker_evs", "252/0/0/252/0/0"),
            attacker_nature=goal_dict.get("attacker_nature", "Modest"),
            attacker_item=goal_dict.get("attacker_item"),
            attacker_ability=goal_dict.get("attacker_ability"),
            attacker_tera=goal_dict.get("attacker_tera"),
            field_weather=goal_dict.get("weather"),
            field_terrain=goal_dict.get("terrain"),
            attacker_boosts=goal_dict.get("attacker_boosts"),
        )

    if goal_type == "ohko":
        return OHKOGoal(
            defender=goal_dict.get("defender", ""),
            move=goal_dict.get("move", ""),
            defender_evs=goal_dict.get("defender_evs", "252/0/0/0/0/0"),
            defender_nature=goal_dict.get("defender_nature", "Bold"),
            defender_item=goal_dict.get("defender_item"),
            defender_ability=goal_dict.get("defender_ability"),
        )

    if goal_type == "outspeed":
        return OutspeedGoal(
            target=goal_dict.get("target", ""),
            target_evs=goal_dict.get("target_evs", "0/0/0/0/0/252"),
            target_nature=goal_dict.get("target_nature", "Timid"),
        )

    if goal_type == "underspeed":
        return UnderspeedGoal(
            target=goal_dict.get("target", ""),
            target_evs=goal_dict.get("target_evs", "0/0/0/0/0/0"),
            target_nature=goal_dict.get("target_nature", "Brave"),
        )

    if goal_type == "maximize":
        stat = goal_dict.get("stat", "hp").lower()
        if stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            return MaximizeGoal(stat=stat)

    return None


def register_ev_generator_tools(mcp: FastMCP) -> None:
    """Register EV generation tools with the MCP server."""

    @mcp.tool()
    async def suggest_ev_spread(
        pokemon: str,
        goals: list[dict[str, Any]],
        nature: str | None = None,
        item: str | None = None,
        ability: str | None = None,
        tera_type: str | None = None,
    ) -> dict:
        """Generate an optimized EV spread for a Pokemon based on multiple prioritized goals.

        Use this for full EV spread optimization with multiple requirements (survive X, OHKO Y,
        outspeed Z). For single-purpose calculations, use find_minimum_survival_evs,
        find_minimum_ohko_evs, or find_speed_evs instead.

        Returns: pokemon, spread{nature, evs, evs_compact, ivs}, calculated_stats,
        goal_results[]{goal, achieved, evs_used, detail}, ev_total, suggestions.

        Examples:
        - "Build Incineroar to survive Flutter Mane Moonblast and maximize HP"
        - "Create Urshifu spread that OHKOs Incineroar and outspeeds Rillaboom"

        Constraints: Goals processed in priority order (first = highest). 510 EV limit enforced.

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane").
            goals: List of goal dicts in priority order. Goal types:
                SURVIVE: {"type": "survive", "attacker": str, "move": str}
                  Optional: attacker_evs, attacker_nature, attacker_item, attacker_ability,
                  attacker_tera, weather, terrain
                OHKO: {"type": "ohko", "defender": str, "move": str}
                  Optional: defender_evs, defender_nature, defender_item, defender_ability
                OUTSPEED: {"type": "outspeed", "target": str}
                  Optional: target_evs, target_nature
                UNDERSPEED: {"type": "underspeed", "target": str}
                  Optional: target_evs, target_nature
                MAXIMIZE: {"type": "maximize", "stat": "hp"|"atk"|"def"|"spa"|"spd"|"spe"}
            nature: Preferred nature (auto-selected if None).
            item: Held item for calculations.
            ability: Pokemon's ability.
            tera_type: Tera type for defensive calculations.
        """
        try:
            validate_pokemon_name(pokemon)
            if nature:
                validate_nature(nature)
            if tera_type:
                validate_type_name(tera_type)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        parsed_goals = []
        for goal_dict in goals:
            goal = _parse_goal(goal_dict)
            if goal:
                parsed_goals.append(goal)

        if not parsed_goals:
            return make_error_response(
                "No valid goals provided",
                hint="Goals must have a 'type' field "
                "(survive, ohko, outspeed, underspeed, maximize)",
            )

        result = optimize_spread(
            pokemon=pokemon,
            goals=parsed_goals,
            nature=nature,
            item=item,
            ability=ability,
            tera_type=tera_type,
        )

        stat_order = ["hp", "atk", "def", "spa", "spd", "spe"]
        evs_compact = "/".join(str(result.evs.get(s, 0)) for s in stat_order)
        ivs_str = "/".join(str(result.ivs.get(s, 31)) for s in stat_order)
        formatted = format_stats(result.calculated_stats) if result.calculated_stats else None

        return {
            "pokemon": result.pokemon,
            "spread": {
                "nature": result.nature,
                "evs": evs_to_string(result.evs),
                "evs_compact": evs_compact,
                "ivs": ivs_str,
            },
            "calculated_stats": result.calculated_stats,
            "formatted_stats": formatted,
            "goal_results": [
                {
                    "goal": gr.goal_description,
                    "achieved": gr.achieved,
                    "evs_used": gr.evs_used,
                    "detail": gr.detail,
                }
                for gr in result.goal_results
            ],
            "ev_total": f"{result.ev_total}/510",
            "suggestions": result.suggestions if result.suggestions else None,
        }

    @mcp.tool()
    async def find_minimum_survival_evs(
        pokemon: str,
        attacker: str,
        move: str,
        pokemon_nature: str = "Careful",
        attacker_evs: str = "252/0/0/252/0/0",
        attacker_nature: str = "Modest",
        attacker_item: str | None = None,
        attacker_ability: str | None = None,
        pokemon_item: str | None = None,
        pokemon_ability: str | None = None,
        attacker_tera: str | None = None,
        weather: str | None = None,
        terrain: str | None = None,
    ) -> dict:
        """Find minimum HP + defensive EVs needed to survive a specific attack.

        Use this when you need exact investment to survive one attack. For optimizing
        a full spread with multiple goals, use suggest_ev_spread instead.

        Returns: pokemon, attacker, move, minimum_evs{}, evs_formatted, damage_range,
        defense_stat_invested, total_defensive_evs.

        Examples:
        - "What EVs does Incineroar need to survive Flutter Mane Moonblast?"
        - "How much SpD does Rillaboom need to live Kyogre Water Spout?"

        Args:
            pokemon: Defending Pokemon name.
            attacker: Attacking Pokemon name.
            move: Attack to survive.
            pokemon_nature: Defender's nature (default "Careful" for SpD).
            attacker_evs: Attacker's spread (default max SpA "252/0/0/252/0/0").
            attacker_nature: Attacker's nature (default "Modest").
            attacker_item: Attacker's item (e.g., "Choice Specs").
            attacker_ability: Attacker's ability.
            pokemon_item: Defender's item (e.g., "Assault Vest").
            pokemon_ability: Defender's ability.
            attacker_tera: Attacker's Tera type if active.
            weather: Active weather ("Sun", "Rain", "Sand", "Snow").
            terrain: Active terrain ("Grassy", "Electric", "Psychic", "Misty").
        """
        try:
            validate_pokemon_name(pokemon)
            validate_pokemon_name(attacker)
            validate_nature(pokemon_nature)
            validate_nature(attacker_nature)
            validate_ev_spread(attacker_evs)
            if attacker_tera:
                validate_type_name(attacker_tera)
            validate_weather(weather)
            validate_terrain(terrain)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        goal = SurviveGoal(
            attacker=attacker,
            move=move,
            attacker_evs=attacker_evs,
            attacker_nature=attacker_nature,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            attacker_tera=attacker_tera,
            field_weather=weather,
            field_terrain=terrain,
        )

        result = find_survival_evs(pokemon, pokemon_nature, pokemon_item, pokemon_ability, goal)

        if not result.get("success"):
            return make_error_response(
                result.get("error", "Could not find survival EVs"),
                hint="Try adding defensive items like Assault Vest or boosting defensive nature",
            )

        return {
            "pokemon": pokemon,
            "attacker": attacker,
            "move": move,
            "minimum_evs": result["evs"],
            "evs_formatted": evs_to_string(result["evs"]),
            "damage_range": result["damage_range"],
            "defense_stat_invested": result["defense_stat"],
            "total_defensive_evs": result["total_defensive_evs"],
        }

    @mcp.tool()
    async def find_minimum_ohko_evs(
        pokemon: str,
        defender: str,
        move: str,
        pokemon_nature: str = "Modest",
        defender_evs: str = "252/0/0/0/0/0",
        defender_nature: str = "Bold",
        pokemon_item: str | None = None,
        pokemon_ability: str | None = None,
        defender_item: str | None = None,
        defender_ability: str | None = None,
    ) -> dict:
        """Find minimum Attack or Special Attack EVs needed to OHKO a specific target.

        Use this when you need exact offensive investment for an OHKO. For optimizing
        a full spread with multiple goals, use suggest_ev_spread instead.

        Returns: pokemon, defender, move, minimum_evs{}, evs_formatted, damage_range,
        guaranteed_ohko, attack_stat_invested.

        Examples:
        - "What SpA EVs does Flutter Mane need to OHKO Incineroar?"
        - "Can Urshifu OHKO Rillaboom with minimal Attack investment?"

        Args:
            pokemon: Attacking Pokemon name.
            defender: Target Pokemon name.
            move: Move to use.
            pokemon_nature: Attacker's nature (default "Modest" for SpA, "Adamant" for Atk).
            defender_evs: Defender's spread (default "252/0/0/0/0/0").
            defender_nature: Defender's nature (default "Bold").
            pokemon_item: Attacker's item.
            pokemon_ability: Attacker's ability.
            defender_item: Defender's item.
            defender_ability: Defender's ability.
        """
        try:
            validate_pokemon_name(pokemon)
            validate_pokemon_name(defender)
            validate_nature(pokemon_nature)
            validate_nature(defender_nature)
            validate_ev_spread(defender_evs)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        goal = OHKOGoal(
            defender=defender,
            move=move,
            defender_evs=defender_evs,
            defender_nature=defender_nature,
            defender_item=defender_item,
            defender_ability=defender_ability,
        )

        result = find_ohko_evs(pokemon, pokemon_nature, pokemon_item, pokemon_ability, goal)

        if not result.get("success"):
            max_dmg = result.get("max_damage", "unknown")
            return make_error_response(
                result.get("error", "Could not find OHKO EVs"),
                hint=f"Max damage: {max_dmg}. Consider boosting items or abilities.",
            )

        return {
            "pokemon": pokemon,
            "defender": defender,
            "move": move,
            "minimum_evs": result["evs"],
            "evs_formatted": evs_to_string(result["evs"]),
            "damage_range": result["damage_range"],
            "guaranteed_ohko": result["guaranteed_ohko"],
            "attack_stat_invested": result["attack_stat"],
        }

    @mcp.tool()
    async def find_speed_evs(
        pokemon: str,
        target: str,
        goal_type: Literal["outspeed", "underspeed"] = "outspeed",
        pokemon_nature: str = "Jolly",
        target_evs: str = "0/0/0/0/0/252",
        target_nature: str = "Timid",
    ) -> dict:
        """Find Speed EVs needed to outspeed or underspeed a specific target Pokemon.

        Use this for speed tier calculations. For comparing speeds of specific builds,
        use compare_pokemon_speeds. For what a speed stat beats in general, use
        get_speed_benchmarks.

        Returns: pokemon, target, goal (outspeed/underspeed), speed_evs_needed,
        resulting_speed, target_speed, margin.

        Examples:
        - "How much Speed does Incineroar need to outspeed Amoonguss?"
        - "What Speed EVs for Torkoal to underspeed Dondozo in Trick Room?"

        Args:
            pokemon: Pokemon to calculate EVs for.
            target: Target Pokemon to compare against.
            goal_type: "outspeed" (be faster) or "underspeed" (Trick Room).
            pokemon_nature: Pokemon's nature (default "Jolly", use "Brave" for underspeed).
            target_evs: Target's EV spread.
            target_nature: Target's nature.
        """
        try:
            validate_pokemon_name(pokemon)
            validate_pokemon_name(target)
            validate_nature(pokemon_nature)
            validate_nature(target_nature)
            validate_ev_spread(target_evs)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        if goal_type.lower() == "underspeed":
            result = find_speed_evs_to_underspeed(
                pokemon, target, target_evs, target_nature, pokemon_nature, 0
            )
        else:
            result = find_speed_evs_to_outspeed(
                pokemon, target, target_evs, target_nature, pokemon_nature, 31
            )

        if not result.get("success"):
            return make_error_response(
                result.get("error", "Could not calculate speed EVs"),
                hint="Consider changing nature or using speed-modifying items",
            )

        return {
            "pokemon": pokemon,
            "target": target,
            "goal": goal_type,
            "speed_evs_needed": result["evs"],
            "resulting_speed": result["speed"],
            "target_speed": result["target_speed"],
            "margin": result["margin"],
        }
