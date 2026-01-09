"""Fetch and parse Pokedex data from Pokemon Showdown."""

import json
import re
from pathlib import Path

import aiosqlite

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import fetch_json_resilient, fetch_text_resilient

# Pokemon Showdown data URLs
POKEDEX_JSON_URL = "https://play.pokemonshowdown.com/data/pokedex.json"
MOVES_JSON_URL = "https://play.pokemonshowdown.com/data/moves.json"
LEARNSETS_JSON_URL = "https://play.pokemonshowdown.com/data/learnsets.json"
ABILITIES_TS_URL = (
    "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/abilities.ts"
)
ITEMS_TS_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/items.ts"

# Type effectiveness chart (attacking_type -> defending_type -> multiplier)
# 0 = immune, 0.5 = resisted, 1 = neutral, 2 = super effective
TYPE_CHART: dict[str, dict[str, float]] = {
    "Normal": {
        "Rock": 0.5,
        "Ghost": 0,
        "Steel": 0.5,
    },
    "Fire": {
        "Fire": 0.5,
        "Water": 0.5,
        "Grass": 2,
        "Ice": 2,
        "Bug": 2,
        "Rock": 0.5,
        "Dragon": 0.5,
        "Steel": 2,
    },
    "Water": {
        "Fire": 2,
        "Water": 0.5,
        "Grass": 0.5,
        "Ground": 2,
        "Rock": 2,
        "Dragon": 0.5,
    },
    "Electric": {
        "Water": 2,
        "Electric": 0.5,
        "Grass": 0.5,
        "Ground": 0,
        "Flying": 2,
        "Dragon": 0.5,
    },
    "Grass": {
        "Fire": 0.5,
        "Water": 2,
        "Grass": 0.5,
        "Poison": 0.5,
        "Ground": 2,
        "Flying": 0.5,
        "Bug": 0.5,
        "Rock": 2,
        "Dragon": 0.5,
        "Steel": 0.5,
    },
    "Ice": {
        "Fire": 0.5,
        "Water": 0.5,
        "Grass": 2,
        "Ice": 0.5,
        "Ground": 2,
        "Flying": 2,
        "Dragon": 2,
        "Steel": 0.5,
    },
    "Fighting": {
        "Normal": 2,
        "Ice": 2,
        "Poison": 0.5,
        "Flying": 0.5,
        "Psychic": 0.5,
        "Bug": 0.5,
        "Rock": 2,
        "Ghost": 0,
        "Dark": 2,
        "Steel": 2,
        "Fairy": 0.5,
    },
    "Poison": {
        "Grass": 2,
        "Poison": 0.5,
        "Ground": 0.5,
        "Rock": 0.5,
        "Ghost": 0.5,
        "Steel": 0,
        "Fairy": 2,
    },
    "Ground": {
        "Fire": 2,
        "Electric": 2,
        "Grass": 0.5,
        "Poison": 2,
        "Flying": 0,
        "Bug": 0.5,
        "Rock": 2,
        "Steel": 2,
    },
    "Flying": {
        "Electric": 0.5,
        "Grass": 2,
        "Fighting": 2,
        "Bug": 2,
        "Rock": 0.5,
        "Steel": 0.5,
    },
    "Psychic": {
        "Fighting": 2,
        "Poison": 2,
        "Psychic": 0.5,
        "Dark": 0,
        "Steel": 0.5,
    },
    "Bug": {
        "Fire": 0.5,
        "Grass": 2,
        "Fighting": 0.5,
        "Poison": 0.5,
        "Flying": 0.5,
        "Psychic": 2,
        "Ghost": 0.5,
        "Dark": 2,
        "Steel": 0.5,
        "Fairy": 0.5,
    },
    "Rock": {
        "Fire": 2,
        "Ice": 2,
        "Fighting": 0.5,
        "Ground": 0.5,
        "Flying": 2,
        "Bug": 2,
        "Steel": 0.5,
    },
    "Ghost": {
        "Normal": 0,
        "Psychic": 2,
        "Ghost": 2,
        "Dark": 0.5,
    },
    "Dragon": {
        "Dragon": 2,
        "Steel": 0.5,
        "Fairy": 0,
    },
    "Dark": {
        "Fighting": 0.5,
        "Psychic": 2,
        "Ghost": 2,
        "Dark": 0.5,
        "Fairy": 0.5,
    },
    "Steel": {
        "Fire": 0.5,
        "Water": 0.5,
        "Electric": 0.5,
        "Ice": 2,
        "Rock": 2,
        "Steel": 0.5,
        "Fairy": 2,
    },
    "Fairy": {
        "Fire": 0.5,
        "Fighting": 2,
        "Poison": 0.5,
        "Dragon": 2,
        "Dark": 2,
        "Steel": 0.5,
    },
}

