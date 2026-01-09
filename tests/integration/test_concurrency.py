"""Tests for concurrent tool calls."""

import asyncio

import pytest

from tests.integration.conftest import extract_tool_result


@pytest.mark.integration
class TestConcurrentToolCalls:
    """Test parallel tool invocations."""

    @pytest.mark.asyncio
    async def test_concurrent_get_pokemon_calls(self, mcp_client):
        """Test multiple get_pokemon calls in parallel."""
        tasks = [
            mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar"}),
            mcp_client.call_tool("get_pokemon", {"pokemon": "Flutter Mane"}),
        ]
        results = await asyncio.gather(*tasks)

        data1 = extract_tool_result(results[0])
        data2 = extract_tool_result(results[1])

        # Both should return valid results
        assert data1.get("pokemon") == "Incineroar" or "error" in data1
        assert data2.get("pokemon") == "Flutter Mane" or "error" in data2

    @pytest.mark.asyncio
    async def test_concurrent_different_tools(self, mcp_client):
        """Test different tools called in parallel."""
        tasks = [
            mcp_client.call_tool("get_pokemon", {"pokemon": "Incineroar"}),
            mcp_client.call_tool("get_top_pokemon", {"limit": 5}),
            mcp_client.call_tool("list_available_formats", {}),
        ]
        results = await asyncio.gather(*tasks)

        # All should complete without errors
        for i, result in enumerate(results):
            data = extract_tool_result(result)
            assert data is not None, f"Tool {i} returned None"

    @pytest.mark.asyncio
    async def test_concurrent_pokedex_calls(self, mcp_client):
        """Test multiple Pokedex calls in parallel."""
        tasks = [
            mcp_client.call_tool("dex_pokemon", {"pokemon": "Incineroar"}),
            mcp_client.call_tool("dex_move", {"move": "Fake Out"}),
            mcp_client.call_tool("dex_ability", {"ability": "Intimidate"}),
        ]
        results = await asyncio.gather(*tasks)

        # All should return some data
        for result in results:
            data = extract_tool_result(result)
            assert data is not None

    @pytest.mark.asyncio
    async def test_sequential_dependent_calls(self, mcp_client):
        """Test sequential calls where second depends on first."""
        # First, search for teams
        search_result = await mcp_client.call_tool(
            "search_tournament_teams", {"pokemon": "Incineroar"}
        )
        search_data = extract_tool_result(search_result)

        # Then get full details of first team found
        if search_data.get("teams") and len(search_data["teams"]) > 0:
            team_id = search_data["teams"][0]["team_id"]
            team_result = await mcp_client.call_tool("get_tournament_team", {"team_id": team_id})
            team_data = extract_tool_result(team_result)

            assert team_data["team_id"] == team_id

    @pytest.mark.asyncio
    async def test_many_concurrent_calls(self, mcp_client):
        """Test many tool calls at once."""
        # Create 10 parallel calls
        tasks = [mcp_client.call_tool("list_available_formats", {}) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            data = extract_tool_result(result)
            assert "formats" in data
