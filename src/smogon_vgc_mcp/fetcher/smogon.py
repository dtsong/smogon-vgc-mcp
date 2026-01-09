"""Fetch and parse Smogon VGC stats."""

import json
import re
from pathlib import Path

import aiosqlite
import httpx

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.formats import DEFAULT_FORMAT, get_format, get_smogon_stats_url


async def fetch_vgc_data(format_code: str, month: str, elo: int) -> dict | None:
    """Fetch VGC data from Smogon for a specific format, month and ELO bracket.

    Args:
        format_code: Format code (e.g., "regf")
        month: Month in YYYY-MM format (e.g., "2025-12")
        elo: ELO bracket (0, 1500, 1630, 1760)

    Returns:
        Parsed JSON data or None if fetch failed
    """
    url = get_smogon_stats_url(format_code, month, elo)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Failed to fetch {url}: {e}")
            return None


def parse_spread(spread_str: str) -> dict | None:
    """Parse a spread string like 'Careful:252/4/140/0/76/36' into components."""
    match = re.match(r"(\w+):(\d+)/(\d+)/(\d+)/(\d+)/(\d+)/(\d+)", spread_str)
    if match:
        return {
            "nature": match.group(1),
            "hp": int(match.group(2)),
            "atk": int(match.group(3)),
            "def": int(match.group(4)),
            "spa": int(match.group(5)),
            "spd": int(match.group(6)),
            "spe": int(match.group(7)),
        }
    return None


async def store_snapshot_data(
    db: aiosqlite.Connection,
    format_code: str,
    month: str,
    elo: int,
    data: dict,
) -> int:
    """Store fetched data into the database.

    Returns the snapshot ID.
    """
    info = data.get("info", {})
    pokemon_data = data.get("data", {})

    num_battles = info.get("number of battles", 0)

    # Insert or replace snapshot
    await db.execute(
        """INSERT OR REPLACE INTO snapshots (format, month, elo_bracket, num_battles, fetched_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (format_code, month, elo, num_battles),
    )
    await db.commit()

    # Get snapshot ID
    async with db.execute(
        "SELECT id FROM snapshots WHERE format = ? AND month = ? AND elo_bracket = ?",
        (format_code, month, elo),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Snapshot not found for {month} {elo}")
        snapshot_id = row[0]

    # Clear existing data for this snapshot
    await db.execute(
        "DELETE FROM pokemon_usage WHERE snapshot_id = ?",
        (snapshot_id,),
    )

    # Insert Pokemon data
    for pokemon_name, pokemon_stats in pokemon_data.items():
        raw_count = pokemon_stats.get("Raw count", 0)
        viability = json.dumps(pokemon_stats.get("Viability Ceiling", []))

        await db.execute(
            """INSERT INTO pokemon_usage
               (snapshot_id, pokemon, raw_count, usage_percent, viability_ceiling)
               VALUES (?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                pokemon_name,
                raw_count,
                (raw_count / (num_battles * 2) * 100) if num_battles > 0 else 0,
                viability,
            ),
        )

        # Get pokemon_usage_id
        async with db.execute(
            "SELECT id FROM pokemon_usage WHERE snapshot_id = ? AND pokemon = ?",
            (snapshot_id, pokemon_name),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise RuntimeError(f"Pokemon usage not found for {pokemon_name}")
            pokemon_usage_id = row[0]

        # Insert abilities
        abilities = pokemon_stats.get("Abilities", {})
        total_abilities = sum(abilities.values()) if abilities else 1
        for ability, count in abilities.items():
            await db.execute(
                """INSERT INTO abilities (pokemon_usage_id, ability, count, percent)
                   VALUES (?, ?, ?, ?)""",
                (pokemon_usage_id, ability, count, (count / total_abilities * 100)),
            )

        # Insert items
        items = pokemon_stats.get("Items", {})
        total_items = sum(items.values()) if items else 1
        for item, count in items.items():
            await db.execute(
                "INSERT INTO items (pokemon_usage_id, item, count, percent) VALUES (?, ?, ?, ?)",
                (pokemon_usage_id, item, count, (count / total_items * 100)),
            )

        # Insert moves
        moves = pokemon_stats.get("Moves", {})
        total_moves = sum(moves.values()) if moves else 1
        for move, count in moves.items():
            await db.execute(
                "INSERT INTO moves (pokemon_usage_id, move, count, percent) VALUES (?, ?, ?, ?)",
                (pokemon_usage_id, move, count, (count / total_moves * 100)),
            )

        # Insert teammates
        teammates = pokemon_stats.get("Teammates", {})
        total_teammates = sum(teammates.values()) if teammates else 1
        for teammate, count in teammates.items():
            await db.execute(
                """INSERT INTO teammates (pokemon_usage_id, teammate, count, percent)
                   VALUES (?, ?, ?, ?)""",
                (pokemon_usage_id, teammate, count, (count / total_teammates * 100)),
            )

        # Insert spreads (top 50 only to save space)
        spreads = pokemon_stats.get("Spreads", {})
        total_spreads = sum(spreads.values()) if spreads else 1
        sorted_spreads = sorted(spreads.items(), key=lambda x: x[1], reverse=True)[:50]
        for spread_str, count in sorted_spreads:
            parsed = parse_spread(spread_str)
            if parsed:
                await db.execute(
                    """INSERT INTO spreads
                       (pokemon_usage_id, nature, hp, atk, def, spa, spd, spe, count, percent)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        pokemon_usage_id,
                        parsed["nature"],
                        parsed["hp"],
                        parsed["atk"],
                        parsed["def"],
                        parsed["spa"],
                        parsed["spd"],
                        parsed["spe"],
                        count,
                        (count / total_spreads * 100),
                    ),
                )

    await db.commit()
    return snapshot_id


async def fetch_and_store_all(
    format_code: str = DEFAULT_FORMAT,
    months: list[str] | None = None,
    elos: list[int] | None = None,
    db_path: Path | None = None,
) -> dict:
    """Fetch and store all VGC data for a format.

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

    # Initialize database
    await init_database(db_path)

    success: list[dict] = []
    failed: list[dict] = []
    total_pokemon = 0

    async with get_connection(db_path) as db:
        for month in months:
            for elo in elos:
                print(f"Fetching {fmt.name} {month} ELO {elo}...")
                data = await fetch_vgc_data(format_code, month, elo)

                if data:
                    await store_snapshot_data(db, format_code, month, elo, data)
                    pokemon_count = len(data.get("data", {}))
                    success.append(
                        {
                            "month": month,
                            "elo": elo,
                            "pokemon_count": pokemon_count,
                        }
                    )
                    total_pokemon += pokemon_count
                    print(f"  Stored {pokemon_count} Pokemon")
                else:
                    failed.append({"month": month, "elo": elo})
                    print("  Failed to fetch")

    return {
        "success": success,
        "failed": failed,
        "total_pokemon": total_pokemon,
    }
