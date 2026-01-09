"""Tests for database/queries.py - Database query functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smogon_vgc_mcp.database.models import (
    Snapshot,
    TeammateUsage,
)
from smogon_vgc_mcp.database.queries import (
    find_by_item,
    find_by_move,
    find_by_tera_type,
    get_all_snapshots,
    get_counters_for,
    get_snapshot,
    get_team,
    get_team_count,
    get_teammates,
    get_usage_rankings,
    search_pokemon,
)


def create_mock_row(data: dict):
    """Create a mock row object that supports item access."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: data[key]
    return row


def create_async_cursor(rows):
    """Create a mock async cursor that yields rows."""
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=rows[0] if rows else None)
    cursor.fetchall = AsyncMock(return_value=rows)

    # For async iteration
    cursor.__aiter__ = lambda self: iter(rows)

    return cursor


class TestGetSnapshot:
    """Tests for get_snapshot function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_snapshot_when_found(self, mock_get_conn):
        """Test returning snapshot when found."""
        mock_row = create_mock_row(
            {
                "id": 1,
                "format": "regf",
                "month": "2025-12",
                "elo_bracket": 1500,
                "num_battles": 100000,
                "fetched_at": "2025-12-15T10:00:00",
            }
        )

        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_snapshot("regf", "2025-12", 1500)

        assert result is not None
        assert isinstance(result, Snapshot)
        assert result.format == "regf"
        assert result.month == "2025-12"
        assert result.elo_bracket == 1500

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_none_when_not_found(self, mock_get_conn):
        """Test returning None when snapshot not found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_snapshot("regf", "2099-99", 1500)

        assert result is None


class TestGetAllSnapshots:
    """Tests for get_all_snapshots function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_list_of_snapshots(self, mock_get_conn):
        """Test returning list of snapshots."""
        mock_rows = [
            create_mock_row(
                {
                    "id": 1,
                    "format": "regf",
                    "month": "2025-12",
                    "elo_bracket": 1500,
                    "num_battles": 100000,
                    "fetched_at": "2025-12-15",
                }
            ),
            create_mock_row(
                {
                    "id": 2,
                    "format": "regf",
                    "month": "2025-11",
                    "elo_bracket": 1500,
                    "num_battles": 90000,
                    "fetched_at": "2025-11-15",
                }
            ),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_all_snapshots("regf")

        assert len(result) == 2
        assert all(isinstance(s, Snapshot) for s in result)
        assert result[0].month == "2025-12"
        assert result[1].month == "2025-11"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_empty_list_when_no_snapshots(self, mock_get_conn):
        """Test returning empty list when no snapshots."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_all_snapshots("nonexistent")

        assert result == []


class TestGetUsageRankings:
    """Tests for get_usage_rankings function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_empty_list_when_no_snapshot(self, mock_get_conn):
        """Test returning empty list when snapshot not found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_usage_rankings("regf", "2099-99", 1500)

        assert result == []


class TestSearchPokemon:
    """Tests for search_pokemon function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_search_returns_matching_pokemon(self, mock_get_conn):
        """Test search returns matching Pokemon names."""
        mock_rows = [
            create_mock_row({"pokemon": "Incineroar"}),
            create_mock_row({"pokemon": "Incandescent"}),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await search_pokemon("inc")

        assert len(result) == 2
        assert "Incineroar" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_search_returns_empty_list_when_no_match(self, mock_get_conn):
        """Test search returns empty list when no match."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await search_pokemon("xyznotapokemon")

        assert result == []


class TestGetTeammates:
    """Tests for get_teammates function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_teammates(self, mock_get_conn):
        """Test returning teammate list."""
        mock_rows = [
            create_mock_row({"teammate": "Flutter Mane", "count": 25000, "percent": 50.0}),
            create_mock_row({"teammate": "Raging Bolt", "count": 20000, "percent": 40.0}),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_teammates("Incineroar")

        assert len(result) == 2
        assert all(isinstance(t, TeammateUsage) for t in result)
        assert result[0].teammate == "Flutter Mane"
        assert result[0].percent == 50.0


class TestFindByItem:
    """Tests for find_by_item function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_pokemon_with_item(self, mock_get_conn):
        """Test returning Pokemon that use a specific item."""
        mock_rows = [
            create_mock_row({"pokemon": "Incineroar", "count": 20000, "percent": 40.0}),
            create_mock_row({"pokemon": "Amoonguss", "count": 15000, "percent": 30.0}),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await find_by_item("Safety Goggles")

        assert len(result) == 2
        assert result[0]["pokemon"] == "Incineroar"


class TestFindByMove:
    """Tests for find_by_move function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_pokemon_with_move(self, mock_get_conn):
        """Test returning Pokemon that use a specific move."""
        mock_rows = [
            create_mock_row({"pokemon": "Incineroar", "count": 48000, "percent": 96.0}),
            create_mock_row({"pokemon": "Rillaboom", "count": 35000, "percent": 70.0}),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await find_by_move("Fake Out")

        assert len(result) == 2
        assert result[0]["pokemon"] == "Incineroar"


class TestFindByTeraType:
    """Tests for find_by_tera_type function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_pokemon_with_tera_type(self, mock_get_conn):
        """Test returning Pokemon that use a specific Tera type."""
        mock_rows = [
            create_mock_row({"pokemon": "Incineroar", "percent": 45.0}),
            create_mock_row({"pokemon": "Flutter Mane", "percent": 20.0}),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await find_by_tera_type("Ghost")

        assert len(result) == 2
        assert result[0]["pokemon"] == "Incineroar"


class TestGetCountersFor:
    """Tests for get_counters_for function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_counters(self, mock_get_conn):
        """Test returning counters for a Pokemon."""
        from smogon_vgc_mcp.database.models import CheckCounter

        mock_rows = [
            create_mock_row(
                {
                    "counter": "Urshifu-Rapid-Strike",
                    "score": 55.0,
                    "win_percent": 60.0,
                    "ko_percent": 35.0,
                    "switch_percent": 25.0,
                }
            ),
        ]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_counters_for("Incineroar")

        assert len(result) == 1
        assert isinstance(result[0], CheckCounter)
        assert result[0].counter == "Urshifu-Rapid-Strike"
        assert result[0].score == 55.0


class TestGetTeam:
    """Tests for get_team function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_none_when_not_found(self, mock_get_conn):
        """Test returning None when team not found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_team("NOTEXIST")

        assert result is None


class TestGetTeamCount:
    """Tests for get_team_count function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.database.queries.get_connection")
    async def test_returns_zero_when_no_teams(self, mock_get_conn):
        """Test returning 0 when no teams found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_db = AsyncMock()
        mock_db.execute = MagicMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_get_conn.return_value = mock_db

        result = await get_team_count()

        assert result == 0
