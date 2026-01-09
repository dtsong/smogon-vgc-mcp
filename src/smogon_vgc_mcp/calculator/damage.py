"""Damage calculation via @smogon/calc subprocess."""

import json
import subprocess
from pathlib import Path
from typing import Any

from smogon_vgc_mcp.utils import parse_ev_string, parse_iv_string

# Path to the Node.js wrapper script
CALC_WRAPPER_PATH = Path(__file__).parent.parent.parent.parent / "calc" / "calc_wrapper.js"


def build_pokemon_dict(
    name: str,
    evs: str | dict[str, int] | None = None,
    ivs: str | dict[str, int] | None = None,
    nature: str = "Hardy",
    item: str | None = None,
    ability: str | None = None,
    tera_type: str | None = None,
    level: int = 50,
    boosts: dict[str, int] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Build Pokemon dict for damage calc input.

    Args:
        name: Pokemon name
        evs: EV spread as string or dict
        ivs: IV spread as string or dict
        nature: Nature name
        item: Held item
        ability: Ability name
        tera_type: Tera type if terastallized
        level: Pokemon level (default 50 for VGC)
        boosts: Stat boosts (-6 to +6)
        status: Status condition (Burned, Paralyzed, etc.)

    Returns:
        Pokemon dict for calc input
    """
    pokemon: dict[str, Any] = {"name": name, "level": level}

    if evs:
        if isinstance(evs, str):
            pokemon["evs"] = parse_ev_string(evs)
        else:
            pokemon["evs"] = evs

    if ivs:
        if isinstance(ivs, str):
            pokemon["ivs"] = parse_iv_string(ivs)
        else:
            pokemon["ivs"] = ivs

    if nature:
        pokemon["nature"] = nature
    if item:
        pokemon["item"] = item
    if ability:
        pokemon["ability"] = ability
    if tera_type:
        pokemon["teraType"] = tera_type
    if boosts:
        pokemon["boosts"] = boosts
    if status:
        pokemon["status"] = status

    return pokemon


def build_field_dict(
    game_type: str = "Doubles",
    weather: str | None = None,
    terrain: str | None = None,
    attacker_side: dict[str, Any] | None = None,
    defender_side: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Field dict for damage calc input.

    Args:
        game_type: "Singles" or "Doubles"
        weather: "Sun", "Rain", "Sand", "Snow", or None
        terrain: "Grassy", "Electric", "Psychic", "Misty", or None
        attacker_side: Attacker's side conditions
        defender_side: Defender's side conditions

    Returns:
        Field dict for calc input
    """
    field: dict[str, Any] = {"gameType": game_type}

    if weather:
        field["weather"] = weather
    if terrain:
        field["terrain"] = terrain
    if attacker_side:
        field["attackerSide"] = attacker_side
    if defender_side:
        field["defenderSide"] = defender_side

    return field


def run_calc(input_data: dict[str, Any]) -> dict[str, Any]:
    """Run damage calculation via Node.js subprocess.

    Args:
        input_data: Calculation input with attacker, defender, move, field

    Returns:
        Calculation result
    """
    if not CALC_WRAPPER_PATH.exists():
        return {
            "success": False,
            "error": f"Calc wrapper not found at {CALC_WRAPPER_PATH}",
        }

    try:
        # Run the Node.js wrapper
        result = subprocess.run(
            ["node", str(CALC_WRAPPER_PATH)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Calc failed: {result.stderr}",
            }

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Calculation timed out"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to parse calc output: {e}"}
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Node.js not found. Install Node.js and run 'npm install'.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def calculate_damage(
    attacker: dict[str, Any],
    defender: dict[str, Any],
    move: str,
    field: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate damage between two Pokemon.

    Args:
        attacker: Attacker Pokemon dict (from build_pokemon_dict)
        defender: Defender Pokemon dict (from build_pokemon_dict)
        move: Move name
        field: Field conditions dict (from build_field_dict)

    Returns:
        Damage calculation result
    """
    input_data = {
        "attacker": attacker,
        "defender": defender,
        "move": move,
        "field": field or {"gameType": "Doubles"},
    }

    return run_calc(input_data)


def calculate_damage_simple(
    attacker_name: str,
    attacker_evs: str,
    attacker_nature: str,
    defender_name: str,
    defender_evs: str,
    defender_nature: str,
    move: str,
    attacker_item: str | None = None,
    attacker_ability: str | None = None,
    defender_item: str | None = None,
    defender_ability: str | None = None,
    attacker_tera: str | None = None,
    weather: str | None = None,
    terrain: str | None = None,
    helping_hand: bool = False,
    reflect: bool = False,
    light_screen: bool = False,
    attacker_boosts: dict[str, int] | None = None,
    defender_boosts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Simplified damage calculation with common parameters.

    Args:
        attacker_name: Attacker Pokemon name
        attacker_evs: Attacker EV spread
        attacker_nature: Attacker nature
        defender_name: Defender Pokemon name
        defender_evs: Defender EV spread
        defender_nature: Defender nature
        move: Move name
        attacker_item: Attacker's held item
        attacker_ability: Attacker's ability
        defender_item: Defender's held item
        defender_ability: Defender's ability
        attacker_tera: Attacker's Tera type if active
        weather: Active weather
        terrain: Active terrain
        helping_hand: Whether Helping Hand is active
        reflect: Whether Reflect is active
        light_screen: Whether Light Screen is active
        attacker_boosts: Attacker's stat boosts
        defender_boosts: Defender's stat boosts

    Returns:
        Damage calculation result
    """
    attacker = build_pokemon_dict(
        name=attacker_name,
        evs=attacker_evs,
        nature=attacker_nature,
        item=attacker_item,
        ability=attacker_ability,
        tera_type=attacker_tera,
        boosts=attacker_boosts,
    )

    defender = build_pokemon_dict(
        name=defender_name,
        evs=defender_evs,
        nature=defender_nature,
        item=defender_item,
        ability=defender_ability,
        boosts=defender_boosts,
    )

    attacker_side = {}
    if helping_hand:
        attacker_side["isHelpingHand"] = True

    defender_side = {}
    if reflect:
        defender_side["isReflect"] = True
    if light_screen:
        defender_side["isLightScreen"] = True

    field = build_field_dict(
        game_type="Doubles",
        weather=weather,
        terrain=terrain,
        attacker_side=attacker_side if attacker_side else None,
        defender_side=defender_side if defender_side else None,
    )

    return calculate_damage(attacker, defender, move, field)


def batch_calculate(calculations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run multiple damage calculations in a single subprocess call.

    Args:
        calculations: List of calculation inputs

    Returns:
        List of calculation results
    """
    return run_calc(calculations)  # type: ignore
