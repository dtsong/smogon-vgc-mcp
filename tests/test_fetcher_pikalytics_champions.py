"""Tests for Pikalytics Champions usage parser."""

from pathlib import Path

import aiosqlite
import pytest

from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.pikalytics_champions import (
    parse_pikalytics_page,
    store_champions_usage,
)

FIXTURE = Path(__file__).parent / "fixtures" / "pikalytics_incineroar.html"


@pytest.fixture
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_returns_usage_dict(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert result["pokemon"] == "incineroar"
    assert result["usage_percent"] is not None
    assert 0 < result["usage_percent"] <= 100


def test_parse_extracts_moves(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert isinstance(result["moves"], list)
    assert len(result["moves"]) > 0
    name, pct = result["moves"][0]
    assert isinstance(name, str) and name
    assert isinstance(pct, float)


def test_parse_moves_first_entry_clean(html: str) -> None:
    """Regression: first move entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, pct = result["moves"][0]
    assert name == "Fake Out", f"Expected 'Fake Out', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"
    assert "the" not in name.lower().split(), f"Sentence fragment in label: {name!r}"
    assert pct == pytest.approx(41.092)


def test_parse_items_first_entry_clean(html: str) -> None:
    """Regression: first item entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, _pct = result["items"][0]
    assert name == "Sitrus Berry", f"Expected 'Sitrus Berry', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"


def test_parse_abilities_first_entry_clean(html: str) -> None:
    """Regression: first ability entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, _pct = result["abilities"][0]
    assert name == "Intimidate", f"Expected 'Intimidate', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"


def test_parse_teammates_first_entry_clean(html: str) -> None:
    """Regression: first teammate entry must not contain FAQ preamble text."""
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    name, _pct = result["teammates"][0]
    assert name == "Sinistcha", f"Expected 'Sinistcha', got {name!r}"
    assert len(name) < 40, f"Label too long (preamble leak?): {name!r}"


def test_parse_extracts_items_abilities_teammates(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert len(result["items"]) > 0
    assert len(result["abilities"]) > 0
    assert len(result["teammates"]) > 0


def test_parse_handles_404() -> None:
    assert parse_pikalytics_page("", pokemon_slug="missingno") is None
    assert parse_pikalytics_page("<html>Not Found</html>", pokemon_slug="missingno") is None


@pytest.mark.asyncio
async def test_store_creates_snapshot_and_rows() -> None:
    payload = [
        {
            "pokemon": "incineroar",
            "usage_percent": 35.8,
            "rank": 1,
            "raw_count": None,
            "moves": [("Fake Out", 95.2), ("Flare Blitz", 78.1)],
            "items": [("Safety Goggles", 40.0)],
            "abilities": [("Intimidate", 100.0)],
            "teammates": [("Farigiraf", 22.0)],
            "spreads": [],
        }
    ]
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        snapshot_id, count = await store_champions_usage(db, elo_cutoff="0+", pokemon_data=payload)
        assert snapshot_id > 0
        assert count == 1
        async with db.execute("SELECT COUNT(*) FROM champions_usage_moves") as cursor:
            (moves_count,) = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_abilities") as cursor:
            (ab_count,) = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_items") as cursor:
            (items_count,) = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM champions_usage_teammates") as cursor:
            (teammates_count,) = await cursor.fetchone()
    assert moves_count == 2
    assert ab_count == 1
    assert items_count == 1
    assert teammates_count == 1


@pytest.mark.asyncio
async def test_store_replaces_same_elo_snapshot() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        first = [
            {
                "pokemon": "incineroar",
                "usage_percent": 35.8,
                "rank": 1,
                "raw_count": None,
                "moves": [("A", 10.0)],
                "items": [],
                "abilities": [],
                "teammates": [],
                "spreads": [],
            }
        ]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=first)
        second = [
            {
                "pokemon": "incineroar",
                "usage_percent": 40.0,
                "rank": 1,
                "raw_count": None,
                "moves": [("B", 20.0)],
                "items": [],
                "abilities": [],
                "teammates": [],
                "spreads": [],
            }
        ]
        await store_champions_usage(db, elo_cutoff="0+", pokemon_data=second)
        async with db.execute("SELECT COUNT(*) FROM champions_usage_snapshots") as cursor:
            (snap_count,) = await cursor.fetchone()
        async with db.execute("SELECT move, percent FROM champions_usage_moves") as cursor:
            rows = await cursor.fetchall()
    assert snap_count == 1
    assert rows == [("B", 20.0)]
