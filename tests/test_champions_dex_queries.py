"""Tests for Champions Pokedex database schema, store functions, and queries."""

import aiosqlite
import pytest

from smogon_vgc_mcp.database.models import ChampionsDexPokemon
from smogon_vgc_mcp.database.queries import (
    get_champions_pokemon,
    get_champions_pokemon_with_megas,
    search_champions_pokemon_by_type,
)
from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.champions_dex import store_champions_pokemon_data


async def _init_db(db_path):
    """Helper: initialise a fresh DB at db_path using the SCHEMA string."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    return db_path


async def _get_tables(db_path) -> set[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
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
                "SELECT is_mega, base_form_id, mega_stone"
                " FROM champions_dex_pokemon WHERE id='charizard'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 0  # is_mega default
        assert row[1] is None  # base_form_id
        assert row[2] is None  # mega_stone

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
                    "charizardmegax",
                    6,
                    "Charizard-Mega-X",
                    "Fire",
                    "Dragon",
                    78,
                    130,
                    111,
                    130,
                    85,
                    100,
                    1,
                    "charizard",
                    "Charizardite X",
                ),
            )
            await db.commit()
            async with db.execute(
                "SELECT is_mega, base_form_id, mega_stone"
                " FROM champions_dex_pokemon WHERE id='charizardmegax'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row[0] == 1
        assert row[1] == "charizard"
        assert row[2] == "Charizardite X"


# ---------------------------------------------------------------------------
# Task 6: store_champions_pokemon_data() tests
# ---------------------------------------------------------------------------

_CHARIZARD_PARSE_OUTPUT = {
    "id": "charizard",
    "num": 6,
    "name": "Charizard",
    "types": ["Fire", "Flying"],
    "base_stats": {"hp": 78, "atk": 104, "def": 78, "spa": 159, "spd": 115, "spe": 100},
    "abilities": ["Drought"],
    "ability_hidden": None,
    "height_m": 1.7,
    "weight_kg": 90.5,
    "mega_forms": [],
}

_CHARIZARD_WITH_MEGA = {
    "id": "charizard",
    "num": 6,
    "name": "Charizard",
    "types": ["Fire", "Flying"],
    "base_stats": {"hp": 78, "atk": 104, "def": 78, "spa": 159, "spd": 115, "spe": 100},
    "abilities": ["Drought"],
    "ability_hidden": None,
    "height_m": 1.7,
    "weight_kg": 90.5,
    "mega_forms": [
        {
            "slug": "charizard-mega-x",
            "name": "Mega Charizard X",
            "types": ["Fire", "Dragon"],
            "stats": {"hp": 78, "atk": 130, "def": 111, "spa": 130, "spd": 85, "spe": 100},
            "abilities": ["Tough Claws"],
            "height_m": 1.7,
            "weight_kg": 110.5,
            "mega_stone": "Charizardite X",
        }
    ],
}


class TestStoreChampionsPokemonData:
    """Tests for store_champions_pokemon_data()."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.db_path = tmp_path / "test.db"

    @pytest.mark.asyncio
    async def test_store_base_form_returns_count(self):
        """Storing one base form returns count=1."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            count = await store_champions_pokemon_data(db, [_CHARIZARD_PARSE_OUTPUT])
        assert count == 1

    @pytest.mark.asyncio
    async def test_store_base_form_correct_columns(self):
        """Stored base form has correct column values."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            await store_champions_pokemon_data(db, [_CHARIZARD_PARSE_OUTPUT])
            async with db.execute(
                "SELECT id, num, name, type1, type2, hp, atk,"
                " is_mega, base_form_id"
                " FROM champions_dex_pokemon WHERE id='charizard'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "charizard"
        assert row[1] == 6
        assert row[2] == "Charizard"
        assert row[3] == "Fire"
        assert row[4] == "Flying"
        assert row[5] == 78  # hp
        assert row[6] == 104  # atk
        assert row[7] == 0  # is_mega
        assert row[8] is None  # base_form_id

    @pytest.mark.asyncio
    async def test_store_with_mega_forms_count(self):
        """Storing base + 1 Mega returns count=2."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            count = await store_champions_pokemon_data(db, [_CHARIZARD_WITH_MEGA])
        assert count == 2

    @pytest.mark.asyncio
    async def test_stored_mega_has_base_form_id(self):
        """Stored Mega form has base_form_id=charizard and is_mega=1."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            await store_champions_pokemon_data(db, [_CHARIZARD_WITH_MEGA])
            async with db.execute(
                "SELECT is_mega, base_form_id, mega_stone,"
                " type1, type2 FROM champions_dex_pokemon"
                " WHERE id='charizard-mega-x'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1  # is_mega
        assert row[1] == "charizard"  # base_form_id
        assert row[2] == "Charizardite X"  # mega_stone
        assert row[3] == "Fire"
        assert row[4] == "Dragon"

    @pytest.mark.asyncio
    async def test_no_commit_when_commit_false(self):
        """_commit=False does not auto-commit; rows not visible outside transaction."""
        await _init_db(self.db_path)
        async with aiosqlite.connect(self.db_path) as db:
            await store_champions_pokemon_data(db, [_CHARIZARD_PARSE_OUTPUT], _commit=False)
            # Rollback without committing
            await db.rollback()

        # After rollback, no rows should exist
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM champions_dex_pokemon") as cursor:
                row = await cursor.fetchone()
        assert row[0] == 0


# ---------------------------------------------------------------------------
# Task 8: Champions Pokedex query function tests
# ---------------------------------------------------------------------------


async def _seed_db(db_path):
    """Seed test DB with charizard (base + mega-x)."""
    await _init_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await store_champions_pokemon_data(db, [_CHARIZARD_WITH_MEGA])


class TestGetChampionsPokemon:
    """Tests for get_champions_pokemon()."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.db_path = tmp_path / "test.db"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_id(self):
        await _init_db(self.db_path)
        result = await get_champions_pokemon("unknown", db_path=self.db_path)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_champions_dex_pokemon(self):
        await _seed_db(self.db_path)
        result = await get_champions_pokemon("charizard", db_path=self.db_path)
        assert isinstance(result, ChampionsDexPokemon)
        assert result.id == "charizard"
        assert result.name == "Charizard"

    @pytest.mark.asyncio
    async def test_base_stats_populated(self):
        await _seed_db(self.db_path)
        result = await get_champions_pokemon("charizard", db_path=self.db_path)
        assert result is not None
        assert result.base_stats["hp"] == 78
        assert result.base_stats["atk"] == 104

    @pytest.mark.asyncio
    async def test_types_populated(self):
        await _seed_db(self.db_path)
        result = await get_champions_pokemon("charizard", db_path=self.db_path)
        assert result is not None
        assert "Fire" in result.types
        assert "Flying" in result.types

    @pytest.mark.asyncio
    async def test_mega_form_retrievable_by_slug(self):
        await _seed_db(self.db_path)
        mega = await get_champions_pokemon("charizard-mega-x", db_path=self.db_path)
        assert mega is not None
        assert mega.is_mega is True
        assert mega.base_form_id == "charizard"


class TestGetChampionsPokemonWithMegas:
    """Tests for get_champions_pokemon_with_megas()."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.db_path = tmp_path / "test.db"

    @pytest.mark.asyncio
    async def test_returns_none_base_when_not_found(self):
        await _init_db(self.db_path)
        base, megas = await get_champions_pokemon_with_megas("unknown", db_path=self.db_path)
        assert base is None
        assert megas == []

    @pytest.mark.asyncio
    async def test_returns_base_and_megas(self):
        await _seed_db(self.db_path)
        base, megas = await get_champions_pokemon_with_megas("charizard", db_path=self.db_path)
        assert base is not None
        assert base.id == "charizard"
        assert len(megas) == 1
        assert megas[0].id == "charizard-mega-x"
        assert megas[0].is_mega is True


class TestSearchChampionsPokemonByType:
    """Tests for search_champions_pokemon_by_type()."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.db_path = tmp_path / "test.db"

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_type(self):
        await _init_db(self.db_path)
        result = await search_champions_pokemon_by_type("Psychic", db_path=self.db_path)
        assert result == []

    @pytest.mark.asyncio
    async def test_finds_by_primary_type(self):
        await _seed_db(self.db_path)
        result = await search_champions_pokemon_by_type("Fire", db_path=self.db_path)
        ids = [p.id for p in result]
        assert "charizard" in ids

    @pytest.mark.asyncio
    async def test_finds_mega_by_type(self):
        await _seed_db(self.db_path)
        result = await search_champions_pokemon_by_type("Dragon", db_path=self.db_path)
        ids = [p.id for p in result]
        assert "charizard-mega-x" in ids

    @pytest.mark.asyncio
    async def test_returns_list_of_champions_dex_pokemon(self):
        await _seed_db(self.db_path)
        result = await search_champions_pokemon_by_type("Fire", db_path=self.db_path)
        assert all(isinstance(p, ChampionsDexPokemon) for p in result)
