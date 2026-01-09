"""Database query functions for Smogon VGC stats."""

import json
from pathlib import Path

import aiosqlite

from smogon_vgc_mcp.database.models import (
    AbilityUsage,
    CheckCounter,
    DexAbility,
    DexItem,
    DexMove,
    DexPokemon,
    EVSpread,
    ItemUsage,
    MoveUsage,
    PokemonStats,
    Snapshot,
    Team,
    TeammateUsage,
    TeamPokemon,
    TeraTypeUsage,
    UsageRanking,
)
from smogon_vgc_mcp.database.schema import get_connection
from smogon_vgc_mcp.logging import log_database_operation


async def get_snapshot(
    format_code: str,
    month: str,
    elo: int,
    db_path: Path | None = None,
) -> Snapshot | None:
    """Get a snapshot by format, month and ELO bracket."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM snapshots WHERE format = ? AND month = ? AND elo_bracket = ?",
            (format_code, month, elo),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Snapshot(
                    id=row["id"],
                    format=row["format"],
                    month=row["month"],
                    elo_bracket=row["elo_bracket"],
                    num_battles=row["num_battles"],
                    fetched_at=row["fetched_at"],
                )
    return None


async def get_all_snapshots(
    format_code: str | None = None,
    db_path: Path | None = None,
) -> list[Snapshot]:
    """Get all available snapshots, optionally filtered by format."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row
        if format_code:
            query = (
                "SELECT * FROM snapshots WHERE format = ? ORDER BY format, month DESC, elo_bracket"
            )
            params: tuple = (format_code,)
        else:
            query = "SELECT * FROM snapshots ORDER BY format, month DESC, elo_bracket"
            params = ()
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                Snapshot(
                    id=row["id"],
                    format=row["format"],
                    month=row["month"],
                    elo_bracket=row["elo_bracket"],
                    num_battles=row["num_battles"],
                    fetched_at=row["fetched_at"],
                )
                for row in rows
            ]


