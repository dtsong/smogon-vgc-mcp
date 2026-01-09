"""EV spread optimization for VGC teambuilding."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from smogon_vgc_mcp.calculator.damage import calculate_damage_simple
from smogon_vgc_mcp.calculator.speed_tiers import get_speed_stat
from smogon_vgc_mcp.calculator.stats import calculate_all_stats, calculate_stat
from smogon_vgc_mcp.data.pokemon_data import get_base_stats, get_nature_multiplier

MAX_EVS = 510
MAX_SINGLE_EV = 252
EV_STEP = 4

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]


@dataclass
class SurviveGoal:
    """Goal: Survive an attack from a specific Pokemon."""

    attacker: str
    move: str
    attacker_evs: str = "252/0/0/252/0/0"
    attacker_nature: str = "Modest"
    attacker_item: str | None = None
    attacker_ability: str | None = None
    attacker_tera: str | None = None
    field_weather: str | None = None
    field_terrain: str | None = None
    attacker_boosts: dict[str, int] | None = None


@dataclass
class OHKOGoal:
    """Goal: OHKO a specific Pokemon with a move."""

    defender: str
    move: str
    defender_evs: str = "252/0/0/0/0/0"
    defender_nature: str = "Bold"
    defender_item: str | None = None
    defender_ability: str | None = None


@dataclass
class OutspeedGoal:
    """Goal: Outspeed a specific Pokemon."""

    target: str
    target_evs: str = "0/0/0/0/0/252"
    target_nature: str = "Timid"


@dataclass
class UnderspeedGoal:
    """Goal: Underspeed a specific Pokemon (for Trick Room)."""

    target: str
    target_evs: str = "0/0/0/0/0/0"
    target_nature: str = "Brave"


@dataclass
class MaximizeGoal:
    """Goal: Maximize a specific stat with remaining EVs."""

    stat: str


@dataclass
class GoalResult:
    """Result of attempting to achieve a goal."""

    goal_description: str
    achieved: bool
    evs_used: dict[str, int]
    detail: str


@dataclass
class OptimizedSpread:
    """Result of EV spread optimization."""

    pokemon: str
    nature: str
    evs: dict[str, int]
    ivs: dict[str, int]
    calculated_stats: dict[str, int]
    goal_results: list[GoalResult]
    ev_total: int
    suggestions: list[str] = field(default_factory=list)


STAT_NAMES = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}


def evs_to_string(evs: dict[str, int]) -> str:
    """Convert EV dict to readable string format."""
    parts = []
    for stat in STAT_ORDER:
        ev = evs.get(stat, 0)
        if ev > 0:
            parts.append(f"{ev} {STAT_NAMES[stat]}")
    return " / ".join(parts) if parts else "0 HP"


def evs_to_compact(evs: dict[str, int]) -> str:
    """Convert EV dict to compact string format."""
    return "/".join(str(evs.get(stat, 0)) for stat in STAT_ORDER)


def evs_for_stat_target(
    base: int,
    target_stat: int,
    iv: int = 31,
    nature_mult: float = 1.0,
    level: int = 50,
    is_hp: bool = False,
) -> int | None:
    """Calculate EVs needed to reach a target stat value.

    Returns the minimum EVs (rounded up to nearest 4) needed, or None if impossible.
    """
    if is_hp:
        raw_target = (target_stat - level - 10) * 100 / level
        ev_needed = (raw_target - 2 * base - iv) * 4
    else:
        raw_before_nature = target_stat / nature_mult
        raw_target = (math.ceil(raw_before_nature) - 5) * 100 / level
        ev_needed = (raw_target - 2 * base - iv) * 4

    if ev_needed < 0:
        return 0
    if ev_needed > MAX_SINGLE_EV:
        return None

    return min(MAX_SINGLE_EV, ((int(ev_needed) + EV_STEP - 1) // EV_STEP) * EV_STEP)


def find_speed_evs_to_outspeed(
    pokemon: str,
    target_pokemon: str,
    target_evs: str,
    target_nature: str,
    pokemon_nature: str = "Hardy",
    pokemon_iv: int = 31,
) -> dict[str, Any]:
    """Find minimum Speed EVs to outspeed a target Pokemon."""
    target_speed = get_speed_stat(target_pokemon, target_evs, None, target_nature)
    if target_speed is None:
        return {"success": False, "error": f"Could not calculate speed for {target_pokemon}"}

    base = get_base_stats(pokemon)
    if not base:
        return {"success": False, "error": f"Pokemon '{pokemon}' not found"}

    nature_mult = get_nature_multiplier(pokemon_nature, "spe")
    required_speed = target_speed + 1

    for ev in range(0, MAX_SINGLE_EV + 1, EV_STEP):
        speed = calculate_stat(base["spe"], pokemon_iv, ev, nature_mult, 50)
        if speed >= required_speed:
            return {
                "success": True,
                "evs": ev,
                "speed": speed,
                "target_speed": target_speed,
                "margin": speed - target_speed,
            }

    max_speed = calculate_stat(base["spe"], pokemon_iv, MAX_SINGLE_EV, nature_mult, 50)
    return {
        "success": False,
        "error": (
            f"Cannot outspeed {target_pokemon} (max speed: {max_speed}, target: {target_speed})"
        ),
        "max_speed": max_speed,
        "target_speed": target_speed,
    }


def find_speed_evs_to_underspeed(
    pokemon: str,
    target_pokemon: str,
    target_evs: str,
    target_nature: str,
    pokemon_nature: str = "Brave",
    pokemon_iv: int = 0,
) -> dict[str, Any]:
    """Find Speed EVs to underspeed a target Pokemon (for Trick Room)."""
    target_speed = get_speed_stat(target_pokemon, target_evs, None, target_nature)
    if target_speed is None:
        return {"success": False, "error": f"Could not calculate speed for {target_pokemon}"}

    base = get_base_stats(pokemon)
    if not base:
        return {"success": False, "error": f"Pokemon '{pokemon}' not found"}

    nature_mult = get_nature_multiplier(pokemon_nature, "spe")
    min_speed = calculate_stat(base["spe"], pokemon_iv, 0, nature_mult, 50)

    if min_speed < target_speed:
        return {
            "success": True,
            "evs": 0,
            "speed": min_speed,
            "target_speed": target_speed,
            "margin": target_speed - min_speed,
        }

    return {
        "success": False,
        "error": (
            f"Cannot underspeed {target_pokemon} (min speed: {min_speed}, target: {target_speed})"
        ),
        "min_speed": min_speed,
        "target_speed": target_speed,
    }


def find_survival_evs(
    defender: str,
    defender_nature: str,
    defender_item: str | None,
    defender_ability: str | None,
    goal: SurviveGoal,
    current_evs: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Find minimum defensive EVs to survive an attack.

    Uses binary search to find optimal HP + defensive stat investment.
    """
    base = get_base_stats(defender)
    if not base:
        return {"success": False, "error": f"Pokemon '{defender}' not found"}

    if current_evs is None:
        current_evs = {s: 0 for s in STAT_ORDER}

    move_result = calculate_damage_simple(
        attacker_name=goal.attacker,
        attacker_evs=goal.attacker_evs,
        attacker_nature=goal.attacker_nature,
        defender_name=defender,
        defender_evs="252/0/252/0/252/0",
        defender_nature=defender_nature,
        move=goal.move,
        attacker_item=goal.attacker_item,
        attacker_ability=goal.attacker_ability,
        defender_item=defender_item,
        defender_ability=defender_ability,
        attacker_tera=goal.attacker_tera,
        weather=goal.field_weather,
        terrain=goal.field_terrain,
        attacker_boosts=goal.attacker_boosts,
    )

    if not move_result.get("success", False):
        err = move_result.get("error", "Unknown error")
        return {"success": False, "error": f"Damage calc failed: {err}"}

    is_special = move_result.get("category") == "Special"
    def_stat = "spd" if is_special else "def"

    best_spread = None
    best_total_evs = float("inf")

    for hp_ev in range(0, MAX_SINGLE_EV + 1, 4):
        remaining_total = MAX_EVS - sum(current_evs.values()) - hp_ev
        if remaining_total < 0:
            continue

        for def_ev in range(0, min(MAX_SINGLE_EV, remaining_total) + 1, 4):
            test_evs = current_evs.copy()
            test_evs["hp"] = hp_ev
            test_evs[def_stat] = def_ev

            result = calculate_damage_simple(
                attacker_name=goal.attacker,
                attacker_evs=goal.attacker_evs,
                attacker_nature=goal.attacker_nature,
                defender_name=defender,
                defender_evs=evs_to_compact(test_evs),
                defender_nature=defender_nature,
                move=goal.move,
                attacker_item=goal.attacker_item,
                attacker_ability=goal.attacker_ability,
                defender_item=defender_item,
                defender_ability=defender_ability,
                attacker_tera=goal.attacker_tera,
                weather=goal.field_weather,
                terrain=goal.field_terrain,
                attacker_boosts=goal.attacker_boosts,
            )

            if not result.get("success"):
                continue

            max_pct = result.get("maxPercent", 100)
            if max_pct < 100:
                total_evs = hp_ev + def_ev
                if total_evs < best_total_evs:
                    best_total_evs = total_evs
                    best_spread = {"hp": hp_ev, def_stat: def_ev}

                    if total_evs <= 4:
                        break
        if best_spread and best_total_evs <= 4:
            break

    if best_spread:
        final_evs = current_evs.copy()
        final_evs.update(best_spread)

        final_result = calculate_damage_simple(
            attacker_name=goal.attacker,
            attacker_evs=goal.attacker_evs,
            attacker_nature=goal.attacker_nature,
            defender_name=defender,
            defender_evs=evs_to_compact(final_evs),
            defender_nature=defender_nature,
            move=goal.move,
            attacker_item=goal.attacker_item,
            attacker_ability=goal.attacker_ability,
            defender_item=defender_item,
            defender_ability=defender_ability,
            attacker_tera=goal.attacker_tera,
            weather=goal.field_weather,
            terrain=goal.field_terrain,
            attacker_boosts=goal.attacker_boosts,
        )

        min_pct = final_result.get("minPercent", 0)
        max_pct = final_result.get("maxPercent", 100)
        return {
            "success": True,
            "evs": best_spread,
            "damage_range": f"{min_pct:.1f}-{max_pct:.1f}%",
            "defense_stat": def_stat,
            "total_defensive_evs": best_total_evs,
        }

    return {
        "success": False,
        "error": f"Cannot survive {goal.attacker}'s {goal.move} with available EVs",
    }


