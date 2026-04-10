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