ALL_TYPES = [
    "Normal",
    "Fire",
    "Water",
    "Electric",
    "Grass",
    "Ice",
    "Fighting",
    "Poison",
    "Ground",
    "Flying",
    "Psychic",
    "Bug",
    "Rock",
    "Ghost",
    "Dragon",
    "Dark",
    "Steel",
    "Fairy",
]


def _extract_balanced_brace_content(content: str, start: int) -> tuple[str, int]:
    """Extract content between balanced braces, handling nested braces.

    Handles:
    - Nested braces
    - Single and double quoted strings
    - Template literals (backticks)
    - Single-line comments (//)
    - Multi-line comments (/* */)
    - Escaped characters in strings

    Args:
        content: The full string content
        start: Position of opening brace

    Returns:
        Tuple of (extracted content, end position)
    """
    if content[start] != "{":
        return "", start

    length = len(content)
    depth = 1
    pos = start + 1
    in_string: str | None = None  # None, '"', "'", or '`'
    escape_next = False

    while pos < length and depth > 0:
        char = content[pos]

        # Handle escape sequences in strings
        if escape_next:
            escape_next = False
            pos += 1
            continue

        # Check for escape character in strings
        if in_string is not None and char == "\\":
            escape_next = True
            pos += 1
            continue

        # Handle string delimiters
        if char == '"' or char == "'" or char == "`":
            if in_string is None:
                in_string = char
            elif in_string == char:
                in_string = None
            pos += 1
            continue

        # Skip content inside strings
        if in_string is not None:
            pos += 1
            continue

        # Handle single-line comments (//)
        if char == "/" and pos + 1 < length and content[pos + 1] == "/":
            # Skip to end of line
            newline_pos = content.find("\n", pos)
            if newline_pos == -1:
                pos = length
            else:
                pos = newline_pos + 1
            continue

        # Handle multi-line comments (/* */)
        if char == "/" and pos + 1 < length and content[pos + 1] == "*":
            # Skip to end of comment
            end_comment = content.find("*/", pos + 2)
            if end_comment == -1:
                pos = length
            else:
                pos = end_comment + 2
            continue

        # Track brace depth
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

        pos += 1

    return content[start + 1 : pos - 1], pos


def parse_ts_object(content: str, object_name: str) -> dict:
    """Parse a TypeScript object export into a Python dict.

    Handles the pattern: export const ObjectName: Type = { ... }
    Extracts key fields: name, num, desc, shortDesc, rating, gen, fling
    Uses brace-balancing to handle nested structures and functions.
    """
    result = {}

    # Find the start of the object
    pattern = rf"export const {object_name}[^=]*=\s*\{{"
    match = re.search(pattern, content)
    if not match:
        return result

    # Start position after the opening brace
    main_start = match.end() - 1
    main_content, _ = _extract_balanced_brace_content(content, main_start)

    # Find each top-level entry: keyname: { ... },
    entry_pattern = r"(\w+):\s*\{"
    pos = 0
    while pos < len(main_content):
        entry_match = re.search(entry_pattern, main_content[pos:])
        if not entry_match:
            break

        key = entry_match.group(1)
        brace_start = pos + entry_match.end() - 1

        # Extract the full entry content using brace balancing
        entry_content, end_pos = _extract_balanced_brace_content(main_content, brace_start)
        pos = end_pos

        entry = {"id": key}

        # Extract name
        name_match = re.search(r'name:\s*"([^"]+)"', entry_content)
        if name_match:
            entry["name"] = name_match.group(1)

        # Extract num
        num_match = re.search(r"num:\s*(\d+)", entry_content)
        if num_match:
            entry["num"] = int(num_match.group(1))

        # Extract desc
        desc_match = re.search(r'desc:\s*"([^"]*(?:\\.[^"]*)*)"', entry_content)
        if desc_match:
            entry["desc"] = desc_match.group(1).replace('\\"', '"')

        # Extract shortDesc
        short_match = re.search(r'shortDesc:\s*"([^"]*(?:\\.[^"]*)*)"', entry_content)
        if short_match:
            entry["shortDesc"] = short_match.group(1).replace('\\"', '"')

        # Extract rating (for abilities)
        rating_match = re.search(r"rating:\s*([\d.-]+)", entry_content)
        if rating_match:
            entry["rating"] = float(rating_match.group(1))

        # Extract gen (for items)
        gen_match = re.search(r"gen:\s*(\d+)", entry_content)
        if gen_match:
            entry["gen"] = int(gen_match.group(1))

        # Extract fling basePower (for items)
        fling_match = re.search(r"fling:\s*\{[^}]*basePower:\s*(\d+)", entry_content)
        if fling_match:
            entry["flingPower"] = int(fling_match.group(1))

        # Extract isNonstandard
        nonstandard_match = re.search(r'isNonstandard:\s*"([^"]+)"', entry_content)
        if nonstandard_match:
            entry["isNonstandard"] = nonstandard_match.group(1)

        if "name" in entry:
            result[key] = entry

    return result


