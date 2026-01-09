"""Tests for error handling in MCP tools."""

import pytest

from tests.integration.conftest import extract_tool_result


@pytest.mark.integration
class TestPokemonValidationErrors:
    """Test validation errors for Pokemon tools."""

    @pytest.mark.asyncio
    async def test_get_pokemon_not_found_returns_error(self, mcp_client):
        """Test get_pokemon with unknown Pokemon returns error."""
        result = await mcp_client.call_tool("get_pokemon", {"pokemon": "NotARealPokemon"})
        data = extract_tool_result(result)

        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_get_pokemon_invalid_format_returns_error(self, mcp_client):
        """Test get_pokemon with invalid format returns error."""
        result = await mcp_client.call_tool(
            "get_pokemon", {"pokemon": "Incineroar", "format": "invalid_format"}
        )
        data = extract_tool_result(result)

        assert "error" in data
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_get_pokemon_invalid_elo_returns_error(self, mcp_client):
        """Test get_pokemon with invalid ELO returns error."""
        result = await mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar", "elo": 9999})
        data = extract_tool_result(result)

        assert "error" in data
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_find_pokemon_empty_query_returns_error(self, mcp_client):
        """Test find_pokemon with empty query returns error."""
        result = await mcp_client.call_tool("find_pokemon", {"query": ""})
        data = extract_tool_result(result)

        assert "error" in data


@pytest.mark.integration
class TestTeamValidationErrors:
    """Test validation errors for team tools."""

    @pytest.mark.asyncio
    async def test_get_tournament_team_not_found_returns_error(self, mcp_client):
        """Test get_tournament_team with invalid ID returns error."""
        result = await mcp_client.call_tool("get_tournament_team", {"team_id": "F99999"})
        data = extract_tool_result(result)

        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_get_tournament_team_invalid_format_returns_error(self, mcp_client):
        """Test get_tournament_team with malformed ID returns error."""
        result = await mcp_client.call_tool("get_tournament_team", {"team_id": "invalid"})
        data = extract_tool_result(result)

        assert "error" in data

    @pytest.mark.asyncio
    async def test_search_teams_no_params_returns_error(self, mcp_client):
        """Test search_tournament_teams without params returns error."""
        result = await mcp_client.call_tool("search_tournament_teams", {})
        data = extract_tool_result(result)

        assert "error" in data
        assert "parameter" in data["error"].lower()


@pytest.mark.integration
class TestCalculatorValidationErrors:
    """Test validation errors for calculator tools."""

    @pytest.mark.asyncio
    async def test_calculate_stats_invalid_nature_returns_error(self, mcp_client):
        """Test calculate_pokemon_stats with invalid nature returns error."""
        result = await mcp_client.call_tool(
            "calculate_pokemon_stats",
            {"pokemon": "Incineroar", "evs": "252/4/0/0/252/0", "nature": "InvalidNature"},
        )
        data = extract_tool_result(result)

        assert "error" in data


@pytest.mark.integration
class TestPokedexValidationErrors:
    """Test validation errors for Pokedex tools."""

    @pytest.mark.asyncio
    async def test_dex_pokemon_not_found_returns_error(self, mcp_client):
        """Test dex_pokemon with unknown Pokemon returns error."""
        result = await mcp_client.call_tool("dex_pokemon", {"pokemon": "NotARealPokemon"})
        data = extract_tool_result(result)

        assert "error" in data

    @pytest.mark.asyncio
    async def test_dex_move_not_found_returns_error(self, mcp_client):
        """Test dex_move with unknown move returns error."""
        result = await mcp_client.call_tool("dex_move", {"move": "NotARealMove"})
        data = extract_tool_result(result)

        assert "error" in data

    @pytest.mark.asyncio
    async def test_dex_ability_not_found_returns_error(self, mcp_client):
        """Test dex_ability with unknown ability returns error."""
        result = await mcp_client.call_tool("dex_ability", {"ability": "NotARealAbility"})
        data = extract_tool_result(result)

        assert "error" in data


@pytest.mark.integration
class TestRankingsValidationErrors:
    """Test validation errors for rankings tools."""

    @pytest.mark.asyncio
    async def test_get_top_pokemon_invalid_format_returns_error(self, mcp_client):
        """Test get_top_pokemon with invalid format returns error."""
        result = await mcp_client.call_tool("get_top_pokemon", {"format": "invalid_format"})
        data = extract_tool_result(result)

        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_top_pokemon_invalid_elo_returns_error(self, mcp_client):
        """Test get_top_pokemon with invalid ELO returns error."""
        result = await mcp_client.call_tool("get_top_pokemon", {"elo": 9999})
        data = extract_tool_result(result)

        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_top_pokemon_limit_zero_returns_error(self, mcp_client):
        """Test get_top_pokemon with limit=0 returns error."""
        result = await mcp_client.call_tool("get_top_pokemon", {"limit": 0})
        data = extract_tool_result(result)

        assert "error" in data
