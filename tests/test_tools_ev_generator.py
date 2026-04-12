"""Tests for tools/ev_generator.py - EV spread generation tools."""

from unittest.mock import patch

import pytest

from smogon_vgc_mcp.calculator.ev_optimizer import GoalResult, OptimizedSpread


class MockFastMCP:
    """Mock FastMCP to capture registered tools."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def make_optimized_spread(
    pokemon: str = "Incineroar",
    nature: str = "Careful",
    evs: dict | None = None,
    ivs: dict | None = None,
    stats: dict | None = None,
    goal_results: list[GoalResult] | None = None,
    ev_total: int = 508,
    suggestions: list[str] | None = None,
) -> OptimizedSpread:
    """Create a sample OptimizedSpread for testing."""
    if evs is None:
        evs = {"hp": 252, "atk": 4, "def": 0, "spa": 0, "spd": 252, "spe": 0}
    if ivs is None:
        ivs = {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}
    if stats is None:
        stats = {"hp": 202, "atk": 136, "def": 110, "spa": 100, "spd": 156, "spe": 80}
    if goal_results is None:
        goal_results = [
            GoalResult(
                goal_description="Survive Flutter Mane Moonblast",
                achieved=True,
                evs_used={"hp": 252, "spd": 252},
                detail="Takes 70-82.6%",
            )
        ]

    return OptimizedSpread(
        pokemon=pokemon,
        nature=nature,
        evs=evs,
        ivs=ivs,
        calculated_stats=stats,
        goal_results=goal_results,
        ev_total=ev_total,
        suggestions=suggestions or [],
    )


class TestSuggestEVSpread:
    """Tests for suggest_ev_spread tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.ev_generator import register_ev_generator_tools

        mcp = MockFastMCP()
        register_ev_generator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_returns_optimized_spread(self, mock_optimize, mock_mcp):
        """Test valid inputs return spread."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "survive", "attacker": "Flutter Mane", "move": "Moonblast"}],
        )

        assert "error" not in result
        assert result["pokemon"] == "Incineroar"
        assert "spread" in result
        assert "goal_results" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_multiple_goals_processed(self, mock_optimize, mock_mcp):
        """Test multiple goals handled."""
        mock_optimize.return_value = make_optimized_spread(
            goal_results=[
                GoalResult(
                    "Survive Flutter Mane Moonblast", True, {"hp": 252, "spd": 252}, "70-82.6%"
                ),
                GoalResult("Outspeed Amoonguss", True, {"spe": 4}, "81 vs 31"),
                GoalResult("Maximize HP", True, {"hp": 252}, "202 HP"),
            ]
        )

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[
                {"type": "survive", "attacker": "Flutter Mane", "move": "Moonblast"},
                {"type": "outspeed", "target": "Amoonguss"},
                {"type": "maximize", "stat": "hp"},
            ],
        )

        assert len(result["goal_results"]) == 3

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_includes_calculated_stats(self, mock_optimize, mock_mcp):
        """Test stats calculated."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "maximize", "stat": "hp"}],
        )

        assert "calculated_stats" in result
        assert result["calculated_stats"]["hp"] == 202

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_formats_evs_correctly(self, mock_optimize, mock_mcp):
        """Test evs and evs_compact present."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "maximize", "stat": "hp"}],
        )

        assert "evs" in result["spread"]
        assert "evs_compact" in result["spread"]
        assert result["spread"]["evs_compact"] == "252/4/0/0/252/0"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_parse_survive_goal(self, mock_optimize, mock_mcp):
        """Test survive goal parsed."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[
                {
                    "type": "survive",
                    "attacker": "Flutter Mane",
                    "move": "Moonblast",
                    "attacker_evs": "252/0/0/252/0/252",
                    "attacker_nature": "Timid",
                }
            ],
        )

        mock_optimize.assert_called_once()
        call_args = mock_optimize.call_args
        goals = call_args.kwargs.get("goals") or call_args[1].get("goals")
        assert len(goals) == 1
        assert goals[0].attacker == "Flutter Mane"
        assert goals[0].move == "Moonblast"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_parse_ohko_goal(self, mock_optimize, mock_mcp):
        """Test OHKO goal parsed."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        await suggest_ev_spread(
            pokemon="Flutter Mane",
            goals=[
                {
                    "type": "ohko",
                    "defender": "Incineroar",
                    "move": "Moonblast",
                }
            ],
        )

        mock_optimize.assert_called_once()
        goals = mock_optimize.call_args.kwargs.get("goals") or mock_optimize.call_args[1].get(
            "goals"
        )
        assert len(goals) == 1
        assert goals[0].defender == "Incineroar"
        assert goals[0].move == "Moonblast"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_parse_outspeed_goal(self, mock_optimize, mock_mcp):
        """Test outspeed goal parsed."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "outspeed", "target": "Amoonguss"}],
        )

        goals = mock_optimize.call_args.kwargs.get("goals") or mock_optimize.call_args[1].get(
            "goals"
        )
        assert goals[0].target == "Amoonguss"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_parse_underspeed_goal(self, mock_optimize, mock_mcp):
        """Test underspeed goal parsed."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        await suggest_ev_spread(
            pokemon="Torkoal",
            goals=[{"type": "underspeed", "target": "Dondozo"}],
        )

        goals = mock_optimize.call_args.kwargs.get("goals") or mock_optimize.call_args[1].get(
            "goals"
        )
        assert goals[0].target == "Dondozo"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.optimize_spread")
    async def test_parse_maximize_goal(self, mock_optimize, mock_mcp):
        """Test maximize goal parsed."""
        mock_optimize.return_value = make_optimized_spread()

        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "maximize", "stat": "hp"}],
        )

        goals = mock_optimize.call_args.kwargs.get("goals") or mock_optimize.call_args[1].get(
            "goals"
        )
        assert goals[0].stat == "hp"

    @pytest.mark.asyncio
    async def test_empty_goals_list(self, mock_mcp):
        """Test no valid goals error."""
        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[],
        )

        assert "error" in result
        assert "No valid goals" in result["error"]

    @pytest.mark.asyncio
    async def test_all_goals_invalid(self, mock_mcp):
        """Test all goals unparseable returns error."""
        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "invalid_type"}],
        )

        assert "error" in result
        assert "No valid goals" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_pokemon_name(self, mock_mcp):
        """Test unknown Pokemon returns error."""
        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="NotAPokemon",
            goals=[{"type": "maximize", "stat": "hp"}],
        )

        assert "error" in result
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_invalid_nature(self, mock_mcp):
        """Test bad nature name returns error."""
        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "maximize", "stat": "hp"}],
            nature="NotANature",
        )

        assert "error" in result
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_invalid_tera_type(self, mock_mcp):
        """Test bad Tera type returns error."""
        suggest_ev_spread = mock_mcp.tools["suggest_ev_spread"]
        result = await suggest_ev_spread(
            pokemon="Incineroar",
            goals=[{"type": "maximize", "stat": "hp"}],
            tera_type="NotAType",
        )

        assert "error" in result
        assert "hint" in result


class TestFindMinimumSurvivalEVs:
    """Tests for find_minimum_survival_evs tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.ev_generator import register_ev_generator_tools

        mcp = MockFastMCP()
        register_ev_generator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_survival_evs")
    async def test_returns_survival_evs(self, mock_find, mock_mcp):
        """Test EVs calculated."""
        mock_find.return_value = {
            "success": True,
            "evs": {"hp": 252, "spd": 252},
            "damage_range": "70-82.6%",
            "defense_stat": "spd",
            "total_defensive_evs": 504,
        }

        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Incineroar",
            attacker="Flutter Mane",
            move="Moonblast",
        )

        assert "error" not in result
        assert result["minimum_evs"]["hp"] == 252
        assert result["minimum_evs"]["spd"] == 252
        assert result["damage_range"] == "70-82.6%"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_survival_evs")
    async def test_includes_defense_stat_type(self, mock_find, mock_mcp):
        """Test physical/special identified."""
        mock_find.return_value = {
            "success": True,
            "evs": {"hp": 252, "spd": 100},
            "damage_range": "75-89%",
            "defense_stat": "spd",
            "total_defensive_evs": 352,
        }

        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Incineroar",
            attacker="Flutter Mane",
            move="Moonblast",
        )

        assert result["defense_stat_invested"] == "spd"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_survival_evs")
    async def test_includes_total_defensive_evs(self, mock_find, mock_mcp):
        """Test sum of HP + Def."""
        mock_find.return_value = {
            "success": True,
            "evs": {"hp": 252, "spd": 252},
            "damage_range": "70-82.6%",
            "defense_stat": "spd",
            "total_defensive_evs": 504,
        }

        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Incineroar",
            attacker="Flutter Mane",
            move="Moonblast",
        )

        assert result["total_defensive_evs"] == 504

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_survival_evs")
    async def test_already_survives_with_zero(self, mock_find, mock_mcp):
        """Test no EVs needed."""
        mock_find.return_value = {
            "success": True,
            "evs": {"hp": 0, "def": 0, "spd": 0},
            "damage_range": "20-25%",
            "defense_stat": "def",
            "total_defensive_evs": 0,
        }

        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Incineroar",
            attacker="Amoonguss",
            move="Pollen Puff",
        )

        assert result["total_defensive_evs"] == 0

    @pytest.mark.asyncio
    async def test_invalid_pokemon_returns_error(self, mock_mcp):
        """Test bad Pokemon name returns error."""
        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="NotAPokemon",
            attacker="Flutter Mane",
            move="Moonblast",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_attacker_returns_error(self, mock_mcp):
        """Test bad attacker name returns error."""
        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Incineroar",
            attacker="NotAPokemon",
            move="Moonblast",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_nature_returns_error(self, mock_mcp):
        """Test bad nature returns error."""
        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Incineroar",
            attacker="Flutter Mane",
            move="Moonblast",
            pokemon_nature="NotANature",
        )

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_survival_evs")
    async def test_cannot_survive_returns_error(self, mock_find, mock_mcp):
        """Test impossible survival returns error."""
        mock_find.return_value = {
            "success": False,
            "error": "Cannot survive this attack even with max investment",
        }

        find_minimum_survival_evs = mock_mcp.tools["find_minimum_survival_evs"]
        result = await find_minimum_survival_evs(
            pokemon="Flutter Mane",
            attacker="Urshifu-Rapid-Strike",
            move="Surging Strikes",
        )

        assert "error" in result
        assert "hint" in result