async def store_pokemon_data(db: aiosqlite.Connection, data: dict) -> int:
    """Store Pokemon species data."""
    # Clear existing data
    await db.execute("DELETE FROM dex_pokemon")

    count = 0
    for pokemon_id, pokemon in data.items():
        types = pokemon.get("types", [])
        stats = pokemon.get("baseStats", {})
        abilities = pokemon.get("abilities", {})

        # Skip entries without types (e.g., special formes, cosmetic entries)
        if not types:
            continue

        await db.execute(
            """INSERT OR REPLACE INTO dex_pokemon
               (id, num, name, type1, type2, hp, atk, def, spa, spd, spe,
                ability1, ability2, ability_hidden, height_m, weight_kg,
                color, tier, prevo, evo_level, base_species, forme, is_nonstandard)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pokemon_id,
                pokemon.get("num"),
                pokemon.get("name"),
                types[0] if types else None,
                types[1] if len(types) > 1 else None,
                stats.get("hp"),
                stats.get("atk"),
                stats.get("def"),
                stats.get("spa"),
                stats.get("spd"),
                stats.get("spe"),
                abilities.get("0"),
                abilities.get("1"),
                abilities.get("H"),
                pokemon.get("heightm"),
                pokemon.get("weightkg"),
                pokemon.get("color"),
                pokemon.get("tier"),
                pokemon.get("prevo"),
                pokemon.get("evoLevel"),
                pokemon.get("baseSpecies"),
                pokemon.get("forme"),
                pokemon.get("isNonstandard"),
            ),
        )
        count += 1

    await db.commit()
    return count


async def store_moves_data(db: aiosqlite.Connection, data: dict) -> int:
    """Store move data."""
    await db.execute("DELETE FROM dex_moves")

    count = 0
    for move_id, move in data.items():
        accuracy = move.get("accuracy")
        if accuracy is True:
            accuracy = None  # "always hits"

        await db.execute(
            """INSERT OR REPLACE INTO dex_moves
               (id, num, name, type, category, base_power, accuracy, pp,
                priority, target, description, short_desc, is_nonstandard)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                move_id,
                move.get("num"),
                move.get("name"),
                move.get("type"),
                move.get("category"),
                move.get("basePower"),
                accuracy,
                move.get("pp"),
                move.get("priority", 0),
                move.get("target"),
                move.get("desc"),
                move.get("shortDesc"),
                move.get("isNonstandard"),
            ),
        )
        count += 1

    await db.commit()
    return count


async def store_abilities_data(db: aiosqlite.Connection, data: dict) -> int:
    """Store ability data."""
    await db.execute("DELETE FROM dex_abilities")

    count = 0
    for ability_id, ability in data.items():
        await db.execute(
            """INSERT OR REPLACE INTO dex_abilities
               (id, num, name, description, short_desc, rating, is_nonstandard)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                ability_id,
                ability.get("num"),
                ability.get("name"),
                ability.get("desc"),
                ability.get("shortDesc"),
                ability.get("rating"),
                ability.get("isNonstandard"),
            ),
        )
        count += 1

    await db.commit()
    return count


async def store_items_data(db: aiosqlite.Connection, data: dict) -> int:
    """Store item data."""
    await db.execute("DELETE FROM dex_items")

    count = 0
    for item_id, item in data.items():
        await db.execute(
            """INSERT OR REPLACE INTO dex_items
               (id, num, name, description, short_desc, fling_power, gen, is_nonstandard)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_id,
                item.get("num"),
                item.get("name"),
                item.get("desc"),
                item.get("shortDesc"),
                item.get("flingPower"),
                item.get("gen"),
                item.get("isNonstandard"),
            ),
        )
        count += 1

    await db.commit()
    return count


async def store_learnsets_data(db: aiosqlite.Connection, data: dict) -> int:
    """Store learnset data."""
    await db.execute("DELETE FROM dex_learnsets")

    count = 0
    for pokemon_id, pokemon_data in data.items():
        learnset = pokemon_data.get("learnset", {})
        for move_id, methods in learnset.items():
            await db.execute(
                """INSERT OR REPLACE INTO dex_learnsets
                   (pokemon_id, move_id, methods)
                   VALUES (?, ?, ?)""",
                (pokemon_id, move_id, json.dumps(methods)),
            )
            count += 1

    await db.commit()
    return count


