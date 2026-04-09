"""Champions SP (Skill Points) optimizer for item thresholds and speed goals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from smogon_vgc_mcp.calculator.champions_stats import (
    MAX_SP_PER_STAT,
    MAX_TOTAL_SP,
    calculate_champions_hp,
    calculate_champions_stat,
)
from smogon_vgc_mcp.data.pokemon_data import get_nature_multiplier


@dataclass
class SpeedGoal:
    target_speed: int
    mode: str = "outspeed"  # "outspeed" or "underspeed"


@dataclass
class MaximizeGoal:
    stat: str  # hp, atk, def, spa, spd, spe


@dataclass
class HpThresholdGoal:
    item: str  # "Leftovers", "Life Orb", "Sitrus Berry"


SpGoal = SpeedGoal | MaximizeGoal | HpThresholdGoal

# Item HP divisibility rules: (divisor, target_remainder)
_ITEM_HP_RULES: dict[str, tuple[int, int]] = {
    "leftovers": (16, 0),
    "black sludge": (16, 0),
    "life orb": (10, 1),
    "sitrus berry": (4, 0),
}


def suggest_hp_sp(base_hp: int, item: str | None, level: int = 50) -> dict[str, Any]:
    """Suggest HP SP allocation based on item divisibility rules.

    Returns dict with recommended_sp, resulting_hp, reason.
    SP is capped at MAX_SP_PER_STAT (32).
    """
    base_hp_stat = calculate_champions_hp(base_hp, 0, level)

    if item is None:
        return {
            "recommended_sp": 0,
            "resulting_hp": base_hp_stat,
            "reason": "No item — no HP optimization needed",
        }

    rule = _ITEM_HP_RULES.get(item.lower())
    if rule is None:
        return {
            "recommended_sp": 0,
            "resulting_hp": base_hp_stat,
            "reason": f"No HP optimization rule for {item}",
        }

    divisor, target_remainder = rule
    current_remainder = base_hp_stat % divisor

    if current_remainder == target_remainder:
        return {
            "recommended_sp": 0,
            "resulting_hp": base_hp_stat,
            "reason": (
                f"HP {base_hp_stat} already optimal for {item}"
                f" ({base_hp_stat} % {divisor} == {target_remainder})"
            ),
        }

    # Calculate SP needed to reach target remainder
    needed = (target_remainder - current_remainder) % divisor
    resulting_hp = base_hp_stat + needed
    return {
        "recommended_sp": needed,
        "resulting_hp": resulting_hp,
        "reason": f"HP {resulting_hp} % {divisor} == {target_remainder} for {item}",
    }


def optimize_champions_sp(
    base_stats: dict[str, int],
    nature: str,
    goals: list[SpGoal],
    level: int = 50,
) -> dict[str, Any]:
    """Allocate SP budget across stats based on priority-ordered goals.

    Returns dict with success, sp_spread, remaining_sp, total_sp, goal_results.
    """
    sp_spread: dict[str, int] = {s: 0 for s in ("hp", "atk", "def", "spa", "spd", "spe")}
    remaining = MAX_TOTAL_SP
    goal_results: list[dict[str, Any]] = []

    for goal in goals:
        if isinstance(goal, SpeedGoal):
            result = _process_speed_goal(goal, base_stats, nature, sp_spread, remaining, level)
        elif isinstance(goal, HpThresholdGoal):
            result = _process_hp_threshold_goal(goal, base_stats, sp_spread, remaining, level)
        elif isinstance(goal, MaximizeGoal):
            result = _process_maximize_goal(goal, sp_spread, remaining)
        else:
            result = {"success": False, "reason": f"Unknown goal type: {type(goal)}"}

        goal_results.append(result)

        if not result.get("success", False):
            total = sum(sp_spread.values())
            return {
                "success": False,
                "sp_spread": sp_spread,
                "remaining_sp": remaining,
                "total_sp": total,
                "goal_results": goal_results,
            }

        sp_used = result.get("sp_used", 0)
        remaining -= sp_used

    total = sum(sp_spread.values())
    return {
        "success": True,
        "sp_spread": sp_spread,
        "remaining_sp": remaining,
        "total_sp": total,
        "goal_results": goal_results,
    }


def _process_speed_goal(
    goal: SpeedGoal,
    base_stats: dict[str, int],
    nature: str,
    sp_spread: dict[str, int],
    remaining: int,
    level: int,
) -> dict[str, Any]:
    nature_mult = get_nature_multiplier(nature, "spe")
    base_speed_no_sp = calculate_champions_stat(base_stats["spe"], 0, nature_mult, level)

    if goal.mode == "underspeed":
        # Want speed < target_speed. With SP you can only add, not subtract.
        if base_speed_no_sp >= goal.target_speed:
            return {
                "success": False,
                "reason": (
                    f"Base speed {base_speed_no_sp} already >= "
                    f"{goal.target_speed}, cannot underspeed"
                ),
            }
        # Already under, no SP needed for speed
        return {"success": True, "sp_used": 0, "base_speed": base_speed_no_sp}

    # Outspeed mode
    target = goal.target_speed + 1
    sp_needed = target - base_speed_no_sp - sp_spread["spe"]

    if sp_needed <= 0:
        return {"success": True, "sp_used": 0, "base_speed": base_speed_no_sp}

    max_available = min(MAX_SP_PER_STAT - sp_spread["spe"], remaining)
    if sp_needed > max_available:
        return {
            "success": False,
            "reason": f"Need {sp_needed} speed SP but only {max_available} available",
        }

    sp_spread["spe"] += sp_needed
    return {"success": True, "sp_used": sp_needed, "base_speed": base_speed_no_sp}


def _process_hp_threshold_goal(
    goal: HpThresholdGoal,
    base_stats: dict[str, int],
    sp_spread: dict[str, int],
    remaining: int,
    level: int,
) -> dict[str, Any]:
    suggestion = suggest_hp_sp(base_stats["hp"], goal.item, level)
    recommended = suggestion["recommended_sp"]

    # Constrain by current HP SP and remaining budget
    additional = max(0, recommended - sp_spread["hp"])
    actual = min(additional, MAX_SP_PER_STAT - sp_spread["hp"], remaining)

    sp_spread["hp"] += actual
    resulting_hp = calculate_champions_hp(base_stats["hp"], sp_spread["hp"], level)

    return {
        "success": True,
        "sp_used": actual,
        "resulting_hp": resulting_hp,
        "reason": suggestion["reason"],
    }


def _process_maximize_goal(
    goal: MaximizeGoal,
    sp_spread: dict[str, int],
    remaining: int,
) -> dict[str, Any]:
    current = sp_spread[goal.stat]
    to_add = min(MAX_SP_PER_STAT - current, remaining)
    sp_spread[goal.stat] += to_add
    return {"success": True, "sp_used": to_add}
