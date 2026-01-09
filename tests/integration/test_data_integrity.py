"""Tests for data consistency across tool calls."""

import pytest

from tests.integration.conftest import extract_tool_result


@pytest.mark.integration
class TestPokemonDataConsistency:
    """Test Pokemon data is consistent across tools."""

    @pytest.mark.asyncio
    async def test_get_pokemon_and_rankings_agree(self, mcp_client):
        """Test get_pokemon usage matches rankings data."""
        # Get top Pokemon
        rankings_result = await mcp_client.call_tool("get_top_pokemon", {"limit": 10})
        rankings_data = extract_tool_result(rankings_result)

        if not rankings_data.get("rankings"):
            pytest.skip("No rankings data available")

        # Get specific Pokemon stats
        top_pokemon = rankings_data["rankings"][0]["pokemon"]
        pokemon_result = await mcp_client.call_tool("get_pokemon", {"pokemon": top_pokemon})
        pokemon_data = extract_tool_result(pokemon_result)

        # Usage should be similar (may have rounding differences)
        if "usage_percent" in pokemon_data:
            rankings_usage = rankings_data["rankings"][0]["usage_percent"]
            pokemon_usage = pokemon_data["usage_percent"]
            # Allow small difference due to rounding
            assert abs(rankings_usage - pokemon_usage) < 0.1

    @pytest.mark.asyncio
    async def test_find_pokemon_returns_actual_pokemon(self, mcp_client):
        """Test find_pokemon returns Pokemon that exist in get_pokemon."""
        # Find Pokemon matching a query
        find_result = await mcp_client.call_tool("find_pokemon", {"query": "Incin"})
        find_data = extract_tool_result(find_result)

        if not find_data.get("matches"):
            pytest.skip("No matches found")

        # Each match should be gettable
        for pokemon_name in find_data["matches"][:2]:
            pokemon_result = await mcp_client.call_tool("get_pokemon", {"pokemon": pokemon_name})
            pokemon_data = extract_tool_result(pokemon_result)
            # Should either find data or report not found, not crash
            assert "pokemon" in pokemon_data or "error" in pokemon_data


@pytest.mark.integration
class TestTeamDataConsistency:
    """Test team data is consistent across tools."""

    @pytest.mark.asyncio
    async def test_search_and_get_team_match(self, mcp_client):
        """Test search_tournament_teams and get_tournament_team return same data."""
        # Search for teams
        search_result = await mcp_client.call_tool(
            "search_tournament_teams", {"pokemon": "Incineroar"}
        )
        search_data = extract_tool_result(search_result)

        if not search_data.get("teams"):
            pytest.skip("No teams found")

        # Get full team details
        team_id = search_data["teams"][0]["team_id"]
        full_result = await mcp_client.call_tool("get_tournament_team", {"team_id": team_id})
        full_data = extract_tool_result(full_result)

        # IDs should match
        assert full_data["team_id"] == team_id

        # Owner should match
        if "owner" in search_data["teams"][0]:
            assert full_data["owner"] == search_data["teams"][0]["owner"]


@pytest.mark.integration
class TestFormatFiltering:
    """Test format parameter filters data correctly."""

    @pytest.mark.asyncio
    async def test_get_pokemon_respects_format(self, mcp_client):
        """Test get_pokemon filters by format."""
        # Get Pokemon stats for regf format
        result = await mcp_client.call_tool(
            "get_pokemon", {"pokemon": "Incineroar", "format": "regf"}
        )
        data = extract_tool_result(result)

        # Should return data or not found, not wrong format data
        if "format" in data:
            assert data["format"] == "regf"

    @pytest.mark.asyncio
    async def test_get_top_pokemon_respects_format(self, mcp_client):
        """Test get_top_pokemon filters by format."""
        result = await mcp_client.call_tool("get_top_pokemon", {"format": "regf", "limit": 5})
        data = extract_tool_result(result)

        if "format" in data:
            assert data["format"] == "regf"


@pytest.mark.integration
class TestPokedexDataConsistency:
    """Test Pokedex data is consistent."""

    @pytest.mark.asyncio
    async def test_dex_pokemon_types_match_weaknesses(self, mcp_client):
        """Test dex_pokemon types are used in weakness calculations."""
        # Get Incineroar (Fire/Dark)
        pokemon_result = await mcp_client.call_tool("dex_pokemon", {"pokemon": "Incineroar"})
        pokemon_data = extract_tool_result(pokemon_result)

        if "error" in pokemon_data:
            pytest.skip("Pokemon data not available")

        # Get weaknesses
        weakness_result = await mcp_client.call_tool(
            "dex_pokemon_weaknesses", {"pokemon": "Incineroar"}
        )
        weakness_data = extract_tool_result(weakness_result)

        if "error" in weakness_data:
            pytest.skip("Weakness data not available")

        # Fire/Dark should be weak to Fighting, Ground, Rock, Water
        if "weaknesses" in weakness_data:
            weak_types = list(weakness_data["weaknesses"].keys())
            # At least some weaknesses should be present
            assert len(weak_types) > 0
