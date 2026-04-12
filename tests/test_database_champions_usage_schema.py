"""Tests that champions_usage tables exist with expected columns."""

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import SCHEMA

EXPECTED_TABLES = {
    "champions_usage_snapshots",
    "champions_pokemon_usage",
    "champions_usage_moves",
    "champions_usage_items",
    "champions_usage_abilities",
    "champions_usage_teammates",
}


@pytest.mark.asyncio
async def test_champions_usage_tables_exist() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            names = {row[0] async for row in cursor}
    assert EXPECTED_TABLES <= names


@pytest.mark.asyncio
async def test_champions_pokemon_usage_columns() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        async with db.execute("PRAGMA table_info(champions_pokemon_usage)") as cursor:
            cols = {row[1] async for row in cursor}
    assert {"id", "snapshot_id", "pokemon", "usage_percent", "rank"} <= cols


@pytest.mark.asyncio
async def test_cascade_delete_removes_children() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        cursor = await db.execute(
            "INSERT INTO champions_usage_snapshots (elo_cutoff) VALUES ('0+')"
        )
        snap_id = cursor.lastrowid
        pu_cursor = await db.execute(
            "INSERT INTO champions_pokemon_usage (snapshot_id, pokemon) VALUES (?, 'incineroar')",
            (snap_id,),
        )
        pu_id = pu_cursor.lastrowid
        await db.execute(
            "INSERT INTO champions_usage_moves"
            " (pokemon_usage_id, move, percent) VALUES (?, 'Fake Out', 95.0)",
            (pu_id,),
        )
        await db.execute("DELETE FROM champions_usage_snapshots WHERE id = ?", (snap_id,))
        async with db.execute("SELECT COUNT(*) FROM champions_pokemon_usage") as c:
            (pu_count,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_moves") as c:
            (moves_count,) = await c.fetchone()
    assert pu_count == 0
    assert moves_count == 0


@pytest.mark.asyncio
async def test_unique_snapshot_per_source_elo() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("INSERT INTO champions_usage_snapshots (elo_cutoff) VALUES ('0+')")
        with pytest.raises(aiosqlite.IntegrityError):
            await db.execute("INSERT INTO champions_usage_snapshots (elo_cutoff) VALUES ('0+')")


@pytest.mark.asyncio
async def test_get_connection_enables_foreign_keys(tmp_path) -> None:
    """Regression: get_connection must enable PRAGMA foreign_keys so ON DELETE
    CASCADE works at the application layer, not just in ad-hoc raw connects.
    """
    from smogon_vgc_mcp.database.schema import get_connection, init_database

    db_path = tmp_path / "fk.db"
    await init_database(db_path)
    async with get_connection(db_path) as db:
        async with db.execute("PRAGMA foreign_keys") as cursor:
            row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 1, "PRAGMA foreign_keys must be ON inside get_connection"


@pytest.mark.asyncio
async def test_row_to_champions_move_preserves_nulls(tmp_path) -> None:
    """Regression: _row_to_champions_move must pass NULL `num`/`pp`/`priority`
    through as None rather than silently coercing to 0.  Coercion would hide
    genuine DB drift behind a plausible-looking zero.
    """
    from smogon_vgc_mcp.database.queries import get_champions_move
    from smogon_vgc_mcp.database.schema import get_connection, init_database

    db_path = tmp_path / "nulls.db"
    await init_database(db_path)
    async with get_connection(db_path) as db:
        await db.execute(
            """INSERT INTO champions_dex_moves
               (id, num, name, type, category, base_power, accuracy, pp,
                priority, target, description, short_desc)
               VALUES ('protect', NULL, 'Protect', 'Normal', 'Status',
                       NULL, NULL, NULL, NULL, NULL, NULL, NULL)"""
        )
        await db.commit()

    move = await get_champions_move("protect", db_path=db_path)
    assert move is not None
    assert move.num is None, "NULL num must not be coerced to 0"
    assert move.pp is None, "NULL pp must not be coerced to 0"
    assert move.priority is None, "NULL priority must not be coerced to 0"