@log_database_operation("get_pokemon_stats")
async def get_pokemon_stats(
    pokemon: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    db_path: Path | None = None,
) -> PokemonStats | None:
    """Get comprehensive stats for a Pokemon."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get snapshot
        async with db.execute(
            "SELECT id, num_battles FROM snapshots "
            "WHERE format = ? AND month = ? AND elo_bracket = ?",
            (format_code, month, elo),
        ) as cursor:
            snapshot_row = await cursor.fetchone()
            if not snapshot_row:
                return None

        snapshot_id = snapshot_row["id"]
        num_battles = snapshot_row["num_battles"]

        # Get pokemon usage
        async with db.execute(
            """SELECT * FROM pokemon_usage
               WHERE snapshot_id = ? AND LOWER(pokemon) = LOWER(?)""",
            (snapshot_id, pokemon),
        ) as cursor:
            pokemon_row = await cursor.fetchone()
            if not pokemon_row:
                return None

        pokemon_usage_id = pokemon_row["id"]
        raw_count = pokemon_row["raw_count"]

        # Calculate usage percent
        usage_percent = (raw_count / (num_battles * 2) * 100) if num_battles > 0 else 0

        # Parse viability ceiling
        viability = json.loads(pokemon_row["viability_ceiling"] or "[]")

        # Get abilities
        abilities = []
        async with db.execute(
            "SELECT * FROM abilities WHERE pokemon_usage_id = ? ORDER BY count DESC",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                abilities.append(
                    AbilityUsage(
                        ability=row["ability"],
                        count=row["count"],
                        percent=row["percent"],
                    )
                )

        # Get items
        items = []
        async with db.execute(
            "SELECT * FROM items WHERE pokemon_usage_id = ? ORDER BY count DESC LIMIT 15",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                items.append(
                    ItemUsage(
                        item=row["item"],
                        count=row["count"],
                        percent=row["percent"],
                    )
                )

        # Get moves
        moves = []
        async with db.execute(
            "SELECT * FROM moves WHERE pokemon_usage_id = ? ORDER BY count DESC LIMIT 15",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                moves.append(
                    MoveUsage(
                        move=row["move"],
                        count=row["count"],
                        percent=row["percent"],
                    )
                )

        # Get teammates
        teammates = []
        async with db.execute(
            "SELECT * FROM teammates WHERE pokemon_usage_id = ? ORDER BY count DESC LIMIT 10",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                teammates.append(
                    TeammateUsage(
                        teammate=row["teammate"],
                        count=row["count"],
                        percent=row["percent"],
                    )
                )

        # Get spreads
        spreads = []
        async with db.execute(
            "SELECT * FROM spreads WHERE pokemon_usage_id = ? ORDER BY count DESC LIMIT 10",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                spreads.append(
                    EVSpread(
                        nature=row["nature"],
                        hp=row["hp"],
                        atk=row["atk"],
                        def_=row["def"],
                        spa=row["spa"],
                        spd=row["spd"],
                        spe=row["spe"],
                        count=row["count"],
                        percent=row["percent"],
                    )
                )

        # Get tera types (from moveset data)
        tera_types = []
        async with db.execute(
            "SELECT * FROM tera_types WHERE pokemon_usage_id = ? ORDER BY percent DESC LIMIT 10",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                tera_types.append(
                    TeraTypeUsage(
                        tera_type=row["tera_type"],
                        percent=row["percent"],
                    )
                )

        # Get checks/counters (from moveset data)
        checks_counters = []
        async with db.execute(
            "SELECT * FROM checks_counters WHERE pokemon_usage_id = ? ORDER BY score DESC LIMIT 10",
            (pokemon_usage_id,),
        ) as cursor:
            async for row in cursor:
                checks_counters.append(
                    CheckCounter(
                        counter=row["counter"],
                        score=row["score"],
                        win_percent=row["win_percent"],
                        ko_percent=row["ko_percent"],
                        switch_percent=row["switch_percent"],
                    )
                )

        return PokemonStats(
            pokemon=pokemon_row["pokemon"],
            raw_count=raw_count,
            usage_percent=usage_percent,
            viability_ceiling=viability,
            abilities=abilities,
            items=items,
            moves=moves,
            teammates=teammates,
            spreads=spreads,
            tera_types=tera_types,
            checks_counters=checks_counters,
        )


@log_database_operation("get_usage_rankings")
async def get_usage_rankings(
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[UsageRanking]:
    """Get top Pokemon by usage rate."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get snapshot
        async with db.execute(
            "SELECT id, num_battles FROM snapshots "
            "WHERE format = ? AND month = ? AND elo_bracket = ?",
            (format_code, month, elo),
        ) as cursor:
            snapshot_row = await cursor.fetchone()
            if not snapshot_row:
                return []

        snapshot_id = snapshot_row["id"]
        num_battles = snapshot_row["num_battles"]

        rankings = []
        async with db.execute(
            """SELECT pokemon, raw_count FROM pokemon_usage
               WHERE snapshot_id = ?
               ORDER BY raw_count DESC
               LIMIT ?""",
            (snapshot_id, limit),
        ) as cursor:
            rank = 1
            async for row in cursor:
                raw_count = row["raw_count"]
                usage_percent = (raw_count / (num_battles * 2) * 100) if num_battles > 0 else 0
                rankings.append(
                    UsageRanking(
                        rank=rank,
                        pokemon=row["pokemon"],
                        usage_percent=round(usage_percent, 2),
                        raw_count=raw_count,
                    )
                )
                rank += 1

        return rankings


@log_database_operation("search_pokemon")
async def search_pokemon(
    query: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    db_path: Path | None = None,
) -> list[str]:
    """Search for Pokemon by partial name match."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT DISTINCT pu.pokemon FROM pokemon_usage pu
               JOIN snapshots s ON pu.snapshot_id = s.id
               WHERE s.format = ? AND s.month = ? AND s.elo_bracket = ?
               AND LOWER(pu.pokemon) LIKE LOWER(?)
               ORDER BY pu.raw_count DESC
               LIMIT 20""",
            (format_code, month, elo, f"%{query}%"),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row["pokemon"] for row in rows]


async def get_teammates(
    pokemon: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    limit: int = 10,
    db_path: Path | None = None,
) -> list[TeammateUsage]:
    """Get most common teammates for a Pokemon."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT t.teammate, t.count, t.percent FROM teammates t
               JOIN pokemon_usage pu ON t.pokemon_usage_id = pu.id
               JOIN snapshots s ON pu.snapshot_id = s.id
               WHERE s.format = ? AND s.month = ? AND s.elo_bracket = ?
               AND LOWER(pu.pokemon) = LOWER(?)
               ORDER BY t.count DESC
               LIMIT ?""",
            (format_code, month, elo, pokemon, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                TeammateUsage(
                    teammate=row["teammate"],
                    count=row["count"],
                    percent=row["percent"],
                )
                for row in rows
            ]


