"""Tests for tools/pokemon.py - Pokemon lookup tools."""

from unittest.mock import patch

import pytest

from smogon_vgc_mcp.database.models import (
    AbilityUsage,
    CheckCounter,
    EVSpread,
    ItemUsage,
    MoveUsage,
    PokemonStats,
    TeammateUsage,
    TeraTypeUsage,
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


class TestGetPokemon:
    """Tests for get_pokemon tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokemon import register_pokemon_tools

        mcp = MockFastMCP()
        register_pokemon_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.get_pokemon_stats")
    async def test_returns_pokemon_stats(self, mock_get_stats, mock_mcp):
        """Test returning Pokemon stats."""
        mock_get_stats.return_value = PokemonStats(
            pokemon="Incineroar",
            raw_count=50000,
            usage_percent=48.39,
            viability_ceiling=[1, 1, 1, 1],
            abilities=[AbilityUsage("Intimidate", 49000, 98.0)],
            items=[ItemUsage("Safety Goggles", 20000, 40.0)],
            moves=[MoveUsage("Fake Out", 48000, 96.0)],
            teammates=[TeammateUsage("Flutter Mane", 25000, 50.0)],
            spreads=[EVSpread("Careful", 252, 4, 0, 0, 252, 0, 15000, 30.0)],
        )

        get_pokemon = mock_mcp.tools["get_pokemon"]
        result = await get_pokemon("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert result["usage_percent"] == 48.39
        assert len(result["abilities"]) >= 1
        assert result["abilities"][0]["ability"] == "Intimidate"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.get_pokemon_stats")
    async def test_returns_error_when_not_found(self, mock_get_stats, mock_mcp):
        """Test returning error when Pokemon not found."""
        mock_get_stats.return_value = None

        get_pokemon = mock_mcp.tools["get_pokemon"]
        result = await get_pokemon("NotAPokemon")

        assert "error" in result
        assert "not found" in result["error"]
        assert "hint" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.get_pokemon_stats")
    async def test_includes_tera_types_when_available(self, mock_get_stats, mock_mcp):
        """Test including Tera types when available."""
        mock_get_stats.return_value = PokemonStats(
            pokemon="Incineroar",
            raw_count=50000,
            usage_percent=48.39,
            viability_ceiling=[1, 1, 1, 1],
            tera_types=[
                TeraTypeUsage("Ghost", 45.0),
                TeraTypeUsage("Grass", 30.0),
            ],
        )

        get_pokemon = mock_mcp.tools["get_pokemon"]
        result = await get_pokemon("Incineroar")

        assert "tera_types" in result
        assert len(result["tera_types"]) == 2
        assert result["tera_types"][0]["type"] == "Ghost"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.get_pokemon_stats")
    async def test_includes_checks_counters_when_available(self, mock_get_stats, mock_mcp):
        """Test including checks/counters when available."""
        mock_get_stats.return_value = PokemonStats(
            pokemon="Incineroar",
            raw_count=50000,
            usage_percent=48.39,
            viability_ceiling=[1, 1, 1, 1],
            checks_counters=[
                CheckCounter("Urshifu-Rapid-Strike", 55.0, 60.0, 35.0, 25.0),
            ],
        )

        get_pokemon = mock_mcp.tools["get_pokemon"]
        result = await get_pokemon("Incineroar")

        assert "checks_counters" in result
        assert len(result["checks_counters"]) == 1
        assert result["checks_counters"][0]["pokemon"] == "Urshifu-Rapid-Strike"


class TestFindPokemon:
    """Tests for find_pokemon tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokemon import register_pokemon_tools

        mcp = MockFastMCP()
        register_pokemon_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.search_pokemon")
    async def test_returns_matching_pokemon(self, mock_search, mock_mcp):
        """Test returning matching Pokemon."""
        mock_search.return_value = ["Incineroar", "Incandescent"]

        find_pokemon = mock_mcp.tools["find_pokemon"]
        result = await find_pokemon("inc")

        assert result["query"] == "inc"
        assert len(result["matches"]) == 2
        assert "Incineroar" in result["matches"]
        assert result["count"] == 2

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.search_pokemon")
    async def test_returns_empty_when_no_match(self, mock_search, mock_mcp):
        """Test returning empty when no match."""
        mock_search.return_value = []

        find_pokemon = mock_mcp.tools["find_pokemon"]
        result = await find_pokemon("xyznotapokemon")

        assert result["matches"] == []
        assert "message" in result
        assert "No Pokemon found" in result["message"]


class TestGetPokemonBoundary:
    """Boundary and error tests for get_pokemon tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokemon import register_pokemon_tools

        mcp = MockFastMCP()
        register_pokemon_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_invalid_format_returns_error(self, mock_mcp):
        """Test invalid format code returns error."""
        get_pokemon = mock_mcp.tools["get_pokemon"]
        result = await get_pokemon("Incineroar", format="invalid_format")

        assert "error" in result
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_invalid_elo_returns_error(self, mock_mcp):
        """Test invalid ELO bracket returns error."""
        get_pokemon = mock_mcp.tools["get_pokemon"]
        result = await get_pokemon("Incineroar", elo=999)

        assert "error" in result
        assert "hint" in result


class TestFindPokemonBoundary:
    """Boundary and error tests for find_pokemon tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.pokemon import register_pokemon_tools

        mcp = MockFastMCP()
        register_pokemon_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, mock_mcp):
        """Test empty string query returns error."""
        find_pokemon = mock_mcp.tools["find_pokemon"]
        result = await find_pokemon("")

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.pokemon.search_pokemon")
    async def test_special_characters_handled(self, mock_search, mock_mcp):
        """Test query with special characters handled."""
        mock_search.return_value = []

        find_pokemon = mock_mcp.tools["find_pokemon"]
        result = await find_pokemon("test<>!@#$%")

        assert "error" not in result or "matches" in result

    @pytest.mark.asyncio
    async def test_very_long_query_returns_error(self, mock_mcp):
        """Test query > 100 chars returns error."""
        find_pokemon = mock_mcp.tools["find_pokemon"]
        long_query = "a" * 150
        result = await find_pokemon(long_query)

        assert "error" in result
        assert "hint" in result
