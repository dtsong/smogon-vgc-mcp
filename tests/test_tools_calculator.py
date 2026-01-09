"""Tests for tools/calculator.py - Calculator tools."""

from unittest.mock import patch

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


class TestCalculatePokemonStats:
    """Tests for calculate_pokemon_stats tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.format_stats")
    @patch("smogon_vgc_mcp.tools.calculator.calculate_all_stats")
    @patch("smogon_vgc_mcp.tools.calculator.get_base_stats")
    async def test_returns_calculated_stats(self, mock_base, mock_calc, mock_format, mock_mcp):
        """Test returning calculated stats."""
        mock_base.return_value = {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}
        mock_calc.return_value = {"hp": 202, "atk": 167, "def": 110, "spa": 100, "spd": 142, "spe": 80}
        mock_format.return_value = "HP: 202 | Atk: 167 | Def: 110 | SpA: 100 | SpD: 142 | Spe: 80"

        calculate_pokemon_stats = mock_mcp.tools["calculate_pokemon_stats"]
        result = await calculate_pokemon_stats("Incineroar", "252/4/0/0/252/0", "Careful")

        assert result["pokemon"] == "Incineroar"
        assert result["nature"] == "Careful"
        assert result["calculated_stats"]["hp"] == 202

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.get_base_stats")
    async def test_returns_error_when_pokemon_not_found(self, mock_base, mock_mcp):
        """Test returning error when Pokemon not found."""
        mock_base.return_value = None

        calculate_pokemon_stats = mock_mcp.tools["calculate_pokemon_stats"]
        result = await calculate_pokemon_stats("NotAPokemon", "252/252/4/0/0/0", "Adamant")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.calculate_all_stats")
    @patch("smogon_vgc_mcp.tools.calculator.get_base_stats")
    async def test_returns_error_when_calc_fails(self, mock_base, mock_calc, mock_mcp):
        """Test returning error when calculation fails."""
        mock_base.return_value = {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}
        mock_calc.return_value = None

        calculate_pokemon_stats = mock_mcp.tools["calculate_pokemon_stats"]
        result = await calculate_pokemon_stats("Incineroar", "invalid", "Careful")

        assert "error" in result


class TestComparePokemonSpeeds:
    """Tests for compare_pokemon_speeds tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.compare_speeds")
    async def test_returns_speed_comparison(self, mock_compare, mock_mcp):
        """Test returning speed comparison."""
        mock_compare.return_value = {
            "pokemon1": {"name": "Flutter Mane", "speed": 205, "nature": "Timid"},
            "pokemon2": {"name": "Incineroar", "speed": 80, "nature": "Careful"},
            "difference": 125,
            "result": "Flutter Mane outspeeds Incineroar",
            "faster": "Flutter Mane",
        }

        compare_pokemon_speeds = mock_mcp.tools["compare_pokemon_speeds"]
        result = await compare_pokemon_speeds(
            "Flutter Mane", "4/0/0/252/0/252", "Timid",
            "Incineroar", "252/4/0/0/252/0", "Careful"
        )

        assert result["faster"] == "Flutter Mane"
        assert result["difference"] == 125