def find_ohko_evs(
    attacker: str,
    attacker_nature: str,
    attacker_item: str | None,
    attacker_ability: str | None,
    goal: OHKOGoal,
) -> dict[str, Any]:
    """Find minimum offensive EVs to OHKO a target."""
    move_result = calculate_damage_simple(
        attacker_name=attacker,
        attacker_evs="0/252/0/252/0/0",
        attacker_nature=attacker_nature,
        defender_name=goal.defender,
        defender_evs=goal.defender_evs,
        defender_nature=goal.defender_nature,
        move=goal.move,
        attacker_item=attacker_item,
        attacker_ability=attacker_ability,
        defender_item=goal.defender_item,
        defender_ability=goal.defender_ability,
    )

    if not move_result.get("success", False):
        err = move_result.get("error", "Unknown error")
        return {"success": False, "error": f"Damage calc failed: {err}"}

    is_special = move_result.get("category") == "Special"
    atk_stat = "spa" if is_special else "atk"

    for ev in range(0, MAX_SINGLE_EV + 1, 4):
        test_evs = {s: 0 for s in STAT_ORDER}
        test_evs[atk_stat] = ev

        result = calculate_damage_simple(
            attacker_name=attacker,
            attacker_evs=evs_to_compact(test_evs),
            attacker_nature=attacker_nature,
            defender_name=goal.defender,
            defender_evs=goal.defender_evs,
            defender_nature=goal.defender_nature,
            move=goal.move,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            defender_item=goal.defender_item,
            defender_ability=goal.defender_ability,
        )

        if not result.get("success"):
            continue

        min_pct = result.get("minPercent", 0)
        if min_pct >= 100:
            max_pct = result.get("maxPercent", 100)
            return {
                "success": True,
                "evs": {atk_stat: ev},
                "damage_range": f"{min_pct:.1f}-{max_pct:.1f}%",
                "guaranteed_ohko": True,
                "attack_stat": atk_stat,
            }

    max_result = calculate_damage_simple(
        attacker_name=attacker,
        attacker_evs=f"0/{MAX_SINGLE_EV}/0/{MAX_SINGLE_EV}/0/0",
        attacker_nature=attacker_nature,
        defender_name=goal.defender,
        defender_evs=goal.defender_evs,
        defender_nature=goal.defender_nature,
        move=goal.move,
        attacker_item=attacker_item,
        attacker_ability=attacker_ability,
        defender_item=goal.defender_item,
        defender_ability=goal.defender_ability,
    )

    min_dmg = max_result.get("minPercent", 0)
    max_dmg = max_result.get("maxPercent", 100)
    return {
        "success": False,
        "error": f"Cannot OHKO {goal.defender} with {goal.move}",
        "max_damage": f"{min_dmg:.1f}-{max_dmg:.1f}%",
    }


