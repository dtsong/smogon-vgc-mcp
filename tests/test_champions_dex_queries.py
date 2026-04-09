"""Tests for Champions Pokedex database schema."""

import pytest
import aiosqlite

from smogon_vgc_mcp.database.schema import SCHEMA


async def _init_db(db_path):
    """Helper: initialise a fresh DB at db_path using the SCHEMA string."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    return db_path


async def _get_tables(db_path) -> set[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cursor:
            rows = await cursor.fetchall()
    return {row[0] for row in rows}


async def _get_columns(db_path, table: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(f"PRAGMA table_info({table})") as cursor:
            rows = await cursor.fetchall()
    return [row[1] for row in rows]


class TestChampionsTablesExist:
    """Champions tables are created by init_database / SCHEMA."""

    @pytest.mark.asyncio
    async def test_champions_dex_pokemon_table_exists(self, tmp_path):
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        tables = await _get_tables(db_path)
        assert "champions_dex_pokemon" in tables

    @pytest.mark.asyncio
    async def test_champions_dex_moves_table_exists(self, tmp_path):
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        tables = await _get_tables(db_path)
        assert "champions_dex_moves" in tables

    @pytest.mark.asyncio
    async def test_champions_dex_abilities_table_exists(self, tmp_path):
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        tables = await _get_tables(db_path)
        assert "champions_dex_abilities" in tables

    @pytest.mark.asyncio
    async def test_champions_dex_learnsets_table_exists(self, tmp_path):
        db_path = tmp_path / "test.db.db"
        await _init_db(db_path)
        tables = await _get_tables(db_path)
        assert "champions_dex_learnsets" in tables


class TestChampionsPokemonColumns:
    """champions_dex_pokemon has the expected columns including Mega-related ones."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.db_path = tmp_path / "test.db"

    @pytest.mark.asyncio
    async def test_base_form_id_column_exists(self):
        await _init_db(self.db_path)
        columns = await _get_columns(self.db_path, "champions_dex_pokemon")
        assert "base_form_id" in columns

    @pytest.mark.asyncio
    async def test_is_mega_column_exists(self):
        await _init_db(self.db_path)
        columns = await _get_columns(self.db_path, "champions_dex_pokemon")
        assert "is_mega" in columns

    @pytest.mark.asyncio
    async def test_mega_stone_column_exists(self):
        await _init_db(self.db_path)
        columns = await _get_columns(self.db_path, "champions_dex_pokemon")
        assert "mega_stone" in columns

    @pytest.mark.asyncio
    async def test_all_stat_columns_exist(self):
        await _init_db(self.db_path)
        columns = await _get_columns(self.db_path, "champions_dex_pokemon")
        for stat in ("hp", "atk", "def", "spa", "spd", "spe"):
            assert stat in columns, f"Missing stat column: {stat}"

    @pytest.mark.asyncio
    async def test_insert_base_pokemon(self):
        """Can insert a base-form Pokemon row."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO champions_dex_pokemon
                   (id, num, name, type1, hp, atk, def, spa, spd, spe)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("charizard", 6, "Charizard", "Fire", 78, 84, 78, 109, 85, 100),
            )
            await db.commit()
            async with db.execute(
                "SELECT is_mega, base_form_id, mega_stone FROM champions_dex_pokemon WHERE id='charizard'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 0       # is_mega default
        assert row[1] is None    # base_form_id
        assert row[2] is None    # mega_stone

    @pytest.mark.asyncio
    async def test_insert_mega_pokemon(self):
        """Can insert a Mega form with base_form_id link."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO champions_dex_pokemon
                   (id, num, name, type1, hp, atk, def, spa, spd, spe)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("charizard", 6, "Charizard", "Fire", 78, 84, 78, 109, 85, 100),
            )
            await db.execute(
                """INSERT INTO champions_dex_pokemon
                   (id, num, name, type1, type2, hp, atk, def, spa, spd, spe,
                    is_mega, base_form_id, mega_stone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "charizardmegax", 6, "Charizard-Mega-X", "Fire", "Dragon",
                    78, 130, 111, 130, 85, 100,
                    1, "charizard", "Charizardite X",
                ),
            )
            await db.commit()
            async with db.execute(
                "SELECT is_mega, base_form_id, mega_stone FROM champions_dex_pokemon WHERE id='charizardmegax'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row[0] == 1
        assert row[1] == "charizard"
        assert row[2] == "Charizardite X"