async def find_by_item(
    item: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    limit: int = 10,
    db_path: Path | None = None,
) -> list[dict]:
    """Find Pokemon that commonly use a specific item."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT pu.pokemon, i.count, i.percent FROM items i
               JOIN pokemon_usage pu ON i.pokemon_usage_id = pu.id
               JOIN snapshots s ON pu.snapshot_id = s.id
               WHERE s.format = ? AND s.month = ? AND s.elo_bracket = ?
               AND LOWER(i.item) = LOWER(?)
               ORDER BY i.count DESC
               LIMIT ?""",
            (format_code, month, elo, item, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "pokemon": row["pokemon"],
                    "count": row["count"],
                    "percent": row["percent"],
                }
                for row in rows
            ]


async def find_by_move(
    move: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    limit: int = 10,
    db_path: Path | None = None,
) -> list[dict]:
    """Find Pokemon that commonly use a specific move."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT pu.pokemon, m.count, m.percent FROM moves m
               JOIN pokemon_usage pu ON m.pokemon_usage_id = pu.id
               JOIN snapshots s ON pu.snapshot_id = s.id
               WHERE s.format = ? AND s.month = ? AND s.elo_bracket = ?
               AND LOWER(m.move) = LOWER(?)
               ORDER BY m.count DESC
               LIMIT ?""",
            (format_code, month, elo, move, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "pokemon": row["pokemon"],
                    "count": row["count"],
                    "percent": row["percent"],
                }
                for row in rows
            ]


async def find_by_tera_type(
    tera_type: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    limit: int = 10,
    db_path: Path | None = None,
) -> list[dict]:
    """Find Pokemon that commonly use a specific Tera Type."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT pu.pokemon, tt.percent FROM tera_types tt
               JOIN pokemon_usage pu ON tt.pokemon_usage_id = pu.id
               JOIN snapshots s ON pu.snapshot_id = s.id
               WHERE s.format = ? AND s.month = ? AND s.elo_bracket = ?
               AND LOWER(tt.tera_type) = LOWER(?)
               ORDER BY tt.percent DESC
               LIMIT ?""",
            (format_code, month, elo, tera_type, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "pokemon": row["pokemon"],
                    "percent": row["percent"],
                }
                for row in rows
            ]


async def get_counters_for(
    pokemon: str,
    format_code: str = "regf",
    month: str = "2025-12",
    elo: int = 1500,
    limit: int = 10,
    db_path: Path | None = None,
) -> list[CheckCounter]:
    """Get Pokemon that counter a specific Pokemon."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT cc.* FROM checks_counters cc
               JOIN pokemon_usage pu ON cc.pokemon_usage_id = pu.id
               JOIN snapshots s ON pu.snapshot_id = s.id
               WHERE s.format = ? AND s.month = ? AND s.elo_bracket = ?
               AND LOWER(pu.pokemon) = LOWER(?)
               ORDER BY cc.score DESC
               LIMIT ?""",
            (format_code, month, elo, pokemon, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                CheckCounter(
                    counter=row["counter"],
                    score=row["score"],
                    win_percent=row["win_percent"],
                    ko_percent=row["ko_percent"],
                    switch_percent=row["switch_percent"],
                )
                for row in rows
            ]


# =============================================================================
# Team query functions (pokepaste repository)
# =============================================================================