class TestFindMinimumOHKOEVs:
    """Tests for find_minimum_ohko_evs tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.ev_generator import register_ev_generator_tools

        mcp = MockFastMCP()
        register_ev_generator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_ohko_evs")
    async def test_returns_ohko_evs(self, mock_find, mock_mcp):
        """Test EVs calculated."""
        mock_find.return_value = {
            "success": True,
            "evs": {"spa": 252},
            "damage_range": "105-124%",
            "guaranteed_ohko": True,
            "attack_stat": "spa",
        }

        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="Flutter Mane",
            defender="Incineroar",
            move="Moonblast",
        )

        assert "error" not in result
        assert result["minimum_evs"]["spa"] == 252
        assert result["guaranteed_ohko"] is True

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_ohko_evs")
    async def test_identifies_attack_stat(self, mock_find, mock_mcp):
        """Test physical vs Special identified."""
        mock_find.return_value = {
            "success": True,
            "evs": {"atk": 252},
            "damage_range": "110-130%",
            "guaranteed_ohko": True,
            "attack_stat": "atk",
        }

        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="Urshifu-Rapid-Strike",
            defender="Incineroar",
            move="Close Combat",
            pokemon_nature="Adamant",
        )

        assert result["attack_stat_invested"] == "atk"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_ohko_evs")
    async def test_ohko_with_zero_evs(self, mock_find, mock_mcp):
        """Test already OHKOs without investment."""
        mock_find.return_value = {
            "success": True,
            "evs": {"spa": 0},
            "damage_range": "120-142%",
            "guaranteed_ohko": True,
            "attack_stat": "spa",
        }

        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="Flutter Mane",
            defender="Amoonguss",
            move="Moonblast",
        )

        assert result["minimum_evs"]["spa"] == 0

    @pytest.mark.asyncio
    async def test_invalid_pokemon_returns_error(self, mock_mcp):
        """Test bad Pokemon returns error."""
        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="NotAPokemon",
            defender="Incineroar",
            move="Moonblast",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_defender_returns_error(self, mock_mcp):
        """Test bad defender returns error."""
        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="Flutter Mane",
            defender="NotAPokemon",
            move="Moonblast",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_nature_returns_error(self, mock_mcp):
        """Test bad nature returns error."""
        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="Flutter Mane",
            defender="Incineroar",
            move="Moonblast",
            pokemon_nature="NotANature",
        )

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_ohko_evs")
    async def test_cannot_ohko_returns_error(self, mock_find, mock_mcp):
        """Test impossible OHKO returns error."""
        mock_find.return_value = {
            "success": False,
            "error": "Cannot OHKO even with max investment",
            "max_damage": "85-100%",
        }

        find_minimum_ohko_evs = mock_mcp.tools["find_minimum_ohko_evs"]
        result = await find_minimum_ohko_evs(
            pokemon="Amoonguss",
            defender="Incineroar",
            move="Pollen Puff",
        )

        assert "error" in result
        assert "hint" in result


class TestFindSpeedEVs:
    """Tests for find_speed_evs tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.ev_generator import register_ev_generator_tools

        mcp = MockFastMCP()
        register_ev_generator_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_outspeed")
    async def test_returns_outspeed_evs(self, mock_find, mock_mcp):
        """Test outspeed EVs found."""
        mock_find.return_value = {
            "success": True,
            "evs": 116,
            "speed": 91,
            "target_speed": 90,
            "margin": 1,
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Incineroar",
            target="Amoonguss",
            goal_type="outspeed",
        )

        assert "error" not in result
        assert result["speed_evs_needed"] == 116
        assert result["resulting_speed"] == 91
        assert result["target_speed"] == 90

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_underspeed")
    async def test_returns_underspeed_evs(self, mock_find, mock_mcp):
        """Test underspeed EVs found."""
        mock_find.return_value = {
            "success": True,
            "evs": 0,
            "speed": 36,
            "target_speed": 40,
            "margin": 4,
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Torkoal",
            target="Dondozo",
            goal_type="underspeed",
            pokemon_nature="Quiet",
        )

        assert "error" not in result
        assert result["goal"] == "underspeed"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_outspeed")
    async def test_includes_margin(self, mock_find, mock_mcp):
        """Test speed margin calculated."""
        mock_find.return_value = {
            "success": True,
            "evs": 116,
            "speed": 91,
            "target_speed": 90,
            "margin": 1,
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Incineroar",
            target="Amoonguss",
        )

        assert result["margin"] == 1

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_outspeed")
    async def test_already_outspeeds(self, mock_find, mock_mcp):
        """Test zero EVs needed when naturally faster."""
        mock_find.return_value = {
            "success": True,
            "evs": 0,
            "speed": 80,
            "target_speed": 31,
            "margin": 49,
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Incineroar",
            target="Dondozo",
        )

        assert result["speed_evs_needed"] == 0

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_outspeed")
    async def test_goal_type_case_insensitive(self, mock_find, mock_mcp):
        """Test OUTSPEED == outspeed."""
        mock_find.return_value = {
            "success": True,
            "evs": 116,
            "speed": 91,
            "target_speed": 90,
            "margin": 1,
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Incineroar",
            target="Amoonguss",
            goal_type="OUTSPEED",
        )

        assert "error" not in result
        mock_find.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_pokemon_returns_error(self, mock_mcp):
        """Test bad Pokemon returns error."""
        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="NotAPokemon",
            target="Amoonguss",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_target_returns_error(self, mock_mcp):
        """Test bad target returns error."""
        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Incineroar",
            target="NotAPokemon",
        )

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_outspeed")
    async def test_cannot_outspeed_returns_error(self, mock_find, mock_mcp):
        """Test impossible outspeed returns error."""
        mock_find.return_value = {
            "success": False,
            "error": "Cannot outspeed even with max investment",
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Torkoal",
            target="Flutter Mane",
        )

        assert "error" in result
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_invalid_nature_returns_error(self, mock_mcp):
        """Test bad nature returns error."""
        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Incineroar",
            target="Amoonguss",
            pokemon_nature="NotANature",
        )

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.ev_generator.find_speed_evs_to_underspeed")
    async def test_cannot_underspeed_returns_error(self, mock_find, mock_mcp):
        """Test impossible underspeed returns error."""
        mock_find.return_value = {
            "success": False,
            "error": "Cannot underspeed - already slower than target",
        }

        find_speed_evs = mock_mcp.tools["find_speed_evs"]
        result = await find_speed_evs(
            pokemon="Flutter Mane",
            target="Dondozo",
            goal_type="underspeed",
        )

        assert "error" in result
