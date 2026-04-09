"""Pokemon Champions format speed tier tools and benchmarks."""

from smogon_vgc_mcp.calculator.champions_stats import MAX_SP_PER_STAT, calculate_champions_stat
from smogon_vgc_mcp.data.pokemon_data import get_nature_multiplier

CHAMPIONS_SPEED_TIERS: list[tuple[int, str, str]] = [
    (280, "Excadrill", "Sand Rush"),
    (264, "Venusaur", "Chlorophyll/Tailwind"),
    (264, "Dragonite", "Tailwind"),
    (264, "Mega Meganium", "Tailwind"),
    (264, "Eelektross", "Tailwind"),
    (260, "Basculegion", "Swift Swim/Shell Smash"),
    (260, "Mega Blastoise", "Swift Swim"),
    (256, "Pelipper", "Tailwind"),
    (254, "Mega Scizor", "Tailwind"),
    (250, "Mega Charizard X", "Dragon Dance"),
    (250, "Volcarona", "Quiver Dance"),
    (244, "Mega Swampert", "Swift Swim"),
    (243, "Gengar", "Choice Scarf"),
    (228, "Mega Charizard X", "Dragon Dance (1 boost)"),
    (228, "Volcarona", "Quiver Dance (1 boost)"),
    (224, "Primarina", "Tailwind"),
    (224, "Incineroar", "Tailwind"),
    (224, "Aegislash", "Tailwind"),
    (224, "Sylveon", "Tailwind"),
    (223, "Mega Lucario", "Max Speed"),
    (223, "Mega Garchomp", "Max Speed"),
    (222, "Mega Aerodactyl", "Max Speed"),
    (222, "Mega Alakazam", "Max Speed"),
    (213, "Dragapult", "Max Speed"),
    (213, "Mega Greninja", "Max Speed"),
    (205, "Mega Manectric", "Max Speed"),
    (205, "Mega Lopunny", "Max Speed"),
    (200, "Mega Gengar", "Max Speed"),
    (200, "Mega Raichu Y", "Max Speed"),
    (195, "Talonflame", "Max Speed"),
    (194, "Weavile", "Max Speed"),
    (192, "Meowscarada", "Max Speed"),
    (191, "Greninja", "Max Speed"),
    (152, "Mega Charizard X", "Max Speed (unboosted)"),
    (152, "Mega Dragonite", "Max Speed"),
    (150, "Hydreigon", "Max Speed"),
    (150, "Archaludon", "Max Speed"),
    (150, "Kommo-o", "Max Speed"),
    (150, "Ceruledge", "Max Speed"),
    (137, "Archaludon", "Neutral Max SP"),
    (137, "Kommo-o", "Neutral Max SP"),
    (137, "Ceruledge", "Neutral Max SP"),
    (132, "Altaria", "Max Speed"),
    (132, "Dragonite", "Max Speed"),
    (132, "Mega Meganium", "Max Speed"),
    (132, "Chandelure", "Max Speed"),
    (112, "Primarina", "Max Speed"),
    (112, "Incineroar", "Max Speed"),
    (112, "Aegislash", "Max Speed"),
    (112, "Sylveon", "Max Speed"),
    (102, "Kingambit", "Max Speed"),
    (102, "Azumarill", "Max Speed"),
]


def get_champions_speed(base_spe: int, sp: int, nature: str, level: int = 50) -> int:
    """Calculate Champions speed stat."""
    nature_mult = get_nature_multiplier(nature, "spe")
    return calculate_champions_stat(base_spe, sp, nature_mult, level)


def compare_champions_speeds(
    pokemon1: str,
    base_spe1: int,
    sp1: int,
    nature1: str,
    pokemon2: str,
    base_spe2: int,
    sp2: int,
    nature2: str,
    level: int = 50,
) -> dict:
    """Compare two Pokemon speeds. Returns comparison result dict."""
    speed1 = get_champions_speed(base_spe1, sp1, nature1, level)
    speed2 = get_champions_speed(base_spe2, sp2, nature2, level)

    if speed1 > speed2:
        result = "pokemon1_faster"
    elif speed2 > speed1:
        result = "pokemon2_faster"
    else:
        result = "tie"

    return {
        "pokemon1": {"name": pokemon1, "speed": speed1},
        "pokemon2": {"name": pokemon2, "speed": speed2},
        "result": result,
        "difference": abs(speed1 - speed2),
    }


def find_champions_speed_benchmarks(pokemon: str, speed: int) -> dict:
    """Find what Champions meta Pokemon a speed stat outspeeds/underspeeds."""
    outspeeds: list[dict] = []
    underspeeds: list[dict] = []
    speed_ties: list[dict] = []

    seen: set[tuple[int, str, str]] = set()

    for tier_speed, name, notes in CHAMPIONS_SPEED_TIERS:
        key = (tier_speed, name, notes)
        if key in seen:
            continue
        seen.add(key)

        entry = {"speed": tier_speed, "pokemon": name, "notes": notes}
        if speed > tier_speed:
            outspeeds.append(entry)
        elif speed < tier_speed:
            underspeeds.append(entry)
        else:
            speed_ties.append(entry)

    return {
        "pokemon": pokemon,
        "speed": speed,
        "outspeeds": outspeeds,
        "underspeeds": underspeeds,
        "speed_ties": speed_ties,
    }


def find_champions_speed_sp(
    base_spe: int,
    target_speed: int,
    nature: str,
    goal: str,
    level: int = 50,
) -> dict:
    """Find minimum SP needed to outspeed/underspeed a target speed."""
    nature_mult = get_nature_multiplier(nature, "spe")
    base_speed_no_sp = calculate_champions_stat(base_spe, 0, nature_mult, level)

    if goal == "outspeed":
        if base_speed_no_sp > target_speed:
            return {
                "success": True,
                "sp_needed": 0,
                "resulting_speed": base_speed_no_sp,
                "target_speed": target_speed,
            }
        sp_needed = target_speed + 1 - base_speed_no_sp
        if sp_needed > MAX_SP_PER_STAT:
            return {
                "success": False,
                "sp_needed": None,
                "resulting_speed": None,
                "target_speed": target_speed,
            }
        return {
            "success": True,
            "sp_needed": sp_needed,
            "resulting_speed": base_speed_no_sp + sp_needed,
            "target_speed": target_speed,
        }

    # goal == "underspeed"
    if base_speed_no_sp < target_speed:
        return {
            "success": True,
            "sp_needed": 0,
            "resulting_speed": base_speed_no_sp,
            "target_speed": target_speed,
        }
    return {
        "success": False,
        "sp_needed": None,
        "resulting_speed": None,
        "target_speed": target_speed,
    }
