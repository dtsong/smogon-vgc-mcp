"""Schema migration tests for the Nugget Bridge archive tables."""

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import (
    init_database,
    migrate_add_nugget_bridge_tables,
)

NB_TABLES = {"nb_posts", "nb_sets", "nb_chunks", "nb_chunk_embeddings"}


@pytest.mark.asyncio
async def test_init_creates_nb_tables(tmp_path):
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            names = {row[0] async for row in cursor}

    assert NB_TABLES.issubset(names)


@pytest.mark.asyncio
async def test_migration_is_idempotent(tmp_path):
    """Running init twice must not raise (CREATE TABLE IF NOT EXISTS)."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)
    await init_database(db_path)

    async with aiosqlite.connect(db_path) as db:
        await migrate_add_nugget_bridge_tables(db)  # third call, direct


@pytest.mark.asyncio
async def test_nb_posts_columns(tmp_path):
    """Pipeline status columns must exist so the ingest CLI can checkpoint."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("PRAGMA table_info(nb_posts)") as cursor:
            cols = {row[1] async for row in cursor}

    required = {
        "id",
        "slug",
        "url",
        "title",
        "published_at",
        "content_html",
        "format",
        "format_confidence",
        "fetch_status",
        "extract_status",
        "chunk_status",
        "embed_status",
        "extract_cost_usd",
        "embed_cost_usd",
    }
    missing = required - cols
    assert not missing, f"nb_posts missing columns: {missing}"


@pytest.mark.asyncio
async def test_nb_sets_foreign_key_cascade(tmp_path):
    """Deleting a post should cascade to its extracted sets."""
    db_path = tmp_path / "test.db"
    await init_database(db_path)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO nb_posts (id, slug, url, title, content_html)
               VALUES (1, 'test', 'http://x', 'T', '<p>hi</p>')"""
        )
        await db.execute(
            """INSERT INTO nb_sets (post_id, pokemon, pokemon_normalized)
               VALUES (1, 'Kartana', 'kartana')"""
        )
        await db.commit()

        await db.execute("DELETE FROM nb_posts WHERE id = 1")
        await db.commit()

        async with db.execute("SELECT COUNT(*) FROM nb_sets") as cursor:
            (count,) = await cursor.fetchone()
        assert count == 0
