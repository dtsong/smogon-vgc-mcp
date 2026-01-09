"""Fetch and parse pokepaste.es team pastes."""

import re

from smogon_vgc_mcp.database.models import TeamPokemon
from smogon_vgc_mcp.resilience import FetchResult
from smogon_vgc_mcp.utils import fetch_text_resilient, parse_ev_string, parse_iv_string


async def fetch_pokepaste(url: str) -> FetchResult[str]:
    """Fetch raw paste content from pokepast.es.

    Args:
        url: The pokepaste URL (e.g., https://pokepast.es/abc123)

    Returns:
        FetchResult with raw paste text or error information
    """
    # Convert to raw URL format
    if not url.endswith("/raw"):
        raw_url = url.rstrip("/") + "/raw"
    else:
        raw_url = url

    return await fetch_text_resilient(raw_url, service="pokepaste", timeout=30.0, verify=False)


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
                evs = parse_ev_string(line)
                pokemon.hp_ev = evs["hp"]
                pokemon.atk_ev = evs["atk"]
                pokemon.def_ev = evs["def"]
                pokemon.spa_ev = evs["spa"]
                pokemon.spd_ev = evs["spd"]
                pokemon.spe_ev = evs["spe"]
            elif line.startswith("IVs:"):
                ivs = parse_iv_string(line)
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

        # Assign moves (up to 4)
        move_attrs = ["move1", "move2", "move3", "move4"]
        for i, move in enumerate(moves[:4]):
            setattr(pokemon, move_attrs[i], move)

        pokemon_list.append(pokemon)

    return pokemon_list
