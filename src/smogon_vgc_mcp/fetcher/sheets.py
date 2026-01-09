"""Fetch team data from Google Sheets pokepaste repository."""

import asyncio
import csv
import io
import re

import aiosqlite

from smogon_vgc_mcp.database.schema import get_connection, get_db_path, init_database
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste, parse_pokepaste
from smogon_vgc_mcp.formats import DEFAULT_FORMAT, get_format, get_sheet_csv_url
from smogon_vgc_mcp.utils import fetch_text


async def fetch_teams_from_sheet(format_code: str) -> list[dict]:
    """Fetch teams from Google Sheet for a specific format.

    Args:
        format_code: Format code (e.g., "regf")

    Returns:
        List of dicts with team metadata
    """
    fmt = get_format(format_code)
    sheet_url = get_sheet_csv_url(format_code)

    if not sheet_url:
        print(f"No Google Sheet configured for {fmt.name}")
        return []

    csv_text = await fetch_text(sheet_url)
    if not csv_text:
        print(f"Failed to fetch sheet for {fmt.name}")
        return []

    # Parse CSV as raw rows (no header inference - the sheet has complex multi-row headers)
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    teams = []

    # Build team ID pattern from format config
    team_id_pattern = rf"^{fmt.team_id_prefix}\d+$"

    for row in rows:
        if not row or len(row) < 2:
            continue

        # Check if first column is a team ID (prefix followed by digits)
        first_col = row[0].strip()
        if not re.match(team_id_pattern, first_col):
            continue

        team_id = first_col

        # Find pokepaste URL in this row
        pokepaste_url = None
        for cell in row:
            if cell and "pokepast.es" in cell:
                # Extract just the URL if there's extra content
                match = re.search(r"https?://pokepast\.es/[a-zA-Z0-9]+", cell)
                if match:
                    pokepaste_url = match.group(0)
                break

        # Extract other fields by position (based on sheet structure)
        description = row[1].strip() if len(row) > 1 else ""
        owner = row[3].strip() if len(row) > 3 else ""

        # Look for rental code - typically a 6-character alphanumeric code
        rental_code = None
        for cell in row:
            if cell and re.match(r"^[A-Z0-9]{6}$", cell.strip()):
                rental_code = cell.strip()
                break

        team = {
            "team_id": team_id,
            "description": description,
            "owner": owner,
            "tournament": "",  # Tournament info is in a merged cell, hard to extract
            "rank": "",
            "rental_code": rental_code,
            "pokepaste_url": pokepaste_url,
            "source_url": "",
        }

        teams.append(team)

    return teams


async def store_team(db: aiosqlite.Connection, format_code: str, team: dict) -> int | None:
    """Store a single team's metadata in the database.

    Args:
        db: Database connection
        format_code: Format code (e.g., "regf")
        team: Team metadata dict

    Returns:
        The team's database ID or None if team_id is missing
    """
    if not team.get("team_id"):
        return None

    await db.execute(
        """INSERT OR REPLACE INTO teams
           (format, team_id, description, owner, tournament, rank,
            rental_code, pokepaste_url, source_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            format_code,
            team["team_id"],
            team.get("description"),
            team.get("owner"),
            team.get("tournament"),
            team.get("rank"),
            team.get("rental_code"),
            team.get("pokepaste_url"),
            team.get("source_url"),
        ),
    )

    # Get the team ID
    async with db.execute(
        "SELECT id FROM teams WHERE format = ? AND team_id = ?",
        (format_code, team["team_id"]),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None


async def store_team_pokemon(db: aiosqlite.Connection, team_db_id: int, pokemon_list: list) -> None:
    """Store parsed Pokemon for a team."""
    # Clear existing Pokemon for this team
    await db.execute("DELETE FROM team_pokemon WHERE team_id = ?", (team_db_id,))

    for pokemon in pokemon_list:
        await db.execute(
            """INSERT INTO team_pokemon
               (team_id, slot, pokemon, item, ability, tera_type, nature,
                hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev,
                hp_iv, atk_iv, def_iv, spa_iv, spd_iv, spe_iv,
                move1, move2, move3, move4)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                team_db_id,
                pokemon.slot,
                pokemon.pokemon,
                pokemon.item,
                pokemon.ability,
                pokemon.tera_type,
                pokemon.nature,
                pokemon.hp_ev,
                pokemon.atk_ev,
                pokemon.def_ev,
                pokemon.spa_ev,
                pokemon.spd_ev,
                pokemon.spe_ev,
                pokemon.hp_iv,
                pokemon.atk_iv,
                pokemon.def_iv,
                pokemon.spa_iv,
                pokemon.spd_iv,
                pokemon.spe_iv,
                pokemon.move1,
                pokemon.move2,
                pokemon.move3,
                pokemon.move4,
            ),
        )


async def fetch_and_store_pokepaste_teams(
    format_code: str = DEFAULT_FORMAT,
    max_teams: int | None = None,
    delay_between_fetches: float = 0.5,
) -> dict:
    """Fetch all teams from Google Sheet and parse their pokepastes.

    Args:
        format_code: Format code (e.g., "regf")
        max_teams: Optional limit on number of teams to process
        delay_between_fetches: Delay between pokepaste fetches to be polite

    Returns:
        Dict with results summary
    """
    fmt = get_format(format_code)
    db_path = get_db_path()
    await init_database(db_path)

    print(f"Fetching team list from Google Sheet for {fmt.name}...")
    teams = await fetch_teams_from_sheet(format_code)
    print(f"Found {len(teams)} teams")

    if max_teams:
        teams = teams[:max_teams]

    success = []
    failed = []
    skipped = []

    async with get_connection(db_path) as db:
        for i, team in enumerate(teams):
            team_id = team.get("team_id", f"unknown_{i}")
            pokepaste_url = team.get("pokepaste_url")

            # Store team metadata
            team_db_id = await store_team(db, format_code, team)
            if team_db_id is None:
                skipped.append({"team_id": team_id, "reason": "no team_id"})
                continue

            if not pokepaste_url:
                skipped.append({"team_id": team_id, "reason": "no pokepaste URL"})
                await db.commit()
                continue

            print(f"Processing {team_id} ({i + 1}/{len(teams)})...")

            # Fetch and parse pokepaste
            paste_text = await fetch_pokepaste(pokepaste_url)
            if paste_text:
                pokemon_list = parse_pokepaste(paste_text)
                await store_team_pokemon(db, team_db_id, pokemon_list)
                success.append(
                    {
                        "team_id": team_id,
                        "pokemon_count": len(pokemon_list),
                    }
                )
                print(f"  Stored {len(pokemon_list)} Pokemon")
            else:
                failed.append({"team_id": team_id, "url": pokepaste_url})
                print("  Failed to fetch pokepaste")

            await db.commit()

            # Rate limiting
            if delay_between_fetches > 0:
                await asyncio.sleep(delay_between_fetches)

    return {
        "total_teams": len(teams),
        "success": len(success),
        "failed": len(failed),
        "skipped": len(skipped),
        "success_details": success[:10],  # Limit details in response
        "failed_details": failed[:10],
        "skipped_details": skipped[:10],
    }
