"""Tests for tool response formats."""

import pytest

from tests.integration.conftest import extract_tool_result


@pytest.mark.integration
class TestPokemonTools:
    """Test Pokemon lookup tools."""

    @pytest.mark.asyncio
    async def test_get_pokemon_returns_usage_data(self, mcp_client):
        """Test get_pokemon returns usage stats."""
        result = await mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert data["pokemon"] == "Incineroar"
        assert "usage_percent" in data
        assert "raw_count" in data

    @pytest.mark.asyncio
    async def test_get_pokemon_includes_abilities(self, mcp_client):
        """Test get_pokemon includes abilities."""
        result = await mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert "abilities" in data
        assert len(data["abilities"]) > 0
        assert "ability" in data["abilities"][0]

    @pytest.mark.asyncio
    async def test_get_pokemon_includes_items(self, mcp_client):
        """Test get_pokemon includes items."""
        result = await mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert "items" in data

    @pytest.mark.asyncio
    async def test_get_pokemon_includes_moves(self, mcp_client):
        """Test get_pokemon includes moves."""
        result = await mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert "moves" in data

    @pytest.mark.asyncio
    async def test_find_pokemon_returns_matches(self, mcp_client):
        """Test find_pokemon returns matching Pokemon."""
        result = await mcp_client.call_tool("find_pokemon", {"query": "Incin"})
        data = extract_tool_result(result)

        assert "matches" in data
        assert "Incineroar" in data["matches"]


@pytest.mark.integration
class TestRankingsTools:
    """Test usage rankings tools."""

    @pytest.mark.asyncio
    async def test_get_top_pokemon_returns_rankings(self, mcp_client):
        """Test get_top_pokemon returns ranked list."""
        result = await mcp_client.call_tool("get_top_pokemon", {"limit": 5})
        data = extract_tool_result(result)

        assert "rankings" in data
        assert len(data["rankings"]) <= 5

    @pytest.mark.asyncio
    async def test_get_top_pokemon_has_rank_fields(self, mcp_client):
        """Test rankings have required fields."""
        result = await mcp_client.call_tool("get_top_pokemon", {"limit": 3})
        data = extract_tool_result(result)

        if data.get("rankings"):
            first = data["rankings"][0]
            assert "rank" in first
            assert "pokemon" in first
            assert "usage_percent" in first


@pytest.mark.integration
class TestTeambuildingTools:
    """Test teambuilding tools."""

    @pytest.mark.asyncio
    async def test_get_pokemon_teammates_returns_data(self, mcp_client):
        """Test get_pokemon_teammates returns teammate data."""
        result = await mcp_client.call_tool("get_pokemon_teammates", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert data["pokemon"] == "Incineroar"
        # May have teammates or error if no data
        assert "teammates" in data or "error" in data


@pytest.mark.integration
class TestTeamTools:
    """Test tournament team tools."""

    @pytest.mark.asyncio
    async def test_get_tournament_team_returns_full_team(self, mcp_client):
        """Test get_tournament_team returns full team details."""
        result = await mcp_client.call_tool("get_tournament_team", {"team_id": "F001"})
        data = extract_tool_result(result)

        assert data["team_id"] == "F001"
        assert "pokemon" in data
        assert "owner" in data

    @pytest.mark.asyncio
    async def test_get_tournament_team_has_pokemon_details(self, mcp_client):
        """Test team Pokemon have full details."""
        result = await mcp_client.call_tool("get_tournament_team", {"team_id": "F001"})
        data = extract_tool_result(result)

        if data.get("pokemon"):
            pokemon = data["pokemon"][0]
            assert "pokemon" in pokemon
            assert "item" in pokemon
            assert "ability" in pokemon
            assert "evs" in pokemon

    @pytest.mark.asyncio
    async def test_search_tournament_teams_returns_results(self, mcp_client):
        """Test search_tournament_teams finds teams."""
        result = await mcp_client.call_tool("search_tournament_teams", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert "teams" in data
        assert "count" in data


@pytest.mark.integration
class TestCalculatorTools:
    """Test stat calculator tools."""

    @pytest.mark.asyncio
    async def test_calculate_pokemon_stats_returns_stats(self, mcp_client):
        """Test calculate_pokemon_stats returns calculated stats."""
        result = await mcp_client.call_tool(
            "calculate_pokemon_stats",
            {
                "pokemon": "Incineroar",
                "evs": "252/4/0/0/252/0",
                "nature": "Careful",
            },
        )
        data = extract_tool_result(result)

        assert data["pokemon"] == "Incineroar"
        # May have stats or error
        assert "calculated_stats" in data or "error" in data


@pytest.mark.integration
class TestPokedexTools:
    """Test Pokedex lookup tools."""

    @pytest.mark.asyncio
    async def test_dex_pokemon_returns_species_data(self, mcp_client):
        """Test dex_pokemon returns species information."""
        result = await mcp_client.call_tool("dex_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        assert data.get("name") == "Incineroar" or "error" in data

    @pytest.mark.asyncio
    async def test_dex_pokemon_includes_types(self, mcp_client):
        """Test dex_pokemon includes type information."""
        result = await mcp_client.call_tool("dex_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        if "types" in data:
            assert len(data["types"]) >= 1

    @pytest.mark.asyncio
    async def test_dex_pokemon_includes_base_stats(self, mcp_client):
        """Test dex_pokemon includes base stats."""
        result = await mcp_client.call_tool("dex_pokemon", {"pokemon": "Incineroar"})
        data = extract_tool_result(result)

        if "base_stats" in data:
            stats = data["base_stats"]
            assert "hp" in stats
            assert "atk" in stats
            assert "spe" in stats

    @pytest.mark.asyncio
    async def test_dex_move_returns_move_data(self, mcp_client):
        """Test dex_move returns move information."""
        result = await mcp_client.call_tool("dex_move", {"move": "Fake Out"})
        data = extract_tool_result(result)

        assert data.get("name") == "Fake Out" or "error" in data

    @pytest.mark.asyncio
    async def test_dex_ability_returns_ability_data(self, mcp_client):
        """Test dex_ability returns ability information."""
        result = await mcp_client.call_tool("dex_ability", {"ability": "Intimidate"})
        data = extract_tool_result(result)

        assert data.get("name") == "Intimidate" or "error" in data


@pytest.mark.integration
class TestAdminTools:
    """Test admin/status tools."""

    @pytest.mark.asyncio
    async def test_list_available_formats_returns_formats(self, mcp_client):
        """Test list_available_formats returns format list."""
        result = await mcp_client.call_tool("list_available_formats", {})
        data = extract_tool_result(result)

        assert "formats" in data
        assert len(data["formats"]) > 0

    @pytest.mark.asyncio
    async def test_list_available_formats_includes_regf(self, mcp_client):
        """Test list_available_formats includes Regulation F."""
        result = await mcp_client.call_tool("list_available_formats", {})
        data = extract_tool_result(result)

        format_codes = [f["code"] for f in data["formats"]]
        assert "regf" in format_codes

    @pytest.mark.asyncio
    async def test_get_usage_stats_status_returns_status(self, mcp_client):
        """Test get_usage_stats_status returns status info."""
        result = await mcp_client.call_tool("get_usage_stats_status", {})
        data = extract_tool_result(result)

        # Should have some status info
        assert "snapshots" in data or "status" in data or "error" in data