@log_database_operation("get_team")
async def get_team(
    team_id: str,
    format_code: str | None = None,
    db_path: Path | None = None,
) -> Team | None:
    """Get a team by its ID (e.g., 'F123') with all Pokemon details."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get team metadata - if format provided, filter by it
        if format_code:
            query = "SELECT * FROM teams WHERE format = ? AND team_id = ?"
            params: tuple = (format_code, team_id)
        else:
            query = "SELECT * FROM teams WHERE team_id = ?"
            params = (team_id,)
        async with db.execute(query, params) as cursor:
            team_row = await cursor.fetchone()
            if not team_row:
                return None

        # Get team Pokemon
        pokemon_list = []
        async with db.execute(
            """SELECT * FROM team_pokemon WHERE team_id = ? ORDER BY slot""",
            (team_row["id"],),
        ) as cursor:
            async for row in cursor:
                pokemon_list.append(
                    TeamPokemon(
                        slot=row["slot"],
                        pokemon=row["pokemon"],
                        item=row["item"],
                        ability=row["ability"],
                        tera_type=row["tera_type"],
                        nature=row["nature"],
                        hp_ev=row["hp_ev"],
                        atk_ev=row["atk_ev"],
                        def_ev=row["def_ev"],
                        spa_ev=row["spa_ev"],
                        spd_ev=row["spd_ev"],
                        spe_ev=row["spe_ev"],
                        hp_iv=row["hp_iv"],
                        atk_iv=row["atk_iv"],
                        def_iv=row["def_iv"],
                        spa_iv=row["spa_iv"],
                        spd_iv=row["spd_iv"],
                        spe_iv=row["spe_iv"],
                        move1=row["move1"],
                        move2=row["move2"],
                        move3=row["move3"],
                        move4=row["move4"],
                    )
                )

        return Team(
            id=team_row["id"],
            format=team_row["format"],
            team_id=team_row["team_id"],
            description=team_row["description"],
            owner=team_row["owner"],
            tournament=team_row["tournament"],
            rank=team_row["rank"],
            rental_code=team_row["rental_code"],
            pokepaste_url=team_row["pokepaste_url"],
            source_url=team_row["source_url"],
            fetched_at=team_row["fetched_at"],
            pokemon=pokemon_list,
        )


@log_database_operation("search_teams")
async def search_teams(
    pokemon: str | None = None,
    tournament: str | None = None,
    owner: str | None = None,
    format_code: str | None = None,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[Team]:
    """Search teams by Pokemon, tournament, owner, or format."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query dynamically
        conditions = []
        params: list = []

        if format_code:
            conditions.append("t.format = ?")
            params.append(format_code)

        if pokemon:
            conditions.append(
                """t.id IN (SELECT team_id FROM team_pokemon
                           WHERE LOWER(pokemon) LIKE LOWER(?))"""
            )
            params.append(f"%{pokemon}%")

        if tournament:
            conditions.append("LOWER(t.tournament) LIKE LOWER(?)")
            params.append(f"%{tournament}%")

        if owner:
            conditions.append("LOWER(t.owner) LIKE LOWER(?)")
            params.append(f"%{owner}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        query = f"""SELECT * FROM teams t WHERE {where_clause} LIMIT ?"""

        teams = []
        async with db.execute(query, params) as cursor:
            async for row in cursor:
                # Get Pokemon for this team
                pokemon_list = []
                async with db.execute(
                    "SELECT * FROM team_pokemon WHERE team_id = ? ORDER BY slot",
                    (row["id"],),
                ) as pokemon_cursor:
                    async for p_row in pokemon_cursor:
                        pokemon_list.append(
                            TeamPokemon(
                                slot=p_row["slot"],
                                pokemon=p_row["pokemon"],
                                item=p_row["item"],
                                ability=p_row["ability"],
                                tera_type=p_row["tera_type"],
                                nature=p_row["nature"],
                                hp_ev=p_row["hp_ev"],
                                atk_ev=p_row["atk_ev"],
                                def_ev=p_row["def_ev"],
                                spa_ev=p_row["spa_ev"],
                                spd_ev=p_row["spd_ev"],
                                spe_ev=p_row["spe_ev"],
                                hp_iv=p_row["hp_iv"],
                                atk_iv=p_row["atk_iv"],
                                def_iv=p_row["def_iv"],
                                spa_iv=p_row["spa_iv"],
                                spd_iv=p_row["spd_iv"],
                                spe_iv=p_row["spe_iv"],
                                move1=p_row["move1"],
                                move2=p_row["move2"],
                                move3=p_row["move3"],
                                move4=p_row["move4"],
                            )
                        )

                teams.append(
                    Team(
                        id=row["id"],
                        format=row["format"],
                        team_id=row["team_id"],
                        description=row["description"],
                        owner=row["owner"],
                        tournament=row["tournament"],
                        rank=row["rank"],
                        rental_code=row["rental_code"],
                        pokepaste_url=row["pokepaste_url"],
                        source_url=row["source_url"],
                        fetched_at=row["fetched_at"],
                        pokemon=pokemon_list,
                    )
                )

        return teams


async def get_tournament_ev_spreads(
    pokemon: str,
    format_code: str | None = None,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[dict]:
    """Get all EV spreads for a Pokemon from tournament teams.

    Returns spreads with frequency counts across all teams.
    """
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        if format_code:
            query = """SELECT
                   nature,
                   hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev,
                   COUNT(*) as count,
                   GROUP_CONCAT(t.team_id) as team_ids
               FROM team_pokemon tp
               JOIN teams t ON tp.team_id = t.id
               WHERE t.format = ? AND LOWER(tp.pokemon) LIKE LOWER(?)
               GROUP BY nature, hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev
               ORDER BY count DESC
               LIMIT ?"""
            params: tuple = (format_code, f"%{pokemon}%", limit)
        else:
            query = """SELECT
                   nature,
                   hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev,
                   COUNT(*) as count,
                   GROUP_CONCAT(t.team_id) as team_ids
               FROM team_pokemon tp
               JOIN teams t ON tp.team_id = t.id
               WHERE LOWER(tp.pokemon) LIKE LOWER(?)
               GROUP BY nature, hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev
               ORDER BY count DESC
               LIMIT ?"""
            params = (f"%{pokemon}%", limit)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "nature": row["nature"],
                    "evs": (
                        f"{row['hp_ev']}/{row['atk_ev']}/{row['def_ev']}/"
                        f"{row['spa_ev']}/{row['spd_ev']}/{row['spe_ev']}"
                    ),
                    "hp": row["hp_ev"],
                    "atk": row["atk_ev"],
                    "def": row["def_ev"],
                    "spa": row["spa_ev"],
                    "spd": row["spd_ev"],
                    "spe": row["spe_ev"],
                    "count": row["count"],
                    "team_ids": row["team_ids"].split(",") if row["team_ids"] else [],
                }
                for row in rows
            ]


async def get_teams_with_core(
    pokemon_list: list[str],
    format_code: str | None = None,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[Team]:
    """Find teams that contain all specified Pokemon."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query to find teams containing ALL specified Pokemon
        pokemon_conditions: list[str] = []
        params: list = []

        if format_code:
            pokemon_conditions.append("t.format = ?")
            params.append(format_code)

        for poke in pokemon_list:
            pokemon_conditions.append(
                """EXISTS (SELECT 1 FROM team_pokemon tp
                          WHERE tp.team_id = t.id
                          AND LOWER(tp.pokemon) LIKE LOWER(?))"""
            )
            params.append(f"%{poke}%")

        where_clause = " AND ".join(pokemon_conditions)
        params.append(limit)

        query = f"""SELECT * FROM teams t WHERE {where_clause} LIMIT ?"""

        teams = []
        async with db.execute(query, params) as cursor:
            async for row in cursor:
                # Get Pokemon for this team
                pokemon_details = []
                async with db.execute(
                    "SELECT * FROM team_pokemon WHERE team_id = ? ORDER BY slot",
                    (row["id"],),
                ) as pokemon_cursor:
                    async for p_row in pokemon_cursor:
                        pokemon_details.append(
                            TeamPokemon(
                                slot=p_row["slot"],
                                pokemon=p_row["pokemon"],
                                item=p_row["item"],
                                ability=p_row["ability"],
                                tera_type=p_row["tera_type"],
                                nature=p_row["nature"],
                                hp_ev=p_row["hp_ev"],
                                atk_ev=p_row["atk_ev"],
                                def_ev=p_row["def_ev"],
                                spa_ev=p_row["spa_ev"],
                                spd_ev=p_row["spd_ev"],
                                spe_ev=p_row["spe_ev"],
                                hp_iv=p_row["hp_iv"],
                                atk_iv=p_row["atk_iv"],
                                def_iv=p_row["def_iv"],
                                spa_iv=p_row["spa_iv"],
                                spd_iv=p_row["spd_iv"],
                                spe_iv=p_row["spe_iv"],
                                move1=p_row["move1"],
                                move2=p_row["move2"],
                                move3=p_row["move3"],
                                move4=p_row["move4"],
                            )
                        )

                teams.append(
                    Team(
                        id=row["id"],
                        format=row["format"],
                        team_id=row["team_id"],
                        description=row["description"],
                        owner=row["owner"],
                        tournament=row["tournament"],
                        rank=row["rank"],
                        rental_code=row["rental_code"],
                        pokepaste_url=row["pokepaste_url"],
                        source_url=row["source_url"],
                        fetched_at=row["fetched_at"],
                        pokemon=pokemon_details,
                    )
                )

        return teams


async def get_team_count(
    format_code: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Get total number of teams in database, optionally filtered by format."""
    async with get_connection(db_path) as db:
        if format_code:
            query = "SELECT COUNT(*) FROM teams WHERE format = ?"
            params: tuple = (format_code,)
        else:
            query = "SELECT COUNT(*) FROM teams"
            params = ()
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_team_pokemon_count(db_path: Path | None = None) -> int:
    """Get total number of team Pokemon entries in database."""
    async with get_connection(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM team_pokemon") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# =============================================================================
# Pokedex query functions (Pokemon Showdown data)
# =============================================================================


@log_database_operation("get_dex_pokemon")
async def get_dex_pokemon(
    pokemon_id: str,
    db_path: Path | None = None,
) -> DexPokemon | None:
    """Get Pokedex data for a Pokemon by ID."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Try exact ID match first, then name match
        async with db.execute(
            """SELECT * FROM dex_pokemon
               WHERE id = ? OR LOWER(name) = LOWER(?)""",
            (pokemon_id.lower().replace(" ", "").replace("-", ""), pokemon_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            types = [row["type1"]]
            if row["type2"]:
                types.append(row["type2"])

            abilities = []
            if row["ability1"]:
                abilities.append(row["ability1"])
            if row["ability2"]:
                abilities.append(row["ability2"])

            return DexPokemon(
                id=row["id"],
                num=row["num"],
                name=row["name"],
                types=types,
                base_stats={
                    "hp": row["hp"],
                    "atk": row["atk"],
                    "def": row["def"],
                    "spa": row["spa"],
                    "spd": row["spd"],
                    "spe": row["spe"],
                },
                abilities=abilities,
                ability_hidden=row["ability_hidden"],
                height_m=row["height_m"] or 0.0,
                weight_kg=row["weight_kg"] or 0.0,
                tier=row["tier"],
                prevo=row["prevo"],
                evo_level=row["evo_level"],
                base_species=row["base_species"],
                forme=row["forme"],
            )


async def search_dex_pokemon(
    query: str,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[DexPokemon]:
    """Search Pokemon by name (partial match)."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_pokemon
               WHERE LOWER(name) LIKE LOWER(?)
               AND is_nonstandard IS NULL
               ORDER BY num
               LIMIT ?""",
            (f"%{query}%", limit),
        ) as cursor:
            results = []
            async for row in cursor:
                types = [row["type1"]]
                if row["type2"]:
                    types.append(row["type2"])

                abilities = []
                if row["ability1"]:
                    abilities.append(row["ability1"])
                if row["ability2"]:
                    abilities.append(row["ability2"])

                results.append(
                    DexPokemon(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        types=types,
                        base_stats={
                            "hp": row["hp"],
                            "atk": row["atk"],
                            "def": row["def"],
                            "spa": row["spa"],
                            "spd": row["spd"],
                            "spe": row["spe"],
                        },
                        abilities=abilities,
                        ability_hidden=row["ability_hidden"],
                        height_m=row["height_m"] or 0.0,
                        weight_kg=row["weight_kg"] or 0.0,
                        tier=row["tier"],
                        prevo=row["prevo"],
                        evo_level=row["evo_level"],
                        base_species=row["base_species"],
                        forme=row["forme"],
                    )
                )
            return results


async def get_pokemon_by_type(
    pokemon_type: str,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[DexPokemon]:
    """Get Pokemon of a specific type."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_pokemon
               WHERE (LOWER(type1) = LOWER(?) OR LOWER(type2) = LOWER(?))
               AND is_nonstandard IS NULL
               ORDER BY num
               LIMIT ?""",
            (pokemon_type, pokemon_type, limit),
        ) as cursor:
            results = []
            async for row in cursor:
                types = [row["type1"]]
                if row["type2"]:
                    types.append(row["type2"])

                abilities = []
                if row["ability1"]:
                    abilities.append(row["ability1"])
                if row["ability2"]:
                    abilities.append(row["ability2"])

                results.append(
                    DexPokemon(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        types=types,
                        base_stats={
                            "hp": row["hp"],
                            "atk": row["atk"],
                            "def": row["def"],
                            "spa": row["spa"],
                            "spd": row["spd"],
                            "spe": row["spe"],
                        },
                        abilities=abilities,
                        ability_hidden=row["ability_hidden"],
                        height_m=row["height_m"] or 0.0,
                        weight_kg=row["weight_kg"] or 0.0,
                        tier=row["tier"],
                        prevo=row["prevo"],
                        evo_level=row["evo_level"],
                        base_species=row["base_species"],
                        forme=row["forme"],
                    )
                )
            return results


async def get_dex_move(
    move_id: str,
    db_path: Path | None = None,
) -> DexMove | None:
    """Get move data by ID."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_moves
               WHERE id = ? OR LOWER(name) = LOWER(?)""",
            (move_id.lower().replace(" ", "").replace("-", ""), move_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            return DexMove(
                id=row["id"],
                num=row["num"],
                name=row["name"],
                type=row["type"],
                category=row["category"],
                base_power=row["base_power"],
                accuracy=row["accuracy"],
                pp=row["pp"],
                priority=row["priority"] or 0,
                target=row["target"],
                description=row["description"],
                short_desc=row["short_desc"],
            )


async def search_dex_moves(
    query: str,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[DexMove]:
    """Search moves by name (partial match)."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_moves
               WHERE LOWER(name) LIKE LOWER(?)
               AND is_nonstandard IS NULL
               ORDER BY name
               LIMIT ?""",
            (f"%{query}%", limit),
        ) as cursor:
            results = []
            async for row in cursor:
                results.append(
                    DexMove(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        type=row["type"],
                        category=row["category"],
                        base_power=row["base_power"],
                        accuracy=row["accuracy"],
                        pp=row["pp"],
                        priority=row["priority"] or 0,
                        target=row["target"],
                        description=row["description"],
                        short_desc=row["short_desc"],
                    )
                )
            return results


async def get_moves_by_type(
    move_type: str,
    category: str | None = None,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[DexMove]:
    """Get moves of a specific type, optionally filtered by category."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        if category:
            query = """SELECT * FROM dex_moves
                       WHERE LOWER(type) = LOWER(?)
                       AND LOWER(category) = LOWER(?)
                       AND is_nonstandard IS NULL
                       ORDER BY base_power DESC NULLS LAST
                       LIMIT ?"""
            params = (move_type, category, limit)
        else:
            query = """SELECT * FROM dex_moves
                       WHERE LOWER(type) = LOWER(?)
                       AND is_nonstandard IS NULL
                       ORDER BY base_power DESC NULLS LAST
                       LIMIT ?"""
            params = (move_type, limit)

        async with db.execute(query, params) as cursor:
            results = []
            async for row in cursor:
                results.append(
                    DexMove(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        type=row["type"],
                        category=row["category"],
                        base_power=row["base_power"],
                        accuracy=row["accuracy"],
                        pp=row["pp"],
                        priority=row["priority"] or 0,
                        target=row["target"],
                        description=row["description"],
                        short_desc=row["short_desc"],
                    )
                )
            return results


async def get_pokemon_learnset(
    pokemon_id: str,
    db_path: Path | None = None,
) -> list[DexMove]:
    """Get all moves a Pokemon can learn."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Normalize pokemon ID
        normalized_id = pokemon_id.lower().replace(" ", "").replace("-", "")

        async with db.execute(
            """SELECT m.* FROM dex_moves m
               JOIN dex_learnsets l ON m.id = l.move_id
               WHERE l.pokemon_id = ?
               ORDER BY m.name""",
            (normalized_id,),
        ) as cursor:
            results = []
            async for row in cursor:
                results.append(
                    DexMove(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        type=row["type"],
                        category=row["category"],
                        base_power=row["base_power"],
                        accuracy=row["accuracy"],
                        pp=row["pp"],
                        priority=row["priority"] or 0,
                        target=row["target"],
                        description=row["description"],
                        short_desc=row["short_desc"],
                    )
                )
            return results


async def get_dex_ability(
    ability_id: str,
    db_path: Path | None = None,
) -> DexAbility | None:
    """Get ability data by ID."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_abilities
               WHERE id = ? OR LOWER(name) = LOWER(?)""",
            (ability_id.lower().replace(" ", "").replace("-", ""), ability_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            return DexAbility(
                id=row["id"],
                num=row["num"],
                name=row["name"],
                description=row["description"],
                short_desc=row["short_desc"],
                rating=row["rating"] or 0.0,
            )


async def search_dex_abilities(
    query: str,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[DexAbility]:
    """Search abilities by name (partial match)."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_abilities
               WHERE LOWER(name) LIKE LOWER(?)
               AND is_nonstandard IS NULL
               ORDER BY name
               LIMIT ?""",
            (f"%{query}%", limit),
        ) as cursor:
            results = []
            async for row in cursor:
                results.append(
                    DexAbility(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        description=row["description"],
                        short_desc=row["short_desc"],
                        rating=row["rating"] or 0.0,
                    )
                )
            return results


async def get_dex_item(
    item_id: str,
    db_path: Path | None = None,
) -> DexItem | None:
    """Get item data by ID."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_items
               WHERE id = ? OR LOWER(name) = LOWER(?)""",
            (item_id.lower().replace(" ", "").replace("-", ""), item_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            return DexItem(
                id=row["id"],
                num=row["num"],
                name=row["name"],
                description=row["description"],
                short_desc=row["short_desc"],
                fling_power=row["fling_power"],
                gen=row["gen"],
            )


async def search_dex_items(
    query: str,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[DexItem]:
    """Search items by name (partial match)."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT * FROM dex_items
               WHERE LOWER(name) LIKE LOWER(?)
               AND is_nonstandard IS NULL
               ORDER BY name
               LIMIT ?""",
            (f"%{query}%", limit),
        ) as cursor:
            results = []
            async for row in cursor:
                results.append(
                    DexItem(
                        id=row["id"],
                        num=row["num"],
                        name=row["name"],
                        description=row["description"],
                        short_desc=row["short_desc"],
                        fling_power=row["fling_power"],
                        gen=row["gen"],
                    )
                )
            return results


async def get_type_effectiveness(
    attacking_type: str,
    defending_types: list[str],
    db_path: Path | None = None,
) -> dict:
    """Calculate type effectiveness multiplier for an attack against defending types."""
    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        multiplier = 1.0
        details = {}

        for defending_type in defending_types:
            async with db.execute(
                """SELECT multiplier FROM dex_type_chart
                   WHERE LOWER(attacking_type) = LOWER(?)
                   AND LOWER(defending_type) = LOWER(?)""",
                (attacking_type, defending_type),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    type_mult = row["multiplier"]
                    details[defending_type] = type_mult
                    multiplier *= type_mult
                else:
                    details[defending_type] = 1.0

        return {
            "attacking_type": attacking_type,
            "defending_types": defending_types,
            "multiplier": multiplier,
            "effectiveness": _effectiveness_label(multiplier),
            "details": details,
        }


def _effectiveness_label(multiplier: float) -> str:
    """Convert multiplier to human-readable label."""
    if multiplier == 0:
        return "immune"
    elif multiplier < 1:
        return "resisted"
    elif multiplier > 1:
        return "super effective"
    return "neutral"


async def get_pokemon_type_matchups(
    pokemon_id: str,
    db_path: Path | None = None,
) -> dict | None:
    """Get type weaknesses and resistances for a Pokemon."""
    # First get the Pokemon's types
    pokemon = await get_dex_pokemon(pokemon_id, db_path)
    if not pokemon:
        return None

    async with get_connection(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get all type matchups
        weaknesses = {}
        resistances = {}
        immunities = {}

        # Get all attacking types
        async with db.execute("SELECT DISTINCT attacking_type FROM dex_type_chart") as cursor:
            attacking_types = [row["attacking_type"] async for row in cursor]

        for atk_type in attacking_types:
            multiplier = 1.0
            for def_type in pokemon.types:
                async with db.execute(
                    """SELECT multiplier FROM dex_type_chart
                       WHERE attacking_type = ? AND defending_type = ?""",
                    (atk_type, def_type),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        multiplier *= row["multiplier"]

            if multiplier == 0:
                immunities[atk_type] = multiplier
            elif multiplier < 1:
                resistances[atk_type] = multiplier
            elif multiplier > 1:
                weaknesses[atk_type] = multiplier

        return {
            "pokemon": pokemon.name,
            "types": pokemon.types,
            "weaknesses": weaknesses,
            "resistances": resistances,
            "immunities": immunities,
        }


async def get_pokedex_stats(db_path: Path | None = None) -> dict:
    """Get counts of Pokedex data."""
    async with get_connection(db_path) as db:
        counts = {}

        for table in ["dex_pokemon", "dex_moves", "dex_abilities", "dex_items", "dex_learnsets"]:
            async with db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                row = await cursor.fetchone()
                counts[table.replace("dex_", "")] = row[0] if row else 0

        return counts