def optimize_spread(
    pokemon: str,
    goals: list[SurviveGoal | OHKOGoal | OutspeedGoal | UnderspeedGoal | MaximizeGoal],
    nature: str | None = None,
    item: str | None = None,
    ability: str | None = None,
    tera_type: str | None = None,
    ivs: dict[str, int] | None = None,
) -> OptimizedSpread:
    """Generate an optimized EV spread for a list of goals.

    Goals are processed in priority order. The nature can be auto-selected
    based on the goals if not specified.
    """
    base = get_base_stats(pokemon)
    if not base:
        return OptimizedSpread(
            pokemon=pokemon,
            nature=nature or "Hardy",
            evs={s: 0 for s in STAT_ORDER},
            ivs=ivs or {s: 31 for s in STAT_ORDER},
            calculated_stats={s: 0 for s in STAT_ORDER},
            goal_results=[
                GoalResult(
                    goal_description="Find Pokemon",
                    achieved=False,
                    evs_used={},
                    detail=f"Pokemon '{pokemon}' not found in database",
                )
            ],
            ev_total=0,
        )

    if ivs is None:
        ivs = {s: 31 for s in STAT_ORDER}

    if nature is None:
        nature = _suggest_nature(goals)

    evs: dict[str, int] = {s: 0 for s in STAT_ORDER}
    goal_results: list[GoalResult] = []
    suggestions: list[str] = []

    for goal in goals:
        remaining = MAX_EVS - sum(evs.values())

        if isinstance(goal, OutspeedGoal):
            result = find_speed_evs_to_outspeed(
                pokemon, goal.target, goal.target_evs, goal.target_nature, nature, ivs["spe"]
            )
            if result["success"]:
                needed = result["evs"]
                if needed <= remaining and evs["spe"] + needed <= MAX_SINGLE_EV:
                    evs["spe"] = max(evs["spe"], needed)
                    speed = result["speed"]
                    target_spe = result["target_speed"]
                    goal_results.append(
                        GoalResult(
                            goal_description=f"Outspeed {goal.target}",
                            achieved=True,
                            evs_used={"spe": needed},
                            detail=f"{speed} Spe outspeeds {goal.target}'s {target_spe}",
                        )
                    )
                else:
                    goal_results.append(
                        GoalResult(
                            goal_description=f"Outspeed {goal.target}",
                            achieved=False,
                            evs_used={},
                            detail=f"Not enough EVs remaining ({remaining} left, need {needed})",
                        )
                    )
            else:
                goal_results.append(
                    GoalResult(
                        goal_description=f"Outspeed {goal.target}",
                        achieved=False,
                        evs_used={},
                        detail=result.get("error", "Failed"),
                    )
                )

        elif isinstance(goal, UnderspeedGoal):
            ivs["spe"] = 0
            result = find_speed_evs_to_underspeed(
                pokemon, goal.target, goal.target_evs, goal.target_nature, nature, ivs["spe"]
            )
            if result["success"]:
                speed = result["speed"]
                target_spe = result["target_speed"]
                goal_results.append(
                    GoalResult(
                        goal_description=f"Underspeed {goal.target}",
                        achieved=True,
                        evs_used={"spe": 0},
                        detail=f"{speed} Spe underspeeds {goal.target}'s {target_spe}",
                    )
                )
            else:
                goal_results.append(
                    GoalResult(
                        goal_description=f"Underspeed {goal.target}",
                        achieved=False,
                        evs_used={},
                        detail=result.get("error", "Failed"),
                    )
                )
                suggestions.append(f"Consider a -Spe nature to underspeed {goal.target}")

        elif isinstance(goal, SurviveGoal):
            result = find_survival_evs(pokemon, nature, item, ability, goal, evs)
            if result["success"]:
                for stat, ev in result["evs"].items():
                    evs[stat] = max(evs[stat], ev)
                goal_results.append(
                    GoalResult(
                        goal_description=f"Survive {goal.attacker}'s {goal.move}",
                        achieved=True,
                        evs_used=result["evs"],
                        detail=f"Takes {result['damage_range']} damage",
                    )
                )
            else:
                goal_results.append(
                    GoalResult(
                        goal_description=f"Survive {goal.attacker}'s {goal.move}",
                        achieved=False,
                        evs_used={},
                        detail=result.get("error", "Failed"),
                    )
                )

        elif isinstance(goal, OHKOGoal):
            result = find_ohko_evs(pokemon, nature, item, ability, goal)
            if result["success"]:
                for stat, ev in result["evs"].items():
                    evs[stat] = max(evs[stat], ev)
                goal_results.append(
                    GoalResult(
                        goal_description=f"OHKO {goal.defender} with {goal.move}",
                        achieved=True,
                        evs_used=result["evs"],
                        detail=f"Deals {result['damage_range']} damage (guaranteed OHKO)",
                    )
                )
            else:
                goal_results.append(
                    GoalResult(
                        goal_description=f"OHKO {goal.defender} with {goal.move}",
                        achieved=False,
                        evs_used={},
                        detail=result.get("error", "Failed"),
                    )
                )

        elif isinstance(goal, MaximizeGoal):
            remaining = MAX_EVS - sum(evs.values())
            stat = goal.stat
            can_add = min(MAX_SINGLE_EV - evs[stat], remaining)
            can_add = (can_add // EV_STEP) * EV_STEP
            if can_add > 0:
                evs[stat] += can_add
                goal_results.append(
                    GoalResult(
                        goal_description=f"Maximize {stat.upper()}",
                        achieved=True,
                        evs_used={stat: can_add},
                        detail=f"Added {can_add} EVs to {stat.upper()}",
                    )
                )
            else:
                goal_results.append(
                    GoalResult(
                        goal_description=f"Maximize {stat.upper()}",
                        achieved=False,
                        evs_used={},
                        detail="No EVs remaining",
                    )
                )

    remaining = MAX_EVS - sum(evs.values())
    if remaining >= EV_STEP:
        for stat in ["hp", "def", "spd"]:
            can_add = min(MAX_SINGLE_EV - evs[stat], remaining)
            can_add = (can_add // EV_STEP) * EV_STEP
            if can_add > 0:
                evs[stat] += can_add
                remaining -= can_add
            if remaining < EV_STEP:
                break

    calculated_stats = calculate_all_stats(pokemon, evs, ivs, nature)
    if calculated_stats is None:
        calculated_stats = {s: 0 for s in STAT_ORDER}

    return OptimizedSpread(
        pokemon=pokemon,
        nature=nature,
        evs=evs,
        ivs=ivs,
        calculated_stats=calculated_stats,
        goal_results=goal_results,
        ev_total=sum(evs.values()),
        suggestions=suggestions,
    )


def _suggest_nature(goals: list) -> str:
    """Suggest a nature based on the goals."""
    has_physical_ohko = any(isinstance(g, OHKOGoal) for g in goals)
    has_special_ohko = any(isinstance(g, OHKOGoal) for g in goals)
    has_outspeed = any(isinstance(g, OutspeedGoal) for g in goals)
    has_underspeed = any(isinstance(g, UnderspeedGoal) for g in goals)
    has_survive = any(isinstance(g, SurviveGoal) for g in goals)

    if has_underspeed:
        if has_physical_ohko:
            return "Brave"
        if has_special_ohko:
            return "Quiet"
        return "Relaxed"

    if has_outspeed:
        if has_physical_ohko:
            return "Jolly"
        if has_special_ohko:
            return "Timid"
        return "Timid"

    if has_physical_ohko:
        return "Adamant"
    if has_special_ohko:
        return "Modest"

    if has_survive:
        return "Careful"

    return "Hardy"
