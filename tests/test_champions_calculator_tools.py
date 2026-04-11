"""Tests for Champions calculator MCP tools."""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database.models import ChampionsDexPokemon
from smogon_vgc_mcp.tools.champions_calculator import (
    _parse_sp_spread,
    register_champions_calculator_tools,
)

TEST_VENUSAUR = ChampionsDexPokemon(
    id="venusaur",
    num=3,
    name="Venusaur",
    types=["Grass", "Poison"],
    base_stats={"hp": 80, "atk": 82, "def": 83, "spa": 100, "spd": 100, "spe": 80},
    abilities=["Overgrow"],
    ability_hidden="Chlorophyll",
)

TEST_INCINEROAR = ChampionsDexPokemon(
    id="incineroar",
    num=727,
    name="Incineroar",
    types=["Fire", "Dark"],
    base_stats={"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60},
    abilities=["Blaze"],
    ability_hidden="Intimidate",
)


@pytest.fixture
def mcp_server():
    return FastMCP("test")


class TestToolRegistration:
    def test_all_tools_register(self, mcp_server: FastMCP):
        register_champions_calculator_tools(mcp_server)
        tools = mcp_server._tool_manager._tools
        expected = {
            "calculate_champions_stats",
            "compare_champions_speeds",
            "get_champions_speed_benchmarks",
            "suggest_champions_sp_spread",
        }
        assert expected.issubset(set(tools.keys()))


class TestParseSpSpread:
    def test_valid_spread(self):
        result = _parse_sp_spread("0/0/0/32/0/2")
        assert result == {"hp": 0, "atk": 0, "def": 0, "spa": 32, "spd": 0, "spe": 2}

    def test_all_zeros(self):
        result = _parse_sp_spread("0/0/0/0/0/0")
        assert result == {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}

    def test_max_budget(self):
        result = _parse_sp_spread("11/11/11/11/11/11")
        assert isinstance(result, dict)
        assert sum(result.values()) == 66

    def test_wrong_number_of_values(self):
        result = _parse_sp_spread("0/0/0/0/0")
        assert isinstance(result, str)
        assert "6 values" in result

    def test_non_integer(self):
        result = _parse_sp_spread("0/0/0/abc/0/0")
        assert isinstance(result, str)
        assert "not an integer" in result

    def test_negative_value(self):
        result = _parse_sp_spread("0/0/0/-1/0/0")
        assert isinstance(result, str)
        assert "must be 0-32" in result

    def test_exceeds_per_stat_max(self):
        result = _parse_sp_spread("0/0/0/33/0/0")
        assert isinstance(result, str)
        assert "must be 0-32" in result

    def test_exceeds_total_budget(self):
        result = _parse_sp_spread("32/32/32/0/0/0")
        assert isinstance(result, str)
        assert "exceeds maximum" in result


@pytest.mark.asyncio
class TestCalculateChampionsStats:
    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_valid_pokemon(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["calculate_champions_stats"]
        result = await tool.run(
            arguments={"pokemon": "Venusaur", "sp_spread": "0/0/0/32/0/2"},
        )
        assert "error" not in result
        assert result["pokemon"] == "Venusaur"
        assert result["calculated_stats"]["spa"] > 0
        assert result["nature"] == "Hardy"

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_pokemon_not_found(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = None
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["calculate_champions_stats"]
        result = await tool.run(
            arguments={"pokemon": "FakeMon", "sp_spread": "0/0/0/0/0/0"},
        )
        assert "error" in result

    async def test_invalid_sp_spread(self, mcp_server: FastMCP):
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["calculate_champions_stats"]
        result = await tool.run(
            arguments={"pokemon": "Venusaur", "sp_spread": "32/32/32/0/0/0"},
        )
        assert "error" in result
        assert "exceeds" in result["error"]

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_invalid_nature(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["calculate_champions_stats"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "sp_spread": "0/0/0/0/0/0",
                "nature": "FakeNature",
            },
        )
        assert "error" in result


@pytest.mark.asyncio
class TestCompareChampionsSpeeds:
    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_speed_comparison(self, mock_lookup, mcp_server: FastMCP):
        async def side_effect(pid):
            if pid == "venusaur":
                return TEST_VENUSAUR
            if pid == "incineroar":
                return TEST_INCINEROAR
            return None

        mock_lookup.side_effect = side_effect
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["compare_champions_speeds"]
        result = await tool.run(
            arguments={
                "pokemon1": "Venusaur",
                "sp1": 32,
                "nature1": "Timid",
                "pokemon2": "Incineroar",
                "sp2": 0,
                "nature2": "Adamant",
            },
        )
        assert "error" not in result
        assert result["pokemon1"]["speed"] > result["pokemon2"]["speed"]
        assert result["result"] == "pokemon1_faster"


@pytest.mark.asyncio
class TestGetChampionsSpeedBenchmarks:
    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_benchmarks(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["get_champions_speed_benchmarks"]
        result = await tool.run(
            arguments={"pokemon": "Venusaur", "sp": 32, "nature": "Timid"},
        )
        assert "error" not in result
        assert "outspeeds" in result
        assert "underspeeds" in result
        assert result["pokemon"] == "Venusaur"


@pytest.mark.asyncio
class TestSuggestChampionsSpSpread:
    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_speed_then_maximize(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["suggest_champions_sp_spread"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "nature": "Modest",
                "goals": [
                    {"type": "speed", "target_speed": 100, "mode": "outspeed"},
                    {"type": "maximize", "stat": "spa"},
                ],
            },
        )
        assert "error" not in result
        assert result["success"] is True
        assert result["sp_spread"]["spa"] > 0
        assert "calculated_stats" in result

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_invalid_goal_type(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["suggest_champions_sp_spread"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "nature": "Modest",
                "goals": [{"type": "unknown"}],
            },
        )
        assert "error" in result

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_hp_threshold_goal(self, mock_lookup, mcp_server: FastMCP):
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["suggest_champions_sp_spread"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "nature": "Modest",
                "goals": [
                    {"type": "hp", "item": "Sitrus Berry"},
                    {"type": "maximize", "stat": "spa"},
                ],
            },
        )
        assert "error" not in result
        assert result["success"] is True

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_invalid_nature_rejected(self, mock_lookup, mcp_server: FastMCP):
        """Regression: bad nature must fail loudly, not silently drop final stats."""
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["suggest_champions_sp_spread"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "nature": "Spicy",  # not a real nature
                "goals": [{"type": "maximize", "stat": "spa"}],
            },
        )
        assert "error" in result
        # Must not have silently run the optimizer with a bad nature.
        assert "sp_spread" not in result

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_invalid_speed_target_rejected(self, mock_lookup, mcp_server: FastMCP):
        """Regression: non-numeric target_speed must return a structured error,
        not raise ValueError out of the tool handler."""
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["suggest_champions_sp_spread"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "nature": "Modest",
                "goals": [{"type": "speed", "target_speed": "fast", "mode": "outspeed"}],
            },
        )
        assert "error" in result
        assert "target_speed" in result["error"]

    @patch(
        "smogon_vgc_mcp.tools.champions_calculator._get_champions_base_stats",
        new_callable=AsyncMock,
    )
    async def test_invalid_speed_mode_rejected(self, mock_lookup, mcp_server: FastMCP):
        """Regression: unknown speed mode must return a structured error."""
        mock_lookup.return_value = TEST_VENUSAUR
        register_champions_calculator_tools(mcp_server)
        tool = mcp_server._tool_manager._tools["suggest_champions_sp_spread"]
        result = await tool.run(
            arguments={
                "pokemon": "Venusaur",
                "nature": "Modest",
                "goals": [{"type": "speed", "target_speed": 100, "mode": "sideways"}],
            },
        )
        assert "error" in result
        assert "mode" in result["error"]
