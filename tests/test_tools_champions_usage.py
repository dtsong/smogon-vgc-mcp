"""Tests for champions usage MCP tool and query helpers."""

import aiosqlite
import pytest
from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database.queries import get_champions_usage
from smogon_vgc_mcp.database.schema import SCHEMA
from smogon_vgc_mcp.fetcher.pikalytics_champions import store_champions_usage
from smogon_vgc_mcp.tools.champions_usage import register_champions_usage_tools
from smogon_vgc_mcp.utils.pokemon_id import normalize_pokemon_id


async def _seed(db: aiosqlite.Connection) -> None:
    await db.executescript(SCHEMA)
    await db.execute("PRAGMA foreign_keys = ON")
    await store_champions_usage(
        db,
        elo_cutoff="0+",
        pokemon_data=[
            {
                "pokemon": "incineroar",
                "usage_percent": 35.8,
                "rank": 1,
                "raw_count": None,
                "moves": [("Fake Out", 95.2)],
                "items": [("Safety Goggles", 40.0)],
                "abilities": [("Intimidate", 100.0)],
                "teammates": [("Farigiraf", 22.0)],
            }
        ],
    )


@pytest.mark.asyncio
async def test_get_champions_usage_returns_full_payload(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await _seed(db)
    result = await get_champions_usage("incineroar", elo_cutoff="0+")
    assert result is not None
    assert result["pokemon"] == "incineroar"
    assert result["usage_percent"] == 35.8
    assert ("Fake Out", 95.2) in result["moves"]
    assert result["abilities"] == [("Intimidate", 100.0)]


@pytest.mark.asyncio
async def test_get_champions_usage_returns_none_for_missing(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
    result = await get_champions_usage("missingno", elo_cutoff="0+")
    assert result is None


@pytest.mark.asyncio
async def test_mcp_tool_returns_usage(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await _seed(db)

    mcp = FastMCP("test")
    register_champions_usage_tools(mcp)

    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_champions_usage_stats" in tool_names

    result = await mcp.call_tool(
        "get_champions_usage_stats",
        {"pokemon": "Incineroar", "elo_cutoff": "0+"},
    )
    assert len(result) == 1
    payload = result[0].text
    assert "incineroar" in payload.lower()
    assert "usage_percent" in payload
    assert "error" not in payload.lower()


@pytest.mark.asyncio
async def test_mcp_tool_returns_error_for_missing(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)

    mcp = FastMCP("test")
    register_champions_usage_tools(mcp)

    result = await mcp.call_tool(
        "get_champions_usage_stats",
        {"pokemon": "Missingno", "elo_cutoff": "0+"},
    )
    assert len(result) == 1
    payload = result[0].text
    assert "error" in payload.lower()
    assert "no champions usage data" in payload.lower()


@pytest.mark.asyncio
async def test_mcp_tool_rejects_invalid_elo_cutoff(monkeypatch, tmp_path) -> None:
    """Tool must reject unknown ELO cutoffs before touching the DB.

    Guards the current "0+"-only contract while higher-ELO URL support is
    still unwired — see the ELO_CUTOFFS comment in pikalytics_champions.py.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SMOGON_VGC_DB_PATH", str(db_path))
    async with aiosqlite.connect(db_path) as db:
        await _seed(db)

    mcp = FastMCP("test")
    register_champions_usage_tools(mcp)

    result = await mcp.call_tool(
        "get_champions_usage_stats",
        {"pokemon": "Incineroar", "elo_cutoff": "1760+"},
    )
    assert len(result) == 1
    payload = result[0].text
    assert "error" in payload.lower()
    assert "invalid elo_cutoff" in payload.lower()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Incineroar", "incineroar"),
        ("  Incineroar  ", "incineroar"),
        ("Nidoran-F", "nidoranf"),
        ("Mega Charizard X", "megacharizardx"),
        ("Farfetch'd", "farfetchd"),
        ("Mr. Mime", "mrmime"),
        ("Type: Null", "typenull"),
        ("Porygon-Z", "porygonz"),
    ],
)
def test_normalize_pokemon_id_strips_all_punctuation(raw: str, expected: str) -> None:
    """Normalization must match Showdown's toID() for user-visible names.

    Regression guard: earlier revision only stripped spaces and hyphens,
    so apostrophes, periods, and colons leaked through and the DB lookup
    silently missed.
    """
    assert normalize_pokemon_id(raw) == expected
