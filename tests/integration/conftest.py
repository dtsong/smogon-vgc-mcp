"""Integration test fixtures for MCP server testing."""

import asyncio
import json
import os
from pathlib import Path

import aiosqlite
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Test data constants
TEST_FORMAT = "regf"
TEST_MONTH = "2025-12"
TEST_ELO = 1500


async def seed_test_data(db_path: Path) -> None:
    """Seed the database with test data for integration tests."""
    async with aiosqlite.connect(db_path) as db:
        # Insert a snapshot
        cursor = await db.execute(
            """
            INSERT INTO snapshots (format, month, elo_bracket, num_battles)
            VALUES (?, ?, ?, ?)
            """,
            (TEST_FORMAT, TEST_MONTH, TEST_ELO, 100000),
        )
        snapshot_id = cursor.lastrowid

        # Insert Pokemon usage data
        pokemon_data = [
            ("Incineroar", 50000, 48.39),
            ("Flutter Mane", 52000, 50.1),
            ("Urshifu-Rapid-Strike", 44500, 43.0),
            ("Raging Bolt", 38875, 37.5),
            ("Tornadus", 30060, 29.0),
        ]

        for pokemon, raw_count, usage_pct in pokemon_data:
            cursor = await db.execute(
                """
                INSERT INTO pokemon_usage
                    (snapshot_id, pokemon, raw_count, usage_percent, viability_ceiling)
                VALUES (?, ?, ?, ?, ?)
                """,
                (snapshot_id, pokemon, raw_count, usage_pct, "[1,1,1,1]"),
            )
            pokemon_id = cursor.lastrowid

            # Add abilities
            if pokemon == "Incineroar":
                await db.execute(
                    """
                    INSERT INTO abilities (pokemon_usage_id, ability, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Intimidate", 49000, 98.0),
                )
                await db.execute(
                    """
                    INSERT INTO items (pokemon_usage_id, item, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Safety Goggles", 20000, 40.0),
                )
                await db.execute(
                    """
                    INSERT INTO moves (pokemon_usage_id, move, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Fake Out", 48000, 96.0),
                )
                await db.execute(
                    """
                    INSERT INTO teammates (pokemon_usage_id, teammate, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Flutter Mane", 25000, 50.0),
                )
                await db.execute(
                    """
                    INSERT INTO spreads
                        (pokemon_usage_id, nature, hp, atk, def, spa, spd, spe, count, percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (pokemon_id, "Careful", 252, 4, 0, 0, 252, 0, 15000, 30.0),
                )
                await db.execute(
                    """
                    INSERT INTO tera_types (pokemon_usage_id, tera_type, percent)
                    VALUES (?, ?, ?)
                    """,
                    (pokemon_id, "Ghost", 45.0),
                )
            elif pokemon == "Flutter Mane":
                await db.execute(
                    """
                    INSERT INTO abilities (pokemon_usage_id, ability, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Protosynthesis", 52000, 100.0),
                )
                await db.execute(
                    """
                    INSERT INTO items (pokemon_usage_id, item, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Booster Energy", 40000, 76.9),
                )
                await db.execute(
                    """
                    INSERT INTO moves (pokemon_usage_id, move, count, percent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pokemon_id, "Moonblast", 50000, 96.2),
                )

        # Insert a tournament team
        cursor = await db.execute(
            """
            INSERT INTO teams
                (format, team_id, description, owner, tournament, rank, rental_code, pokepaste_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                TEST_FORMAT,
                "F001",
                "Test Tournament Team",
                "TestPlayer",
                "Regional Championship",
                "1st",
                "ABC123",
                "https://pokepast.es/test",
            ),
        )
        team_db_id = cursor.lastrowid

        # Insert team Pokemon
        team_pokemon = [
            (
                "Incineroar",
                "Safety Goggles",
                "Intimidate",
                "Ghost",
                "Careful",
                252,
                4,
                0,
                0,
                252,
                0,
            ),
            (
                "Flutter Mane",
                "Booster Energy",
                "Protosynthesis",
                "Fairy",
                "Timid",
                4,
                0,
                0,
                252,
                0,
                252,
            ),
        ]
        for slot, (poke, item, ability, tera, nature, hp, atk, def_, spa, spd, spe) in enumerate(
            team_pokemon, 1
        ):
            await db.execute(
                """
                INSERT INTO team_pokemon
                    (team_id, slot, pokemon, item, ability, tera_type, nature,
                     hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev, move1, move2, move3, move4)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_db_id,
                    slot,
                    poke,
                    item,
                    ability,
                    tera,
                    nature,
                    hp,
                    atk,
                    def_,
                    spa,
                    spd,
                    spe,
                    "Fake Out",
                    "Flare Blitz",
                    "Parting Shot",
                    "Knock Off",
                ),
            )

        # Insert Pokedex data
        dex_pokemon = [
            (
                "incineroar",
                727,
                "Incineroar",
                "Fire",
                "Dark",
                95,
                115,
                90,
                80,
                90,
                60,
                "Blaze",
                "Intimidate",
                None,
            ),
            (
                "fluttermane",
                987,
                "Flutter Mane",
                "Ghost",
                "Fairy",
                55,
                55,
                55,
                135,
                135,
                135,
                "Protosynthesis",
                None,
                None,
            ),
        ]
        for row in dex_pokemon:
            await db.execute(
                """
                INSERT INTO dex_pokemon
                    (id, num, name, type1, type2, hp, atk, def, spa, spd, spe,
                     ability1, ability2, ability_hidden)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )

        # Insert moves
        dex_moves = [
            (
                "fakeout",
                252,
                "Fake Out",
                "Normal",
                "Physical",
                40,
                100,
                10,
                3,
                "normal",
                "High priority flinch move",
            ),
            (
                "moonblast",
                585,
                "Moonblast",
                "Fairy",
                "Special",
                95,
                100,
                15,
                0,
                "normal",
                "May lower SpA",
            ),
        ]
        for row in dex_moves:
            await db.execute(
                """
                INSERT INTO dex_moves
                    (id, num, name, type, category, base_power, accuracy, pp,
                     priority, target, short_desc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )

        # Insert abilities
        dex_abilities = [
            ("intimidate", 22, "Intimidate", "Lowers adjacent opponents' Attack."),
            ("protosynthesis", 281, "Protosynthesis", "Boosts stat in Sun."),
        ]
        for row in dex_abilities:
            await db.execute(
                """
                INSERT INTO dex_abilities (id, num, name, short_desc)
                VALUES (?, ?, ?, ?)
                """,
                row,
            )

        # Insert items
        dex_items = [
            ("safetygoggles", 650, "Safety Goggles", "Immune to powder moves."),
            ("boosterenergy", 1880, "Booster Energy", "Activates Protosynthesis."),
        ]
        for row in dex_items:
            await db.execute(
                """
                INSERT INTO dex_items (id, num, name, short_desc)
                VALUES (?, ?, ?, ?)
                """,
                row,
            )

        # Insert type chart (subset)
        type_chart = [
            ("Fire", "Grass", 2.0),
            ("Fire", "Water", 0.5),
            ("Fire", "Fire", 0.5),
            ("Water", "Fire", 2.0),
            ("Grass", "Water", 2.0),
            ("Ghost", "Ghost", 2.0),
            ("Ghost", "Normal", 0.0),
            ("Fairy", "Dragon", 2.0),
            ("Fairy", "Dark", 2.0),
            ("Dark", "Ghost", 2.0),
            ("Dark", "Psychic", 2.0),
        ]
        for row in type_chart:
            await db.execute(
                """
                INSERT INTO dex_type_chart (attacking_type, defending_type, multiplier)
                VALUES (?, ?, ?)
                """,
                row,
            )

        await db.commit()


@pytest.fixture(scope="session")
def seeded_database(tmp_path_factory) -> Path:
    """Create a database with test data."""
    db_path = tmp_path_factory.mktemp("data") / "test_integration.db"

    # Initialize schema and seed data
    from smogon_vgc_mcp.database.schema import init_database

    async def setup():
        await init_database(db_path)
        await seed_test_data(db_path)

    asyncio.run(setup())
    return db_path


class MCPTestClient:
    """A test client wrapper that runs each operation in an isolated async context."""

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def _get_server_params(self) -> StdioServerParameters:
        """Get server parameters for spawning the MCP server."""
        return StdioServerParameters(
            command="uv",
            args=["run", "smogon-vgc-mcp"],
            env={
                **os.environ,
                "SMOGON_VGC_DB_PATH": str(self._db_path),
                "LOG_LEVEL": "WARNING",
            },
        )

    async def _run_with_session(self, operation):
        """Run an async operation with a connected session."""
        server_params = self._get_server_params()
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await operation(session)

    async def call_tool(self, name: str, arguments: dict | None = None):
        """Call a tool on the server."""

        async def op(session):
            return await session.call_tool(name, arguments or {})

        return await self._run_with_session(op)

    async def list_tools(self):
        """List all available tools."""

        async def op(session):
            return await session.list_tools()

        return await self._run_with_session(op)

    async def list_resources(self):
        """List all available resources."""

        async def op(session):
            return await session.list_resources()

        return await self._run_with_session(op)


@pytest.fixture(scope="session")
def mcp_client(seeded_database: Path):
    """Provide an MCP test client.

    Each method call spawns a new server connection to avoid
    pytest-asyncio/anyio task boundary issues.
    """
    return MCPTestClient(seeded_database)


def extract_tool_result(result) -> dict:
    """Extract the content from a CallToolResult.

    MCP tool results contain a list of content items. This helper
    extracts the first text content and parses it as JSON.
    """
    if hasattr(result, "content") and result.content:
        for item in result.content:
            if hasattr(item, "text"):
                return json.loads(item.text)
    return {}
