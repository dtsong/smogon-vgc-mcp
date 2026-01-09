"""Tests for tools/rankings.py - Usage rankings tools."""

from unittest.mock import MagicMock, patch

import pytest

from smogon_vgc_mcp.database.models import (
    PokemonStats,
    UsageRanking,
)


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


class TestGetTopPokemon:
    """Tests for get_top_pokemon tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.rankings import register_rankings_tools

        mcp = MockFastMCP()
        register_rankings_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_usage_rankings")
    async def test_returns_rankings(self, mock_get_rankings, mock_mcp):
        """Test returning usage rankings."""
        mock_get_rankings.return_value = [
            UsageRanking(1, "Flutter Mane", 50.1, 52000),
            UsageRanking(2, "Incineroar", 48.39, 50000),
        ]

        get_top_pokemon = mock_mcp.tools["get_top_pokemon"]
        result = await get_top_pokemon()

        assert "rankings" in result
        assert len(result["rankings"]) == 2
        assert result["rankings"][0]["pokemon"] == "Flutter Mane"
        assert result["rankings"][0]["rank"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_usage_rankings")
    async def test_returns_error_when_no_data(self, mock_get_rankings, mock_mcp):
        """Test returning error when no data."""
        mock_get_rankings.return_value = []

        get_top_pokemon = mock_mcp.tools["get_top_pokemon"]
        result = await get_top_pokemon()

        assert "error" in result
        assert "No data found" in result["error"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_usage_rankings")
    async def test_limits_to_50(self, mock_get_rankings, mock_mcp):
        """Test that limit is capped at 50."""
        mock_get_rankings.return_value = []

        get_top_pokemon = mock_mcp.tools["get_top_pokemon"]
        await get_top_pokemon(limit=100)

        # Verify limit was capped
        mock_get_rankings.assert_called_once()
        call_args = mock_get_rankings.call_args
        assert call_args[0][3] == 50  # limit parameter


class TestComparePokemonUsage:
    """Tests for compare_pokemon_usage tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.rankings import register_rankings_tools

        mcp = MockFastMCP()
        register_rankings_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_pokemon_stats")
    @patch("smogon_vgc_mcp.tools.rankings.get_format")
    async def test_compares_months(self, mock_get_format, mock_get_stats, mock_mcp):
        """Test comparing usage across months."""
        # Mock format with multiple months
        mock_format = MagicMock()
        mock_format.name = "Regulation F"
        mock_format.available_months = ["2025-11", "2025-12"]
        mock_get_format.return_value = mock_format

        # Mock stats for both months
        mock_get_stats.side_effect = [
            PokemonStats("Incineroar", 40000, 40.0, [1]),  # First month
            PokemonStats("Incineroar", 50000, 50.0, [1]),  # Last month
        ]

        compare_pokemon_usage = mock_mcp.tools["compare_pokemon_usage"]
        result = await compare_pokemon_usage("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert "change" in result
        assert result["change"]["usage_percent_change"] == 10.0
        assert result["change"]["direction"] == "up"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_pokemon_stats")
    @patch("smogon_vgc_mcp.tools.rankings.get_format")
    async def test_returns_error_when_not_enough_months(self, mock_get_format, mock_get_stats, mock_mcp):
        """Test returning error when not enough months."""
        mock_format = MagicMock()
        mock_format.name = "Test Format"
        mock_format.available_months = ["2025-12"]  # Only one month
        mock_get_format.return_value = mock_format

        compare_pokemon_usage = mock_mcp.tools["compare_pokemon_usage"]
        result = await compare_pokemon_usage("Incineroar")

        assert "error" in result
        assert "Not enough months" in result["error"]


class TestCompareEloBrackets:
    """Tests for compare_elo_brackets tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.rankings import register_rankings_tools

        mcp = MockFastMCP()
        register_rankings_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_pokemon_stats")
    @patch("smogon_vgc_mcp.tools.rankings.get_format")
    async def test_compares_elo_brackets(self, mock_get_format, mock_get_stats, mock_mcp):
        """Test comparing usage across ELO brackets."""
        mock_format = MagicMock()
        mock_format.name = "Regulation F"
        mock_format.available_elos = [0, 1500, 1630, 1760]
        mock_get_format.return_value = mock_format

        # Mock different usage at different ELOs
        mock_get_stats.side_effect = [
            PokemonStats("Incineroar", 60000, 45.0, [1]),  # ELO 0
            PokemonStats("Incineroar", 50000, 48.0, [1]),  # ELO 1500
            PokemonStats("Incineroar", 40000, 50.0, [1]),  # ELO 1630
            PokemonStats("Incineroar", 30000, 52.0, [1]),  # ELO 1760
        ]

        compare_elo_brackets = mock_mcp.tools["compare_elo_brackets"]
        result = await compare_elo_brackets("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert "by_elo" in result
        assert "0" in result["by_elo"]
        assert "1500" in result["by_elo"]
        assert result["by_elo"]["1760"]["usage_percent"] == 52.0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.rankings.get_pokemon_stats")
    @patch("smogon_vgc_mcp.tools.rankings.get_format")
    async def test_returns_error_when_not_found(self, mock_get_format, mock_get_stats, mock_mcp):
        """Test returning error when Pokemon not found in any bracket."""
        mock_format = MagicMock()
        mock_format.name = "Regulation F"
        mock_format.available_elos = [1500]
        mock_get_format.return_value = mock_format

        mock_get_stats.return_value = None

        compare_elo_brackets = mock_mcp.tools["compare_elo_brackets"]
        result = await compare_elo_brackets("NotAPokemon")

        assert "error" in result
        assert "not found" in result["error"]
