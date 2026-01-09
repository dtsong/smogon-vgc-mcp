"""Speed tier analysis for VGC."""

from smogon_vgc_mcp.calculator.stats import calculate_all_stats


def get_speed_stat(
    pokemon: str,
    evs: str | dict,
    ivs: str | dict | None = None,
    nature: str = "Hardy",
    level: int = 50,
) -> int | None:
    """Get the speed stat for a Pokemon with given spread.

    Args:
        pokemon: Pokemon name
        evs: EV spread
        ivs: IV spread (defaults to 31s)
        nature: Nature name
        level: Pokemon level

    Returns:
        Speed stat value or None if Pokemon not found
    """
    stats = calculate_all_stats(pokemon, evs, ivs, nature, level)
    if stats:
        return stats["spe"]
    return None


def compare_speeds(
    pokemon1: str,
    evs1: str | dict,
    nature1: str,
    pokemon2: str,
    evs2: str | dict,
    nature2: str,
    ivs1: str | dict | None = None,
    ivs2: str | dict | None = None,
) -> dict:
    """Compare speeds between two Pokemon.

    Returns:
        Dict with speed values and comparison result
    """
    speed1 = get_speed_stat(pokemon1, evs1, ivs1, nature1)
    speed2 = get_speed_stat(pokemon2, evs2, ivs2, nature2)

    if speed1 is None or speed2 is None:
        return {
            "error": "Could not calculate speed for one or both Pokemon",
            "pokemon1": {"name": pokemon1, "speed": speed1},
            "pokemon2": {"name": pokemon2, "speed": speed2},
        }

    if speed1 > speed2:
        result = f"{pokemon1} outspeeds {pokemon2}"
        faster = pokemon1
    elif speed2 > speed1:
        result = f"{pokemon2} outspeeds {pokemon1}"
        faster = pokemon2
    else:
        result = "Speed tie"
        faster = None

    return {
        "pokemon1": {"name": pokemon1, "speed": speed1, "nature": nature1},
        "pokemon2": {"name": pokemon2, "speed": speed2, "nature": nature2},
        "difference": abs(speed1 - speed2),
        "result": result,
        "faster": faster,
    }


# Common VGC speed benchmarks (base speeds of notable Pokemon)
SPEED_BENCHMARKS = {
    # Very fast (base 130+)
    135: ["Dragapult"],
    136: ["Regieleki"],
    142: ["Electrode-Hisui"],
    # Fast (base 100-129)
    130: ["Aerodactyl", "Jolteon"],
    128: ["Zeraora"],
    123: ["Talonflame"],
    122: ["Serperior"],
    121: ["Weavile"],
    119: ["Cinderace", "Meowscarada"],
    116: ["Raging Bolt"],  # Actually 91 but often cited
    112: ["Dugtrio"],
    111: ["Gengar", "Sneasler"],
    110: ["Froslass", "Latios", "Latias"],
    109: ["Galarian Zapdos"],
    108: ["Terrakion", "Infernape", "Keldeo"],
    106: ["Iron Bundle"],
    105: ["Mienshao"],
    104: ["Rillaboom"],  # Grassy Surge user
    103: ["Garchomp"],
    102: ["Landorus-Therian"],
    101: ["Landorus"],
    100: ["Charizard", "Volcarona", "Salamence"],
    # Medium-fast (base 80-99)
    99: ["Arcanine-Hisui"],
    98: ["Dragonite"],
    97: ["Ogerpon"],
    96: ["Tornadus"],
    95: ["Arcanine", "Electivire", "Leafeon"],
    92: ["Urshifu"],
    91: ["Volcanion", "Raging Bolt"],
    90: ["Lucario", "Entei", "Raikou", "Suicune"],
    86: ["Heatran"],
    85: ["Heracross", "Kingambit"],
    83: ["Gyarados"],
    81: ["Dragonite"],  # base
    80: ["Togekiss", "Mamoswine", "Venusaur"],
    # Medium (base 60-79)
    77: ["Politoed", "Pelipper"],
    75: ["Breloom", "Hitmontop"],
    70: ["Clefable", "Goodra", "Volcarona"],
    65: ["Amoonguss", "Umbreon"],
    60: ["Porygon2", "Blissey"],
    # Slow (base <60)
    50: ["Snorlax", "Dusclops"],
    45: ["Torkoal"],
    35: ["Dondozo"],
    30: ["Ferrothorn"],
    20: ["Iron Hands"],
    5: ["Shuckle"],
}


def get_min_speed(base_speed: int, level: int = 50) -> int:
    """Calculate minimum possible speed (0 EVs, 0 IV, negative nature)."""
    import math

    raw = math.floor((2 * base_speed + 0 + 0) * level / 100) + 5
    return math.floor(raw * 0.9)


def get_max_speed(base_speed: int, level: int = 50) -> int:
    """Calculate maximum possible speed (252 EVs, 31 IV, positive nature)."""
    import math

    raw = math.floor((2 * base_speed + 31 + 63) * level / 100) + 5
    return math.floor(raw * 1.1)


def find_speed_benchmarks(pokemon: str, speed_stat: int) -> dict:
    """Find what notable Pokemon this speed stat outspeeds/underspeeds.

    Args:
        pokemon: Pokemon name (for context)
        speed_stat: Calculated speed stat

    Returns:
        Dict with lists of Pokemon this speed beats and loses to
    """
    outspeeds = []
    underspeeds = []
    ties = []

    for base_speed, pokemon_list in sorted(SPEED_BENCHMARKS.items(), reverse=True):
        max_spd = get_max_speed(base_speed)
        min_spd = get_min_speed(base_speed)

        for poke in pokemon_list:
            if speed_stat > max_spd:
                outspeeds.append({"pokemon": poke, "max_speed": max_spd})
            elif speed_stat < min_spd:
                underspeeds.append({"pokemon": poke, "min_speed": min_spd})
            else:
                ties.append({"pokemon": poke, "speed_range": f"{min_spd}-{max_spd}"})

    return {
        "pokemon": pokemon,
        "speed_stat": speed_stat,
        "outspeeds_max": outspeeds[:10],
        "underspeeds_min": underspeeds[:10],
        "speed_ties_possible": ties[:10],
    }
