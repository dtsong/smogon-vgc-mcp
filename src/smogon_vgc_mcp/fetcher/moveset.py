"""Fetch and parse Smogon moveset text files for Tera Types and Checks/Counters."""

import logging
import re
from pathlib import Path

import aiosqlite

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.formats import DEFAULT_FORMAT, get_format, get_moveset_url
from smogon_vgc_mcp.utils import fetch_text

logger = logging.getLogger(__name__)


async def fetch_moveset_text(format_code: str, month: str, elo: int) -> str | None:
    """Fetch raw moveset text file from Smogon.

    Args:
        format_code: Format code (e.g., "regf")
        month: Month in YYYY-MM format (e.g., "2025-12")
        elo: ELO bracket (0, 1500, 1630, 1760)

    Returns:
        Raw text content or None if fetch failed
    """
    url = get_moveset_url(format_code, month, elo)
    return await fetch_text(url)


def parse_pokemon_blocks(text: str) -> list[tuple[str, str]]:
    """Split moveset text into individual Pokemon blocks.

    Args:
        text: Full moveset text file content

    Returns:
        List of (pokemon_name, block_content) tuples
    """
    blocks = []

    # Split by the separator pattern (line of +---+)
    # Each Pokemon block starts with a header like "| Flutter Mane |"
    pattern = r"\+-+\+\s*\n\s*\|\s*([^|]+?)\s*\|\s*\n\s*\+-+\+"

    # Find all Pokemon headers
    matches = list(re.finditer(pattern, text))

    for i, match in enumerate(matches):
        pokemon_name = match.group(1).strip()

        # Get the block content (from this match to the next Pokemon header)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        block_content = text[start:end]
        blocks.append((pokemon_name, block_content))

    return blocks


def parse_tera_types(block: str) -> list[tuple[str, float]]:
    """Parse Tera Types section from a Pokemon block.

    Args:
        block: Pokemon block content

    Returns:
        List of (tera_type, percent) tuples
    """
    tera_types = []

    # Find the Tera Types section
    tera_match = re.search(
        r"\|\s*Tera Types\s*\|\s*\n(.*?)(?:\+-+\+|\Z)",
        block,
        re.DOTALL,
    )

    if not tera_match:
        return tera_types

    tera_section = tera_match.group(1)

    # Parse lines like "| Fairy 87.893% |" or "| Grass  7.504% |"
    for line in tera_section.split("\n"):
        match = re.search(r"\|\s*(\w+)\s+([\d.]+)%", line)
        if match:
            tera_type = match.group(1)
            percent = float(match.group(2))
            if tera_type.lower() != "other":
                tera_types.append((tera_type, percent))

    return tera_types


def parse_checks_counters(block: str) -> list[dict]:
    """Parse Checks and Counters section from a Pokemon block.

    Args:
        block: Pokemon block content

    Returns:
        List of dicts with counter, score, win_percent, ko_percent, switch_percent
    """
    counters = []

    # Find the Checks and Counters section
    cc_match = re.search(
        r"\|\s*Checks and Counters\s*\|\s*\n(.*?)(?:\+-+\+|\Z)",
        block,
        re.DOTALL,
    )

    if not cc_match:
        return counters

    cc_section = cc_match.group(1)
    lines = cc_section.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Match lines like "| Rillaboom 52.526 (55.22±0.67) |"
        # or "| Tatsugiri 52.715 (59.46+-1.69) |"
        counter_match = re.search(
            r"\|\s*([A-Za-z][A-Za-z0-9\-]+(?:\s*\([A-Za-z\-]+\))?)\s+([\d.]+)\s+\(([\d.]+)[±+-]+([\d.]+)\)",
            line,
        )

        if counter_match:
            counter_name = counter_match.group(1).strip()
            score = float(counter_match.group(2))
            win_percent = float(counter_match.group(3))

            # Look for the next line with KO/switch percentages
            ko_percent = 0.0
            switch_percent = 0.0

            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # Match "(34.3% KOed / 25.2% switched out)"
                ko_switch_match = re.search(
                    r"\(([\d.]+)%\s*KOed\s*/\s*([\d.]+)%\s*switched",
                    next_line,
                )
                if ko_switch_match:
                    ko_percent = float(ko_switch_match.group(1))
                    switch_percent = float(ko_switch_match.group(2))
                    i += 1  # Skip the next line since we processed it

            counters.append(
                {
                    "counter": counter_name,
                    "score": score,
                    "win_percent": win_percent,
                    "ko_percent": ko_percent,
                    "switch_percent": switch_percent,
                }
            )

        i += 1

    return counters


