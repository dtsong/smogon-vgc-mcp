"""Pytest configuration and shared fixtures."""

from unittest.mock import AsyncMock

import pytest

from smogon_vgc_mcp.database.models import (
    AbilityUsage,
    CheckCounter,
    EVSpread,
    ItemUsage,
    MoveUsage,
    PokemonStats,
    Snapshot,
    Team,
    TeammateUsage,
    TeamPokemon,
    TeraTypeUsage,
    UsageRanking,
)

# =============================================================================
# Sample Pokemon Data
# =============================================================================


@pytest.fixture
def sample_incineroar_stats() -> PokemonStats:
    """Sample PokemonStats for Incineroar."""
    return PokemonStats(
        pokemon="Incineroar",
        raw_count=50000,
        usage_percent=48.39,
        viability_ceiling=[1, 1, 1, 1],
        abilities=[
            AbilityUsage(ability="Intimidate", count=49000, percent=98.0),
            AbilityUsage(ability="Blaze", count=1000, percent=2.0),
        ],
        items=[
            ItemUsage(item="Safety Goggles", count=20000, percent=40.0),
            ItemUsage(item="Sitrus Berry", count=15000, percent=30.0),
            ItemUsage(item="Assault Vest", count=10000, percent=20.0),
        ],
        moves=[
            MoveUsage(move="Fake Out", count=48000, percent=96.0),
            MoveUsage(move="Flare Blitz", count=45000, percent=90.0),
            MoveUsage(move="Parting Shot", count=40000, percent=80.0),
            MoveUsage(move="Knock Off", count=35000, percent=70.0),
        ],
        teammates=[
            TeammateUsage(teammate="Flutter Mane", count=25000, percent=50.0),
            TeammateUsage(teammate="Raging Bolt", count=20000, percent=40.0),
        ],
        spreads=[
            EVSpread(
                nature="Careful",
                hp=252, atk=4, def_=0, spa=0, spd=252, spe=0,
                count=15000, percent=30.0
            ),
            EVSpread(
                nature="Adamant",
                hp=252, atk=252, def_=0, spa=0, spd=4, spe=0,
                count=10000, percent=20.0
            ),
        ],
        tera_types=[
            TeraTypeUsage(tera_type="Ghost", percent=45.0),
            TeraTypeUsage(tera_type="Grass", percent=30.0),
        ],
        checks_counters=[
            CheckCounter(
                counter="Urshifu-Rapid-Strike",
                score=55.0, win_percent=60.0, ko_percent=35.0, switch_percent=25.0
            ),
        ],
    )


@pytest.fixture
def sample_flutter_mane_stats() -> PokemonStats:
    """Sample PokemonStats for Flutter Mane."""
    return PokemonStats(
        pokemon="Flutter Mane",
        raw_count=52000,
        usage_percent=50.1,
        viability_ceiling=[1, 1, 1, 1],
        abilities=[
            AbilityUsage(ability="Protosynthesis", count=52000, percent=100.0),
        ],
        items=[
            ItemUsage(item="Booster Energy", count=40000, percent=76.9),
            ItemUsage(item="Choice Specs", count=8000, percent=15.4),
        ],
        moves=[
            MoveUsage(move="Moonblast", count=50000, percent=96.2),
            MoveUsage(move="Shadow Ball", count=48000, percent=92.3),
            MoveUsage(move="Protect", count=45000, percent=86.5),
            MoveUsage(move="Dazzling Gleam", count=30000, percent=57.7),
        ],
        teammates=[
            TeammateUsage(teammate="Incineroar", count=25000, percent=48.1),
        ],
        spreads=[
            EVSpread(
                nature="Timid",
                hp=4, atk=0, def_=0, spa=252, spd=0, spe=252,
                count=30000, percent=57.7
            ),
        ],
    )


@pytest.fixture
def sample_snapshot() -> Snapshot:
    """Sample Snapshot."""
    return Snapshot(
        id=1,
        format="regf",
        month="2025-12",
        elo_bracket=1500,
        num_battles=100000,
        fetched_at="2025-12-15T10:00:00",
    )


@pytest.fixture
def sample_usage_rankings() -> list[UsageRanking]:
    """Sample usage rankings."""
    return [
        UsageRanking(rank=1, pokemon="Flutter Mane", usage_percent=50.1, raw_count=52000),
        UsageRanking(rank=2, pokemon="Incineroar", usage_percent=48.39, raw_count=50000),
        UsageRanking(rank=3, pokemon="Urshifu-Rapid-Strike", usage_percent=43.0, raw_count=44500),
        UsageRanking(rank=4, pokemon="Raging Bolt", usage_percent=37.5, raw_count=38875),
        UsageRanking(rank=5, pokemon="Tornadus", usage_percent=29.0, raw_count=30060),
    ]


@pytest.fixture
def sample_team() -> Team:
    """Sample tournament team."""
    return Team(
        id=1,
        format="regf",
        team_id="F1",
        description="Sample VGC team",
        owner="TestPlayer",
        tournament="Regional Championship",
        rank="1st",
        rental_code="ABC123",
        pokepaste_url="https://pokepast.es/abc123",
        pokemon=[
            TeamPokemon(
                slot=1, pokemon="Incineroar", item="Safety Goggles",
                ability="Intimidate", tera_type="Ghost", nature="Careful",
                hp_ev=252, atk_ev=4, def_ev=0, spa_ev=0, spd_ev=252, spe_ev=0,
                move1="Fake Out", move2="Flare Blitz", move3="Parting Shot", move4="Knock Off"
            ),
            TeamPokemon(
                slot=2, pokemon="Flutter Mane", item="Booster Energy",
                ability="Protosynthesis", tera_type="Fairy", nature="Timid",
                hp_ev=4, atk_ev=0, def_ev=0, spa_ev=252, spd_ev=0, spe_ev=252,
                move1="Moonblast", move2="Shadow Ball", move3="Protect", move4="Dazzling Gleam"
            ),
        ],
    )


# =============================================================================
# Mock Database Fixtures
# =============================================================================


@pytest.fixture
def mock_db_connection():
    """Create a mock aiosqlite connection."""
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()

    # Set up cursor context manager
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=None)
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.fetchall = AsyncMock(return_value=[])

    # Set up connection.execute to return cursor
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()
    mock_conn.row_factory = None

    return mock_conn, mock_cursor


# =============================================================================
# Sample Pokepaste Text
# =============================================================================


@pytest.fixture
def sample_pokepaste_text() -> str:
    """Sample pokepaste format text."""
    return """Incineroar @ Safety Goggles
Ability: Intimidate
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Knock Off

Flutter Mane @ Booster Energy
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Protect
- Dazzling Gleam
"""


# =============================================================================
# Base Stats for Common Pokemon (for calculator tests)
# =============================================================================


@pytest.fixture
def incineroar_base_stats() -> dict[str, int]:
    """Incineroar base stats."""
    return {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}


@pytest.fixture
def flutter_mane_base_stats() -> dict[str, int]:
    """Flutter Mane base stats."""
    return {"hp": 55, "atk": 55, "def": 55, "spa": 135, "spd": 135, "spe": 135}