class TestGetSpeedBenchmarks:
    """Tests for get_speed_benchmarks tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.find_speed_benchmarks")
    @patch("smogon_vgc_mcp.tools.calculator.get_speed_stat")
    async def test_returns_benchmarks(self, mock_get_speed, mock_find_bench, mock_mcp):
        """Test returning speed benchmarks."""
        mock_get_speed.return_value = 205
        mock_find_bench.return_value = {
            "pokemon": "Flutter Mane",
            "speed_stat": 205,
            "outspeeds_max": [{"pokemon": "Charizard", "max_speed": 167}],
            "underspeeds_min": [],
            "speed_ties_possible": [],
        }

        get_speed_benchmarks = mock_mcp.tools["get_speed_benchmarks"]
        result = await get_speed_benchmarks("Flutter Mane", "4/0/0/252/0/252", "Timid")

        assert result["speed_stat"] == 205
        assert "outspeeds_max" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.get_speed_stat")
    async def test_returns_error_when_calc_fails(self, mock_get_speed, mock_mcp):
        """Test returning error when calculation fails."""
        mock_get_speed.return_value = None

        get_speed_benchmarks = mock_mcp.tools["get_speed_benchmarks"]
        result = await get_speed_benchmarks("NotAPokemon", "252/252/4/0/0/0", "Adamant")

        assert "error" in result


class TestGetTypeWeaknesses:
    """Tests for get_type_weaknesses tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.get_pokemon_weaknesses")
    async def test_returns_weaknesses(self, mock_get_weak, mock_mcp):
        """Test returning weaknesses."""
        mock_get_weak.return_value = {
            "pokemon": "Incineroar",
            "types": ["Fire", "Dark"],
            "4x_weak": [],
            "2x_weak": ["Water", "Fighting", "Ground", "Rock"],
            "immunities": ["Psychic"],
        }

        get_type_weaknesses = mock_mcp.tools["get_type_weaknesses"]
        result = await get_type_weaknesses("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert "Water" in result["2x_weak"]


class TestAnalyzeTeamTypeCoverage:
    """Tests for analyze_team_type_coverage tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.analyze_team_types")
    async def test_returns_team_analysis(self, mock_analyze, mock_mcp):
        """Test returning team type analysis."""
        mock_analyze.return_value = {
            "team": ["Incineroar", "Flutter Mane"],
            "pokemon_types": {
                "Incineroar": ["Fire", "Dark"],
                "Flutter Mane": ["Ghost", "Fairy"],
            },
            "shared_weaknesses": {"Water": {"count": 1}},
            "errors": None,
        }

        analyze_team_type_coverage = mock_mcp.tools["analyze_team_type_coverage"]
        result = await analyze_team_type_coverage(["Incineroar", "Flutter Mane"])

        assert "team" in result
        assert len(result["team"]) == 2


class TestGetPokemonBaseStats:
    """Tests for get_pokemon_base_stats tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.get_pokemon_types")
    @patch("smogon_vgc_mcp.tools.calculator.get_base_stats")
    async def test_returns_base_stats(self, mock_base, mock_types, mock_mcp):
        """Test returning base stats."""
        mock_base.return_value = {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}
        mock_types.return_value = ["Fire", "Dark"]

        get_pokemon_base_stats = mock_mcp.tools["get_pokemon_base_stats"]
        result = await get_pokemon_base_stats("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert result["types"] == ["Fire", "Dark"]
        assert result["base_stats"]["atk"] == 115
        assert result["bst"] == 530  # Sum of all base stats

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.get_base_stats")
    async def test_returns_error_when_not_found(self, mock_base, mock_mcp):
        """Test returning error when Pokemon not found."""
        mock_base.return_value = None

        get_pokemon_base_stats = mock_mcp.tools["get_pokemon_base_stats"]
        result = await get_pokemon_base_stats("NotAPokemon")

        assert "error" in result


class TestAnalyzeMoveCoverage:
    """Tests for analyze_move_coverage tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.calculator import register_calculator_tools

        mcp = MockFastMCP()
        register_calculator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.calculator.get_offensive_coverage")
    async def test_returns_coverage(self, mock_coverage, mock_mcp):
        """Test returning move coverage."""
        mock_coverage.return_value = {
            "move_types": ["Fire", "Dark"],
            "super_effective_against": ["Grass", "Ghost", "Psychic"],
            "immune_types": [],
        }

        analyze_move_coverage = mock_mcp.tools["analyze_move_coverage"]
        result = await analyze_move_coverage(["Fire", "Dark"])

        assert result["move_types"] == ["Fire", "Dark"]
        assert "Grass" in result["super_effective_against"]
