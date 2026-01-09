"""Tests for tools/teambuilding.py - Team building tools."""

from unittest.mock import patch

import pytest

from smogon_vgc_mcp.database.models import CheckCounter, TeammateUsage


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


class TestGetPokemonTeammates:
    """Tests for get_pokemon_teammates tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teambuilding import register_teambuilding_tools

        mcp = MockFastMCP()
        register_teambuilding_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.get_teammates")
    async def test_returns_teammates(self, mock_get_teammates, mock_mcp):
        """Test returning teammates."""
        mock_get_teammates.return_value = [
            TeammateUsage("Flutter Mane", 25000, 50.0),
            TeammateUsage("Raging Bolt", 20000, 40.0),
        ]

        get_pokemon_teammates = mock_mcp.tools["get_pokemon_teammates"]
        result = await get_pokemon_teammates("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert len(result["teammates"]) == 2
        assert result["teammates"][0]["teammate"] == "Flutter Mane"
        assert result["teammates"][0]["percent"] == 50.0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.get_teammates")
    async def test_returns_error_when_no_data(self, mock_get_teammates, mock_mcp):
        """Test returning error when no data."""
        mock_get_teammates.return_value = []

        get_pokemon_teammates = mock_mcp.tools["get_pokemon_teammates"]
        result = await get_pokemon_teammates("NotAPokemon")

        assert "error" in result
        assert "No teammate data" in result["error"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.get_teammates")
    async def test_limits_to_20(self, mock_get_teammates, mock_mcp):
        """Test that limit is capped at 20."""
        mock_get_teammates.return_value = []

        get_pokemon_teammates = mock_mcp.tools["get_pokemon_teammates"]
        await get_pokemon_teammates("Incineroar", limit=50)

        mock_get_teammates.assert_called_once()
        call_args = mock_get_teammates.call_args
        assert call_args[0][4] == 20  # limit parameter


class TestFindPokemonByItem:
    """Tests for find_pokemon_by_item tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teambuilding import register_teambuilding_tools

        mcp = MockFastMCP()
        register_teambuilding_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.find_by_item")
    async def test_returns_pokemon_with_item(self, mock_find_by_item, mock_mcp):
        """Test returning Pokemon with item."""
        mock_find_by_item.return_value = [
            {"pokemon": "Incineroar", "percent": 40.0},
            {"pokemon": "Amoonguss", "percent": 30.0},
        ]

        find_pokemon_by_item = mock_mcp.tools["find_pokemon_by_item"]
        result = await find_pokemon_by_item("Safety Goggles")

        assert result["item"] == "Safety Goggles"
        assert len(result["pokemon"]) == 2
        assert result["pokemon"][0]["pokemon"] == "Incineroar"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.find_by_item")
    async def test_returns_error_when_no_data(self, mock_find_by_item, mock_mcp):
        """Test returning error when no data."""
        mock_find_by_item.return_value = []

        find_pokemon_by_item = mock_mcp.tools["find_pokemon_by_item"]
        result = await find_pokemon_by_item("notanitem")

        assert "error" in result
        assert "No Pokemon found" in result["error"]


class TestFindPokemonByMove:
    """Tests for find_pokemon_by_move tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teambuilding import register_teambuilding_tools

        mcp = MockFastMCP()
        register_teambuilding_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.find_by_move")
    async def test_returns_pokemon_with_move(self, mock_find_by_move, mock_mcp):
        """Test returning Pokemon with move."""
        mock_find_by_move.return_value = [
            {"pokemon": "Incineroar", "percent": 96.0},
            {"pokemon": "Rillaboom", "percent": 70.0},
        ]

        find_pokemon_by_move = mock_mcp.tools["find_pokemon_by_move"]
        result = await find_pokemon_by_move("Fake Out")

        assert result["move"] == "Fake Out"
        assert len(result["pokemon"]) == 2
        assert result["pokemon"][0]["pokemon"] == "Incineroar"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.find_by_move")
    async def test_returns_error_when_no_data(self, mock_find_by_move, mock_mcp):
        """Test returning error when no data."""
        mock_find_by_move.return_value = []

        find_pokemon_by_move = mock_mcp.tools["find_pokemon_by_move"]
        result = await find_pokemon_by_move("notamove")

        assert "error" in result
        assert "No Pokemon found" in result["error"]


class TestFindPokemonByTera:
    """Tests for find_pokemon_by_tera tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teambuilding import register_teambuilding_tools

        mcp = MockFastMCP()
        register_teambuilding_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.find_by_tera_type")
    async def test_returns_pokemon_with_tera(self, mock_find_by_tera, mock_mcp):
        """Test returning Pokemon with Tera type."""
        mock_find_by_tera.return_value = [
            {"pokemon": "Incineroar", "percent": 45.0},
            {"pokemon": "Flutter Mane", "percent": 20.0},
        ]

        find_pokemon_by_tera = mock_mcp.tools["find_pokemon_by_tera"]
        result = await find_pokemon_by_tera("Ghost")

        assert result["tera_type"] == "Ghost"
        assert len(result["pokemon"]) == 2
        assert result["pokemon"][0]["pokemon"] == "Incineroar"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.find_by_tera_type")
    async def test_returns_error_when_no_data(self, mock_find_by_tera, mock_mcp):
        """Test returning error when no data."""
        mock_find_by_tera.return_value = []

        find_pokemon_by_tera = mock_mcp.tools["find_pokemon_by_tera"]
        result = await find_pokemon_by_tera("Ghost")

        assert "error" in result
        assert "No Pokemon found" in result["error"]


class TestGetPokemonCounters:
    """Tests for get_pokemon_counters tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.teambuilding import register_teambuilding_tools

        mcp = MockFastMCP()
        register_teambuilding_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.get_counters_for")
    async def test_returns_counters(self, mock_get_counters, mock_mcp):
        """Test returning counters."""
        mock_get_counters.return_value = [
            CheckCounter("Urshifu-Rapid-Strike", 55.0, 60.0, 35.0, 25.0),
        ]

        get_pokemon_counters = mock_mcp.tools["get_pokemon_counters"]
        result = await get_pokemon_counters("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert len(result["counters"]) == 1
        assert result["counters"][0]["pokemon"] == "Urshifu-Rapid-Strike"
        assert result["counters"][0]["score"] == 55.0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.teambuilding.get_counters_for")
    async def test_returns_error_when_no_data(self, mock_get_counters, mock_mcp):
        """Test returning error when no data."""
        mock_get_counters.return_value = []

        get_pokemon_counters = mock_mcp.tools["get_pokemon_counters"]
        result = await get_pokemon_counters("NotAPokemon")

        assert "error" in result
        assert "No counter data" in result["error"]
