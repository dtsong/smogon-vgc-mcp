"""Tests for tools/admin.py - Admin tools."""

from unittest.mock import MagicMock, patch

import pytest


# Create mock FastMCP for testing
class MockFastMCP:
    """Mock FastMCP to capture registered tools."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class TestRefreshUsageStats:
    """Tests for refresh_usage_stats tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.fetch_and_store_all")
    async def test_returns_fetch_results(self, mock_fetch, mock_mcp):
        """Test returning fetch results."""
        mock_fetch.return_value = {
            "success": [{"month": "2025-12", "elo": 1500}],
            "failed": [],
            "total_pokemon": 100,
        }

        refresh_usage_stats = mock_mcp.tools["refresh_usage_stats"]
        result = await refresh_usage_stats()

        assert result["status"] == "completed"
        assert result["successful_fetches"] == 1
        assert result["total_pokemon_records"] == 100

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.fetch_and_store_all")
    async def test_returns_errors_when_failed(self, mock_fetch, mock_mcp):
        """Test returning errors when fetch fails."""
        mock_fetch.return_value = {
            "success": [],
            "failed": [{"month": "2025-12", "elo": 1500}],
            "errors": [
                {"month": "2025-12", "elo": 1500, "category": "network", "message": "Error"}
            ],
            "total_pokemon": 0,
            "circuit_states": {},
        }

        refresh_usage_stats = mock_mcp.tools["refresh_usage_stats"]
        result = await refresh_usage_stats()

        assert result["status"] == "partial"
        assert result["failed_fetches"] == 1
        assert result["failed_details"] is not None
        assert result["error_details"] is not None


class TestGetUsageStatsStatus:
    """Tests for get_usage_stats_status tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.get_all_snapshots")
    async def test_returns_status_when_data_exists(self, mock_get_snapshots, mock_mcp):
        """Test returning status when data exists."""
        mock_snapshot = MagicMock()
        mock_snapshot.format = "regf"
        mock_snapshot.month = "2025-12"
        mock_snapshot.elo_bracket = 1500
        mock_snapshot.num_battles = 100000
        mock_snapshot.fetched_at = "2025-12-15"

        mock_get_snapshots.return_value = [mock_snapshot]

        get_usage_stats_status = mock_mcp.tools["get_usage_stats_status"]
        result = await get_usage_stats_status()

        assert result["status"] == "ready"
        assert result["total_snapshots"] == 1
        assert "regf" in result["formats_available"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.get_all_snapshots")
    async def test_returns_no_data_when_empty(self, mock_get_snapshots, mock_mcp):
        """Test returning no_data when empty."""
        mock_get_snapshots.return_value = []

        get_usage_stats_status = mock_mcp.tools["get_usage_stats_status"]
        result = await get_usage_stats_status()

        assert result["status"] == "no_data"
        assert "Run refresh_usage_stats" in result["message"]


class TestRefreshMovesetData:
    """Tests for refresh_moveset_data tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.fetch_and_store_moveset_all")
    async def test_returns_fetch_results(self, mock_fetch, mock_mcp):
        """Test returning fetch results."""
        mock_fetch.return_value = {
            "success": [{"month": "2025-12", "elo": 1500}],
            "failed": [],
            "total_pokemon_updated": 50,
        }

        refresh_moveset_data = mock_mcp.tools["refresh_moveset_data"]
        result = await refresh_moveset_data()

        assert result["status"] == "completed"
        assert result["total_pokemon_updated"] == 50


class TestRefreshPokepasteData:
    """Tests for refresh_pokepaste_data tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.fetch_and_store_pokepaste_teams")
    async def test_returns_fetch_results(self, mock_fetch, mock_mcp):
        """Test returning fetch results."""
        mock_fetch.return_value = {
            "total_teams": 100,
            "success": 100,
            "failed": 0,
            "skipped": 0,
            "success_details": [],
            "failed_details": [],
            "circuit_states": {},
        }

        refresh_pokepaste_data = mock_mcp.tools["refresh_pokepaste_data"]
        result = await refresh_pokepaste_data()

        assert result["status"] == "completed"
        assert result["total_teams"] == 100
        assert result["successfully_parsed"] == 100


class TestGetPokepasteDataStatus:
    """Tests for get_pokepaste_data_status tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.get_format")
    @patch("smogon_vgc_mcp.tools.admin.get_team_count")
    async def test_returns_status_when_data_exists(self, mock_count, mock_format, mock_mcp):
        """Test returning status when data exists."""
        mock_count.return_value = 500

        mock_fmt = MagicMock()
        mock_fmt.name = "Regulation F"
        mock_format.return_value = mock_fmt

        get_pokepaste_data_status = mock_mcp.tools["get_pokepaste_data_status"]
        result = await get_pokepaste_data_status(format="regf")

        assert result["status"] == "ready"
        assert result["total_teams"] == 500

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.get_team_count")
    async def test_returns_no_data_when_empty(self, mock_count, mock_mcp):
        """Test returning no_data when empty."""
        mock_count.return_value = 0

        get_pokepaste_data_status = mock_mcp.tools["get_pokepaste_data_status"]
        result = await get_pokepaste_data_status()

        assert result["status"] == "no_data"
        assert "Run refresh_pokepaste_data" in result["message"]


class TestRefreshPokedexData:
    """Tests for refresh_pokedex_data tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.fetch_and_store_pokedex_all")
    async def test_returns_fetch_results(self, mock_fetch, mock_mcp):
        """Test returning fetch results."""
        mock_fetch.return_value = {
            "pokemon": 1000,
            "moves": 800,
            "abilities": 300,
            "items": 400,
            "learnsets": 1000,
            "type_chart": 18,
            "errors": None,
        }

        refresh_pokedex_data = mock_mcp.tools["refresh_pokedex_data"]
        result = await refresh_pokedex_data()

        assert result["status"] == "completed"
        assert result["pokemon_count"] == 1000
        assert result["moves_count"] == 800


class TestGetPokedexDataStatus:
    """Tests for get_pokedex_data_status tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.get_pokedex_stats")
    async def test_returns_status_when_data_exists(self, mock_stats, mock_mcp):
        """Test returning status when data exists."""
        mock_stats.return_value = {
            "pokemon": 1000,
            "moves": 800,
            "abilities": 300,
            "items": 400,
        }

        get_pokedex_data_status = mock_mcp.tools["get_pokedex_data_status"]
        result = await get_pokedex_data_status()

        assert result["status"] == "ready"
        assert result["counts"]["pokemon"] == 1000

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.admin.get_pokedex_stats")
    async def test_returns_no_data_when_empty(self, mock_stats, mock_mcp):
        """Test returning no_data when empty."""
        mock_stats.return_value = {
            "pokemon": 0,
            "moves": 0,
            "abilities": 0,
            "items": 0,
        }

        get_pokedex_data_status = mock_mcp.tools["get_pokedex_data_status"]
        result = await get_pokedex_data_status()

        assert result["status"] == "no_data"
        assert "Run refresh_pokedex_data" in result["message"]


class TestListAvailableFormats:
    """Tests for list_available_formats tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.admin import register_admin_tools

        mcp = MockFastMCP()
        register_admin_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_returns_formats(self, mock_mcp):
        """Test returning available formats."""
        list_available_formats = mock_mcp.tools["list_available_formats"]
        result = await list_available_formats()

        assert "formats" in result
        assert len(result["formats"]) > 0
        assert "default_format" in result
