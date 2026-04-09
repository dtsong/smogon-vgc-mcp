"""Tests for fetcher/champions_dex.py — real Serebii HTML parser and store function."""

from pathlib import Path

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.champions_dex import (
    parse_serebii_pokemon_page,
    store_champions_pokemon_data,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "serebii_charizard.html"


@pytest.fixture(scope="module")
def charizard_html() -> str:
    return FIXTURE_PATH.read_text(encoding="latin-1")


@pytest.fixture(scope="module")
def charizard_parsed(charizard_html) -> dict:
    return parse_serebii_pokemon_page(charizard_html, "charizard")


async def _init_db(db_path):
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ---------------------------------------------------------------------------
# Task 5 tests: parser
# ---------------------------------------------------------------------------


class TestParseBaseForm:
    """Base form data extracted from the real Charizard fixture."""

    def test_returns_dict(self, charizard_parsed):
        assert isinstance(charizard_parsed, dict)

    def test_id(self, charizard_parsed):
        assert charizard_parsed["id"] == "charizard"

    def test_name(self, charizard_parsed):
        assert charizard_parsed["name"] == "Charizard"

    def test_num(self, charizard_parsed):
        assert charizard_parsed["num"] == 6

    def test_types_fire_flying(self, charizard_parsed):
        assert charizard_parsed["types"] == ["Fire", "Flying"]

    def test_base_stats_hp(self, charizard_parsed):
        assert charizard_parsed["base_stats"]["hp"] == 78

    def test_base_stats_atk(self, charizard_parsed):
        assert charizard_parsed["base_stats"]["atk"] == 104

    def test_base_stats_def(self, charizard_parsed):
        assert charizard_parsed["base_stats"]["def"] == 78

    def test_base_stats_spa(self, charizard_parsed):
        assert charizard_parsed["base_stats"]["spa"] == 159

    def test_base_stats_spd(self, charizard_parsed):
        assert charizard_parsed["base_stats"]["spd"] == 115

    def test_base_stats_spe(self, charizard_parsed):
        assert charizard_parsed["base_stats"]["spe"] == 100

    def test_ability_drought(self, charizard_parsed):
        assert "Drought" in charizard_parsed["abilities"]

    def test_height(self, charizard_parsed):
        assert charizard_parsed["height_m"] == pytest.approx(1.7)

    def test_weight(self, charizard_parsed):
        assert charizard_parsed["weight_kg"] == pytest.approx(90.5)


class TestParseMegaForms:
    """Mega form detection and data extraction from the real fixture."""

    def test_has_mega_forms(self, charizard_parsed):
        assert len(charizard_parsed["mega_forms"]) >= 1

    def test_mega_x_present(self, charizard_parsed):
        slugs = [m["slug"] for m in charizard_parsed["mega_forms"]]
        assert "charizard-mega-x" in slugs

    def test_mega_x_types_fire_dragon(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["types"] == ["Fire", "Dragon"]

    def test_mega_x_ability_tough_claws(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert "Tough Claws" in mega_x["abilities"]

    def test_mega_x_stats_hp(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["stats"]["hp"] == 78

    def test_mega_x_stats_atk(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["stats"]["atk"] == 130

    def test_mega_x_stats_def(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["stats"]["def"] == 111

    def test_mega_x_stats_spa(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["stats"]["spa"] == 130

    def test_mega_x_stats_spd(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["stats"]["spd"] == 85

    def test_mega_x_stats_spe(self, charizard_parsed):
        mega_x = next(m for m in charizard_parsed["mega_forms"] if m["slug"] == "charizard-mega-x")
        assert mega_x["stats"]["spe"] == 100

    def test_mega_y_present_or_skipped_gracefully(self, charizard_parsed):
        """Mega Y has empty stat data — parser must not crash; may be omitted."""
        # Parser either skips it (returns None) or includes it.
        # Either outcome is valid — just must not raise.
        slugs = [m["slug"] for m in charizard_parsed["mega_forms"]]
        # At minimum Mega X must be there
        assert "charizard-mega-x" in slugs


class TestReturnSchema:
    """Returned dict has all required keys."""

    EXPECTED_KEYS = {
        "id",
        "num",
        "name",
        "types",
        "base_stats",
        "abilities",
        "ability_hidden",
        "height_m",
        "weight_kg",
        "mega_forms",
    }

    def test_all_keys_present(self, charizard_parsed):
        assert self.EXPECTED_KEYS <= set(charizard_parsed.keys())

    def test_mega_forms_is_list(self, charizard_parsed):
        assert isinstance(charizard_parsed["mega_forms"], list)


class TestEdgeCases:
    """Edge cases: empty HTML, None, 404-style pages."""

    def test_empty_html_returns_none(self):
        assert parse_serebii_pokemon_page("", "charizard") is None

    def test_whitespace_only_returns_none(self):
        assert parse_serebii_pokemon_page("   \n  ", "charizard") is None

    def test_no_dextable_returns_none(self):
        html = "<html><body><p>Not found</p></body></html>"
        assert parse_serebii_pokemon_page(html, "unknown") is None


# ---------------------------------------------------------------------------
# Task 6 tests: store function
# ---------------------------------------------------------------------------


class TestStoreChampionsPokemonData:
    """Store function inserts base + Mega forms into DB correctly."""

    @pytest.fixture
    def sample_pokemon_list(self):
        return [
            {
                "id": "charizard",
                "num": 6,
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "base_stats": {"hp": 78, "atk": 104, "def": 78, "spa": 159, "spd": 115, "spe": 100},
                "abilities": ["Drought"],
                "ability_hidden": None,
                "is_mega": False,
                "base_form_id": None,
                "mega_stone": None,
                "height_m": 1.7,
                "weight_kg": 90.5,
                "mega_forms": [
                    {
                        "slug": "charizard-mega-x",
                        "name": "Mega Charizard X",
                        "types": ["Fire", "Dragon"],
                        "abilities": ["Tough Claws"],
                        "stats": {
                            "hp": 78,
                            "atk": 130,
                            "def": 111,
                            "spa": 130,
                            "spd": 85,
                            "spe": 100,
                        },
                        "mega_stone": "Charizardite X",
                        "height_m": 1.7,
                        "weight_kg": 110.5,
                    }
                ],
            }
        ]

    @pytest.mark.asyncio
    async def test_store_returns_count(self, tmp_path, sample_pokemon_list):
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            count = await store_champions_pokemon_data(db, sample_pokemon_list)
        assert count == 2  # base + 1 mega

    @pytest.mark.asyncio
    async def test_base_form_in_db(self, tmp_path, sample_pokemon_list):
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await store_champions_pokemon_data(db, sample_pokemon_list)
            async with db.execute(
                "SELECT id, name, type1, type2, hp, spa "
                "FROM champions_dex_pokemon WHERE id='charizard'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "charizard"
        assert row[1] == "Charizard"
        assert row[2] == "Fire"
        assert row[3] == "Flying"
        assert row[4] == 78
        assert row[5] == 159

    @pytest.mark.asyncio
    async def test_mega_form_in_db(self, tmp_path, sample_pokemon_list):
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await store_champions_pokemon_data(db, sample_pokemon_list)
            async with db.execute(
                """SELECT id, base_form_id, is_mega, mega_stone, atk
                   FROM champions_dex_pokemon WHERE id='charizard-mega-x'"""
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "charizard-mega-x"
        assert row[1] == "charizard"
        assert row[2] == 1
        assert row[3] == "Charizardite X"
        assert row[4] == 130

    @pytest.mark.asyncio
    async def test_delete_before_insert(self, tmp_path, sample_pokemon_list):
        """Calling store twice replaces old data, not duplicates."""
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await store_champions_pokemon_data(db, sample_pokemon_list)
            count = await store_champions_pokemon_data(db, sample_pokemon_list)
        assert count == 2

    @pytest.mark.asyncio
    async def test_commit_false_does_not_commit(self, tmp_path, sample_pokemon_list):
        """_commit=False leaves transaction open (caller must commit)."""
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await store_champions_pokemon_data(db, sample_pokemon_list, _commit=False)
            await db.rollback()
        # After rollback, nothing should be in the DB
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM champions_dex_pokemon") as cursor:
                row = await cursor.fetchone()
        assert row[0] == 0

    @pytest.mark.asyncio
    async def test_store_from_real_fixture(self, tmp_path, charizard_html):
        """End-to-end: parse real fixture then store — base + Mega X at minimum."""
        db_path = tmp_path / "test.db"
        await _init_db(db_path)
        parsed = parse_serebii_pokemon_page(charizard_html, "charizard")
        assert parsed is not None

        async with aiosqlite.connect(db_path) as db:
            count = await store_champions_pokemon_data(db, [parsed])
        assert count >= 1  # at least base form stored

        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT hp, spa FROM champions_dex_pokemon WHERE id='charizard'"
            ) as cursor:
                row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 78
        assert row[1] == 159
