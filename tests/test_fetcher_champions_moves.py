"""Tests for Serebii Champions move changes scraper."""

from pathlib import Path

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.champions_moves import (
    parse_serebii_moves_page,
    store_champions_moves,
)

FIXTURE = Path(__file__).parent / "fixtures" / "serebii_champions_moves.html"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="latin-1")


def test_parse_returns_list_of_moves(fixture_html: str) -> None:
    moves = parse_serebii_moves_page(fixture_html)
    assert isinstance(moves, list)
    assert len(moves) > 0


def test_parsed_moves_have_required_fields(fixture_html: str) -> None:
    moves = parse_serebii_moves_page(fixture_html)
    for m in moves:
        assert m["id"]
        assert m["name"]
        assert m["type"]
        assert m["category"] in ("Physical", "Special", "Status")
        assert "base_power" in m
        assert "accuracy" in m
        assert "pp" in m


def test_parse_handles_empty_html() -> None:
    assert parse_serebii_moves_page("") == []
    assert parse_serebii_moves_page("<html></html>") == []


def test_parse_no_tab_tables_returns_empty() -> None:
    html = "<html><body><table class='other'></table></body></html>"
    assert parse_serebii_moves_page(html) == []


def test_parse_known_move_has_expected_fields(fixture_html: str) -> None:
    # Iron Head: Steel / Physical / 80 base power / 16 PP — stable standard values.
    moves = parse_serebii_moves_page(fixture_html)
    iron_head = next((m for m in moves if m["name"] == "Iron Head"), None)
    assert iron_head is not None, "Iron Head not found in parsed moves"
    assert iron_head["type"] == "Steel"
    assert iron_head["category"] == "Physical"
    assert iron_head["base_power"] == 80
    assert iron_head["pp"] == 16


@pytest.mark.asyncio
async def test_store_inserts_moves() -> None:
    moves = [
        {
            "id": "dragonclaw",
            "name": "Dragon Claw",
            "type": "Dragon",
            "category": "Physical",
            "base_power": 85,
            "accuracy": 100,
            "pp": 15,
            "priority": 0,
            "target": None,
            "description": "A slashing attack with sharp claws.",
            "short_desc": "A slashing attack with sharp claws.",
        }
    ]
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        count = await store_champions_moves(db, moves)
        assert count == 1
        async with db.execute(
            "SELECT name, type, base_power FROM champions_dex_moves WHERE id = ?",
            ("dragonclaw",),
        ) as cursor:
            row = await cursor.fetchone()
    assert row == ("Dragon Claw", "Dragon", 85)


@pytest.mark.asyncio
async def test_store_replaces_existing() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await store_champions_moves(
            db,
            [
                {
                    "id": "x",
                    "name": "X",
                    "type": "Fire",
                    "category": "Physical",
                    "base_power": 50,
                    "accuracy": 100,
                    "pp": 10,
                    "priority": 0,
                    "target": None,
                    "description": None,
                    "short_desc": None,
                }
            ],
        )
        await store_champions_moves(
            db,
            [
                {
                    "id": "x",
                    "name": "X",
                    "type": "Fire",
                    "category": "Physical",
                    "base_power": 75,
                    "accuracy": 100,
                    "pp": 10,
                    "priority": 0,
                    "target": None,
                    "description": None,
                    "short_desc": None,
                }
            ],
        )
        async with db.execute(
            "SELECT COUNT(*), MAX(base_power) FROM champions_dex_moves"
        ) as cursor:
            row = await cursor.fetchone()
    assert row == (1, 75)
