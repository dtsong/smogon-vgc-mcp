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
    "champions_usage_spreads",
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
