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
from smogon_vgc_mcp.utils import make_error_response

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
        """Generate an optimized EV spread for specific goals.

        This tool takes a Pokemon and a list of goals (in priority order) and
        generates an EV spread that attempts to achieve all goals within the
        510 EV limit. Goals are processed in order - earlier goals have higher priority.

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane")
            goals: List of goal dicts in priority order (first = highest priority).
                Each goal must have a "type" field. Goal types and required fields:

                SURVIVE - Survive a specific attack:
                  Required: {"type": "survive", "attacker": str, "move": str}
                  Optional: attacker_evs (default "252/0/0/252/0/0"),
                            attacker_nature (default "Modest"),
                            attacker_item, attacker_ability, attacker_tera,
                            weather ("Sun"/"Rain"/"Sand"/"Snow"),
                            terrain ("Grassy"/"Electric"/"Psychic"/"Misty")

                OHKO - Guarantee OHKO on a target:
                  Required: {"type": "ohko", "defender": str, "move": str}
                  Optional: defender_evs (default "252/0/0/0/0/0"),
                            defender_nature (default "Bold"),
                            defender_item, defender_ability

                OUTSPEED - Outspeed a target Pokemon:
                  Required: {"type": "outspeed", "target": str}
                  Optional: target_evs (default "0/0/0/0/0/252"),
                            target_nature (default "Timid")

                UNDERSPEED - Underspeed a target (Trick Room):
                  Required: {"type": "underspeed", "target": str}
                  Optional: target_evs (default "0/0/0/0/0/0"),
                            target_nature (default "Brave")

                MAXIMIZE - Invest remaining EVs in a stat:
                  Required: {"type": "maximize", "stat": "hp"|"atk"|"def"|"spa"|"spd"|"spe"}

            nature: Preferred nature. If None, auto-selected based on goals
                (e.g., "Adamant" +Atk/-SpA, "Modest" +SpA/-Atk, "Careful" +SpD/-SpA)
            item: Held item (e.g., "Assault Vest", "Choice Specs", "Life Orb")
            ability: Pokemon's ability (e.g., "Intimidate", "Protosynthesis")
            tera_type: Tera type for defensive calcs (e.g., "Fairy", "Ghost", "Water")

        Returns:
            Optimized spread with goal results, calculated stats, and suggestions
        """
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
        """Find minimum defensive EVs needed to survive a specific attack.

        This tool calculates the minimum HP + defensive stat investment needed
        to guarantee survival against a specific attack.

        Args:
            pokemon: Defending Pokemon name (e.g., "Incineroar")
            attacker: Attacking Pokemon name (e.g., "Flutter Mane")
            move: Move being used (e.g., "Moonblast")
            pokemon_nature: Defender's nature. Default "Careful" (+SpD/-SpA)
                is common for specially defensive Pokemon
            attacker_evs: Attacker's EV spread as "HP/Atk/Def/SpA/SpD/Spe"
            attacker_nature: Attacker's nature. Default "Modest" (+SpA/-Atk)
                assumes max special attack investment
            attacker_item: Attacker's held item (e.g., "Choice Specs", "Life Orb")
            attacker_ability: Attacker's ability (e.g., "Protosynthesis")
            pokemon_item: Defender's held item (e.g., "Assault Vest", "Sitrus Berry")
            pokemon_ability: Defender's ability (e.g., "Intimidate", "Thick Fat")
            attacker_tera: Attacker's Tera type if active (e.g., "Fairy")
            weather: Active weather: "Sun", "Rain", "Sand", or "Snow"
            terrain: Active terrain: "Grassy", "Electric", "Psychic", or "Misty"

        Returns:
            Minimum EVs needed and damage range after investment
        """
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
        """Find minimum offensive EVs needed to OHKO a specific target.

        This tool calculates the minimum Attack or Special Attack EVs needed
        to guarantee an OHKO against a specific target.

        Args:
            pokemon: Attacking Pokemon name (e.g., "Flutter Mane")
            defender: Defending Pokemon name (e.g., "Incineroar")
            move: Move to use (e.g., "Moonblast")
            pokemon_nature: Attacker's nature. Default "Modest" (+SpA/-Atk)
                for special attackers. Use "Adamant" (+Atk/-SpA) for physical
            defender_evs: Defender's EV spread as "HP/Atk/Def/SpA/SpD/Spe"
            defender_nature: Defender's nature. Default "Bold" (+Def/-Atk)
                assumes physically defensive target
            pokemon_item: Attacker's held item (e.g., "Choice Specs", "Life Orb")
            pokemon_ability: Attacker's ability (e.g., "Protosynthesis")
            defender_item: Defender's held item (e.g., "Assault Vest")
            defender_ability: Defender's ability (e.g., "Intimidate")

        Returns:
            Minimum EVs needed and damage range
        """
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
        """Find Speed EVs needed to outspeed or underspeed a target.

        Args:
            pokemon: Pokemon to calculate for (e.g., "Incineroar")
            target: Target Pokemon to compare against (e.g., "Flutter Mane")
            goal_type: "outspeed" to be faster, "underspeed" for Trick Room
            pokemon_nature: Pokemon's nature. Default "Jolly" (+Spe/-SpA)
                for outspeeding. Use "Brave" (+Atk/-Spe) for underspeeding
            target_evs: Target's EV spread as "HP/Atk/Def/SpA/SpD/Spe"
            target_nature: Target's nature (e.g., "Timid" +Spe/-Atk, "Jolly" +Spe/-SpA)

        Returns:
            EVs needed and resulting speed stats
        """
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
