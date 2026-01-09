"""Tests for resources/vgc.py - VGC data resources."""

import json
from unittest.mock import patch

import pytest

from smogon_vgc_mcp.database.models import (
    AbilityUsage,
    EVSpread,
    ItemUsage,
    MoveUsage,
    PokemonStats,
    Snapshot,
    TeammateUsage,
    UsageRanking,
)


# Create mock FastMCP for testing resources
class MockFastMCP:
    """Mock FastMCP to capture registered resources."""

    def __init__(self):
        self.resources = {}

    def resource(self, uri_template):
        def decorator(func):
            self.resources[uri_template] = func
            return func
        return decorator


class TestPokemonResource:
    """Tests for pokemon resource."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register resources."""
        from smogon_vgc_mcp.resources.vgc import register_vgc_resources

        mcp = MockFastMCP()
        register_vgc_resources(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.resources.vgc.get_pokemon_stats")
    async def test_returns_pokemon_data(self, mock_get_stats, mock_mcp):
        """Test returning Pokemon data as JSON."""
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

        pokemon_resource = mock_mcp.resources["vgc://pokemon/{name}"]
        result = await pokemon_resource("Incineroar")

        data = json.loads(result)
        assert data["pokemon"] == "Incineroar"
        assert data["usage_percent"] == 48.39
        assert len(data["abilities"]) >= 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.resources.vgc.get_pokemon_stats")
    async def test_returns_error_when_not_found(self, mock_get_stats, mock_mcp):
        """Test returning error when Pokemon not found."""
        mock_get_stats.return_value = None

        pokemon_resource = mock_mcp.resources["vgc://pokemon/{name}"]
        result = await pokemon_resource("NotAPokemon")

        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"]


class TestRankingsResource:
    """Tests for rankings resource."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register resources."""
        from smogon_vgc_mcp.resources.vgc import register_vgc_resources

        mcp = MockFastMCP()
        register_vgc_resources(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.resources.vgc.get_usage_rankings")
    async def test_returns_rankings(self, mock_get_rankings, mock_mcp):
        """Test returning rankings as JSON."""
        mock_get_rankings.return_value = [
            UsageRanking(1, "Flutter Mane", 50.1, 52000),
            UsageRanking(2, "Incineroar", 48.39, 50000),
        ]

        rankings_resource = mock_mcp.resources["vgc://rankings/{month}/{elo}"]
        result = await rankings_resource("2025-12", "1500")

        data = json.loads(result)
        assert data["month"] == "2025-12"
        assert data["elo"] == 1500
        assert len(data["rankings"]) == 2
        assert data["rankings"][0]["rank"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.resources.vgc.get_usage_rankings")
    async def test_returns_error_when_no_data(self, mock_get_rankings, mock_mcp):
        """Test returning error when no rankings data."""
        mock_get_rankings.return_value = []

        rankings_resource = mock_mcp.resources["vgc://rankings/{month}/{elo}"]
        result = await rankings_resource("2025-12", "1500")

        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_elo(self, mock_mcp):
        """Test returning error for invalid ELO."""
        rankings_resource = mock_mcp.resources["vgc://rankings/{month}/{elo}"]
        result = await rankings_resource("2025-12", "invalid")

        data = json.loads(result)
        assert "error" in data
        assert "Invalid ELO" in data["error"]


class TestStatusResource:
    """Tests for status resource."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register resources."""
        from smogon_vgc_mcp.resources.vgc import register_vgc_resources

        mcp = MockFastMCP()
        register_vgc_resources(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.resources.vgc.get_all_snapshots")
    async def test_returns_status_when_data_exists(self, mock_get_snapshots, mock_mcp):
        """Test returning status when data exists."""
        mock_get_snapshots.return_value = [
            Snapshot(
                id=1,
                format="regf",
                month="2025-12",
                elo_bracket=1500,
                num_battles=100000,
                fetched_at="2025-12-15",
            )
        ]

        status_resource = mock_mcp.resources["vgc://meta/status"]
        result = await status_resource()

        data = json.loads(result)
        assert data["status"] == "ready"
        assert data["total_snapshots"] == 1
        assert "regf" in data["formats_available"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.resources.vgc.get_all_snapshots")
    async def test_returns_no_data_status(self, mock_get_snapshots, mock_mcp):
        """Test returning no_data status when empty."""
        mock_get_snapshots.return_value = []

        status_resource = mock_mcp.resources["vgc://meta/status"]
        result = await status_resource()

        data = json.loads(result)
        assert data["status"] == "no_data"
        assert "Run refresh_data" in data["message"]
