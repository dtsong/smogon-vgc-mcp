"""Type analysis for Pokemon and teams."""

from collections import defaultdict

from smogon_vgc_mcp.data.pokemon_data import (
    ALL_TYPES,
    get_pokemon_types,
    get_resistances,
    get_type_effectiveness,
    get_weaknesses,
)


def get_pokemon_weaknesses(pokemon: str) -> dict:
    """Get detailed weakness information for a Pokemon.

    Args:
        pokemon: Pokemon name

    Returns:
        Dict with types and weakness info
    """
    types = get_pokemon_types(pokemon)
    if not types:
        return {"error": f"Pokemon '{pokemon}' not found"}

    weaknesses = get_weaknesses(pokemon)
    resistances = get_resistances(pokemon)

    # Categorize
    quad_weak = [(t, m) for t, m in weaknesses if m == 4]
    double_weak = [(t, m) for t, m in weaknesses if m == 2]
    resists = [(t, m) for t, m in resistances if m == 0.5]
    quad_resists = [(t, m) for t, m in resistances if m == 0.25]
    immunities = [(t, m) for t, m in resistances if m == 0]

    return {
        "pokemon": pokemon,
        "types": types,
        "4x_weak": [t for t, _ in quad_weak],
        "2x_weak": [t for t, _ in double_weak],
        "resists": [t for t, _ in resists],
        "4x_resists": [t for t, _ in quad_resists],
        "immunities": [t for t, _ in immunities],
    }


def get_pokemon_resistances(pokemon: str) -> dict:
    """Get detailed resistance information for a Pokemon.

    Args:
        pokemon: Pokemon name

    Returns:
        Dict with types and resistance info
    """
    return get_pokemon_weaknesses(pokemon)  # Same function, just different name


def analyze_team_types(pokemon_list: list[str]) -> dict:
    """Analyze type coverage for a team of Pokemon.

    Args:
        pokemon_list: List of Pokemon names

    Returns:
        Dict with team type analysis
    """
    if not pokemon_list:
        return {"error": "No Pokemon provided"}

    # Track weaknesses and resistances across the team
    team_weaknesses: dict[str, list[str]] = defaultdict(list)
    team_resistances: dict[str, list[str]] = defaultdict(list)
    team_immunities: dict[str, list[str]] = defaultdict(list)

    pokemon_types = {}
    errors = []

    for pokemon in pokemon_list:
        types = get_pokemon_types(pokemon)
        if not types:
            errors.append(f"Pokemon '{pokemon}' not found")
            continue

        pokemon_types[pokemon] = types

        # Check each attacking type
        for atk_type in ALL_TYPES:
            mult = get_type_effectiveness(atk_type, types)
            if mult > 1:
                team_weaknesses[atk_type].append(pokemon)
            elif mult == 0:
                team_immunities[atk_type].append(pokemon)
            elif mult < 1:
                team_resistances[atk_type].append(pokemon)

    # Find shared weaknesses (types that hit multiple team members SE)
    shared_weaknesses = {t: pokes for t, pokes in team_weaknesses.items() if len(pokes) >= 2}

    # Find unresisted types (no team member resists or is immune)
    unresisted = []
    for atk_type in ALL_TYPES:
        if atk_type not in team_resistances and atk_type not in team_immunities:
            unresisted.append(atk_type)

    return {
        "team": pokemon_list,
        "pokemon_types": pokemon_types,
        "shared_weaknesses": {
            t: {"count": len(pokes), "pokemon": pokes}
            for t, pokes in sorted(shared_weaknesses.items(), key=lambda x: -len(x[1]))
        },
        "unresisted_types": unresisted,
        "team_immunities": dict(team_immunities),
        "weakness_count": {
            t: len(pokes) for t, pokes in sorted(team_weaknesses.items(), key=lambda x: -len(x[1]))
        },
        "errors": errors if errors else None,
    }


def get_offensive_coverage(move_types: list[str]) -> dict:
    """Analyze offensive type coverage of a moveset.

    Args:
        move_types: List of move types

    Returns:
        Dict with coverage analysis
    """
    hits_super_effective: dict[str, list[str]] = defaultdict(list)
    resisted_by: dict[str, list[str]] = defaultdict(list)
    immune_to: dict[str, list[str]] = defaultdict(list)

    for move_type in move_types:
        for def_type in ALL_TYPES:
            mult = get_type_effectiveness(move_type, [def_type])
            if mult > 1:
                hits_super_effective[def_type].append(move_type)
            elif mult == 0:
                immune_to[def_type].append(move_type)
            elif mult < 1:
                resisted_by[def_type].append(move_type)

    # Types with no super effective coverage
    no_coverage = [t for t in ALL_TYPES if t not in hits_super_effective]

    return {
        "move_types": move_types,
        "super_effective_against": list(hits_super_effective.keys()),
        "no_super_effective_coverage": no_coverage,
        "resisted_by": list(resisted_by.keys()),
        "immune_types": list(immune_to.keys()),
    }
