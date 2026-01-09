"""Fetch and parse pokepaste.es team pastes."""

import re

import httpx

from smogon_vgc_mcp.database.models import TeamPokemon

# Stat name mappings
STAT_MAP = {
    "HP": "hp",
    "Atk": "atk",
    "Def": "def",
    "SpA": "spa",
    "SpD": "spd",
    "Spe": "spe",
}


async def fetch_pokepaste(url: str) -> str | None:
    """Fetch raw paste content from pokepast.es.

    Args:
        url: The pokepaste URL (e.g., https://pokepast.es/abc123)

    Returns:
        Raw paste text or None if fetch failed
    """
    # Convert to raw URL format
    if not url.endswith("/raw"):
        raw_url = url.rstrip("/") + "/raw"
    else:
        raw_url = url

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.get(raw_url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            print(f"Failed to fetch pokepaste {url}: {e}")
            return None


def parse_evs(line: str) -> dict[str, int]:
    """Parse an EVs line like 'EVs: 252 HP / 4 Def / 252 SpA'.

    Returns:
        Dict mapping stat names to values (e.g., {"hp": 252, "def": 4, "spa": 252})
    """
    evs = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}

    # Remove "EVs:" prefix
    line = line.replace("EVs:", "").strip()

    # Split by /
    parts = [p.strip() for p in line.split("/")]

    for part in parts:
        # Match "252 HP" or "4 Def" etc
        match = re.match(r"(\d+)\s+(\w+)", part)
        if match:
            value = int(match.group(1))
            stat_name = match.group(2)
            if stat_name in STAT_MAP:
                evs[STAT_MAP[stat_name]] = value

    return evs


def parse_ivs(line: str) -> dict[str, int]:
    """Parse an IVs line like 'IVs: 0 Atk'.

    Returns:
        Dict mapping stat names to values (defaults to 31 for unspecified)
    """
    ivs = {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

    # Remove "IVs:" prefix
    line = line.replace("IVs:", "").strip()

    # Split by /
    parts = [p.strip() for p in line.split("/")]

    for part in parts:
        match = re.match(r"(\d+)\s+(\w+)", part)
        if match:
            value = int(match.group(1))
            stat_name = match.group(2)
            if stat_name in STAT_MAP:
                ivs[STAT_MAP[stat_name]] = value

    return ivs


def parse_pokepaste(text: str) -> list[TeamPokemon]:
    """Parse a pokepaste text into a list of TeamPokemon.

    Args:
        text: Raw pokepaste text containing 1-6 Pokemon

    Returns:
        List of TeamPokemon objects
    """
    pokemon_list = []

    # Split by double newlines to separate Pokemon
    pokemon_blocks = re.split(r"\n\s*\n", text.strip())

    for slot, block in enumerate(pokemon_blocks, start=1):
        if not block.strip():
            continue

        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if not lines:
            continue

        # Parse first line: "Pokemon Name @ Item" or "Nickname (Pokemon Name) @ Item"
        first_line = lines[0]

        # Extract item
        item = None
        if " @ " in first_line:
            name_part, item = first_line.split(" @ ", 1)
        else:
            name_part = first_line

        # Extract Pokemon name (handle nicknames)
        pokemon_name = name_part
        if "(" in name_part and ")" in name_part:
            # Format: "Nickname (Pokemon Name)" - extract Pokemon name from parens
            match = re.search(r"\(([^)]+)\)", name_part)
            if match:
                pokemon_name = match.group(1)
        else:
            # No nickname, might have gender suffix like "(M)" or "(F)"
            pokemon_name = re.sub(r"\s*\([MF]\)\s*$", "", name_part).strip()

        # Initialize Pokemon data
        pokemon = TeamPokemon(
            slot=slot,
            pokemon=pokemon_name,
            item=item,
        )

        # Parse remaining lines
        moves = []
        for line in lines[1:]:
            if line.startswith("Ability:"):
                pokemon.ability = line.replace("Ability:", "").strip()
            elif line.startswith("Tera Type:"):
                pokemon.tera_type = line.replace("Tera Type:", "").strip()
            elif line.startswith("EVs:"):
                evs = parse_evs(line)
                pokemon.hp_ev = evs["hp"]
                pokemon.atk_ev = evs["atk"]
                pokemon.def_ev = evs["def"]
                pokemon.spa_ev = evs["spa"]
                pokemon.spd_ev = evs["spd"]
                pokemon.spe_ev = evs["spe"]
            elif line.startswith("IVs:"):
                ivs = parse_ivs(line)
                pokemon.hp_iv = ivs["hp"]
                pokemon.atk_iv = ivs["atk"]
                pokemon.def_iv = ivs["def"]
                pokemon.spa_iv = ivs["spa"]
                pokemon.spd_iv = ivs["spd"]
                pokemon.spe_iv = ivs["spe"]
            elif line.endswith(" Nature"):
                pokemon.nature = line.replace(" Nature", "").strip()
            elif line.startswith("- "):
                moves.append(line[2:].strip())

        # Assign moves
        if len(moves) >= 1:
            pokemon.move1 = moves[0]
        if len(moves) >= 2:
            pokemon.move2 = moves[1]
        if len(moves) >= 3:
            pokemon.move3 = moves[2]
        if len(moves) >= 4:
            pokemon.move4 = moves[3]

        pokemon_list.append(pokemon)

    return pokemon_list