async def store_type_chart(db: aiosqlite.Connection) -> int:
    """Store type effectiveness chart."""
    await db.execute("DELETE FROM dex_type_chart")

    count = 0
    for attacking_type in ALL_TYPES:
        for defending_type in ALL_TYPES:
            multiplier = TYPE_CHART.get(attacking_type, {}).get(defending_type, 1.0)
            await db.execute(
                """INSERT OR REPLACE INTO dex_type_chart
                   (attacking_type, defending_type, multiplier)
                   VALUES (?, ?, ?)""",
                (attacking_type, defending_type, multiplier),
            )
            count += 1

    await db.commit()
    return count


async def fetch_and_store_pokedex_all(db_path: Path | None = None) -> dict:
    """Fetch and store all Pokedex data.

    Returns:
        Dict with fetch results including error details and circuit states
    """
    if db_path is None:
        db_path = get_db_path()

    # Initialize database
    await init_database(db_path)

    errors: list[dict] = []
    pokemon_count = 0
    moves_count = 0
    abilities_count = 0
    items_count = 0
    learnsets_count = 0
    type_chart_count = 0

    async with get_connection(db_path) as db:
        # Fetch and store Pokemon
        print("Fetching Pokemon data...")
        pokemon_result = await fetch_json_resilient(POKEDEX_JSON_URL, service="showdown")
        if pokemon_result.success and pokemon_result.data:
            pokemon_count = await store_pokemon_data(db, pokemon_result.data)
            print(f"  Stored {pokemon_count} Pokemon")
        else:
            error_info = {"source": "Pokemon", "message": "Failed to fetch Pokemon data"}
            if pokemon_result.error:
                error_info.update(pokemon_result.error.to_dict())
            errors.append(error_info)

        # Fetch and store Moves
        print("Fetching Moves data...")
        moves_result = await fetch_json_resilient(MOVES_JSON_URL, service="showdown")
        if moves_result.success and moves_result.data:
            moves_count = await store_moves_data(db, moves_result.data)
            print(f"  Stored {moves_count} moves")
        else:
            error_info = {"source": "Moves", "message": "Failed to fetch Moves data"}
            if moves_result.error:
                error_info.update(moves_result.error.to_dict())
            errors.append(error_info)

        # Fetch and store Abilities (from TypeScript)
        print("Fetching Abilities data...")
        abilities_result = await fetch_text_resilient(ABILITIES_TS_URL, service="showdown")
        if abilities_result.success and abilities_result.data:
            abilities_data = parse_ts_object(abilities_result.data, "Abilities")
            abilities_count = await store_abilities_data(db, abilities_data)
            print(f"  Stored {abilities_count} abilities")
        else:
            error_info = {"source": "Abilities", "message": "Failed to fetch Abilities data"}
            if abilities_result.error:
                error_info.update(abilities_result.error.to_dict())
            errors.append(error_info)

        # Fetch and store Items (from TypeScript)
        print("Fetching Items data...")
        items_result = await fetch_text_resilient(ITEMS_TS_URL, service="showdown")
        if items_result.success and items_result.data:
            items_data = parse_ts_object(items_result.data, "Items")
            items_count = await store_items_data(db, items_data)
            print(f"  Stored {items_count} items")
        else:
            error_info = {"source": "Items", "message": "Failed to fetch Items data"}
            if items_result.error:
                error_info.update(items_result.error.to_dict())
            errors.append(error_info)

        # Fetch and store Learnsets
        print("Fetching Learnsets data...")
        learnsets_result = await fetch_json_resilient(LEARNSETS_JSON_URL, service="showdown")
        if learnsets_result.success and learnsets_result.data:
            learnsets_count = await store_learnsets_data(db, learnsets_result.data)
            print(f"  Stored {learnsets_count} learnset entries")
        else:
            error_info = {"source": "Learnsets", "message": "Failed to fetch Learnsets data"}
            if learnsets_result.error:
                error_info.update(learnsets_result.error.to_dict())
            errors.append(error_info)

        # Store Type Chart
        print("Storing Type Chart...")
        type_chart_count = await store_type_chart(db)
        print(f"  Stored {type_chart_count} type matchups")

    return {
        "pokemon": pokemon_count,
        "moves": moves_count,
        "abilities": abilities_count,
        "items": items_count,
        "learnsets": learnsets_count,
        "type_chart": type_chart_count,
        "errors": errors if errors else None,
        "circuit_states": get_all_circuit_states(),
    }