async def store_moveset_data(
    db: aiosqlite.Connection,
    format_code: str,
    month: str,
    elo: int,
    pokemon_data: list[tuple[str, list[tuple[str, float]], list[dict]]],
) -> int:
    """Store parsed moveset data (tera types and checks/counters) into the database.

    Args:
        db: Database connection
        format_code: Format code
        month: Stats month
        elo: ELO bracket
        pokemon_data: List of (pokemon_name, tera_types, checks_counters)

    Returns:
        Number of Pokemon updated
    """
    # Get snapshot ID
    async with db.execute(
        "SELECT id FROM snapshots WHERE format = ? AND month = ? AND elo_bracket = ?",
        (format_code, month, elo),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            logger.warning(
                "No snapshot found for %s %s ELO %s - run refresh_data first",
                format_code,
                month,
                elo,
            )
            return 0
        snapshot_id = row[0]

    updated_count = 0

    for pokemon_name, tera_types, checks_counters in pokemon_data:
        # Get pokemon_usage_id
        async with db.execute(
            "SELECT id FROM pokemon_usage WHERE snapshot_id = ? AND LOWER(pokemon) = LOWER(?)",
            (snapshot_id, pokemon_name),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                continue
            pokemon_usage_id = row[0]

        # Clear existing tera types and checks/counters for this Pokemon
        await db.execute(
            "DELETE FROM tera_types WHERE pokemon_usage_id = ?",
            (pokemon_usage_id,),
        )
        await db.execute(
            "DELETE FROM checks_counters WHERE pokemon_usage_id = ?",
            (pokemon_usage_id,),
        )

        # Insert tera types
        for tera_type, percent in tera_types:
            await db.execute(
                "INSERT INTO tera_types (pokemon_usage_id, tera_type, percent) VALUES (?, ?, ?)",
                (pokemon_usage_id, tera_type, percent),
            )

        # Insert checks/counters
        for cc in checks_counters:
            await db.execute(
                """INSERT INTO checks_counters
                   (pokemon_usage_id, counter, score, win_percent, ko_percent, switch_percent)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    pokemon_usage_id,
                    cc["counter"],
                    cc["score"],
                    cc["win_percent"],
                    cc["ko_percent"],
                    cc["switch_percent"],
                ),
            )

        updated_count += 1

    await db.commit()
    return updated_count


async def fetch_and_store_moveset(
    format_code: str,
    month: str,
    elo: int,
    db_path: Path | None = None,
) -> dict:
    """Fetch and store moveset data for a specific format, month and ELO.

    Args:
        format_code: Format code (e.g., "regf")
        month: Month in YYYY-MM format
        elo: ELO bracket
        db_path: Optional database path

    Returns:
        Dict with fetch results
    """
    if db_path is None:
        db_path = get_db_path()

    text = await fetch_moveset_text(format_code, month, elo)
    if not text:
        return {"success": False, "month": month, "elo": elo, "error": "fetch_failed"}

    # Parse all Pokemon blocks
    blocks = parse_pokemon_blocks(text)

    pokemon_data = []
    for pokemon_name, block in blocks:
        tera_types = parse_tera_types(block)
        checks_counters = parse_checks_counters(block)
        pokemon_data.append((pokemon_name, tera_types, checks_counters))

    async with get_connection(db_path) as db:
        updated = await store_moveset_data(db, format_code, month, elo, pokemon_data)

    return {
        "success": True,
        "month": month,
        "elo": elo,
        "pokemon_parsed": len(pokemon_data),
        "pokemon_updated": updated,
    }


async def fetch_and_store_moveset_all(
    format_code: str = DEFAULT_FORMAT,
    months: list[str] | None = None,
    elos: list[int] | None = None,
    db_path: Path | None = None,
) -> dict:
    """Fetch and store moveset data for a format.

    Args:
        format_code: Format code (e.g., "regf")
        months: List of months to fetch (default: format's available months)
        elos: List of ELO brackets to fetch (default: format's available elos)
        db_path: Optional database path

    Returns:
        Dict with fetch results
    """
    fmt = get_format(format_code)

    if months is None:
        months = fmt.available_months
    if elos is None:
        elos = fmt.available_elos
    if db_path is None:
        db_path = get_db_path()

    # Ensure database is initialized
    await init_database(db_path)

    success: list[dict] = []
    failed: list[dict] = []
    total_pokemon = 0

    for month in months:
        for elo in elos:
            logger.info("Fetching moveset data for %s %s ELO %s", fmt.name, month, elo)
            result = await fetch_and_store_moveset(format_code, month, elo, db_path)

            if result["success"]:
                success.append(result)
                total_pokemon += result["pokemon_updated"]
                logger.info(
                    "Updated %d Pokemon for %s %s ELO %s",
                    result["pokemon_updated"],
                    fmt.name,
                    month,
                    elo,
                )
            else:
                failed.append(result)
                logger.error(
                    "Failed to fetch moveset for %s %s ELO %s: %s",
                    fmt.name,
                    month,
                    elo,
                    result.get("error", "unknown"),
                )

    return {
        "success": success,
        "failed": failed,
        "total_pokemon_updated": total_pokemon,
    }
