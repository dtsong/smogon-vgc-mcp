"""Tests for tools/damage.py - Damage calculation tools."""

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


class TestCalcDamage:
    """Tests for calc_damage tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_returns_damage_calc(self, mock_calc, mock_mcp):
        """Test returning damage calculation."""
        mock_calc.return_value = {
            "success": True,
            "description": "252 Atk Urshifu Close Combat vs. 252 HP / 84 Def Incineroar",
            "minDamage": 174,
            "maxDamage": 206,
            "minPercent": 87.4,
            "maxPercent": 103.5,
            "koChance": "75% chance to OHKO",
            "defenderMaxHP": 199,
            "attacker": "Urshifu",
            "defender": "Incineroar",
            "move": "Close Combat",
        }

        calc_damage = mock_mcp.tools["calc_damage"]
        result = await calc_damage(
            attacker="Urshifu",
            attacker_evs="0/252/0/0/4/252",
            attacker_nature="Jolly",
            defender="Incineroar",
            defender_evs="252/4/84/0/92/76",
            defender_nature="Careful",
            move="Close Combat",
        )

        assert result["damage_range"] == "174-206"
        assert result["percent_range"] == "87.4-103.5%"
        assert result["ko_chance"] == "75% chance to OHKO"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_returns_error_on_failure(self, mock_calc, mock_mcp):
        """Test returning error when calculation fails."""
        mock_calc.return_value = {
            "success": False,
            "error": "Invalid Pokemon name",
        }

        calc_damage = mock_mcp.tools["calc_damage"]
        result = await calc_damage(
            attacker="NotAPokemon",
            attacker_evs="252/252/4/0/0/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
        )

        assert "error" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_handles_stat_boosts(self, mock_calc, mock_mcp):
        """Test handling stat boosts."""
        mock_calc.return_value = {
            "success": True,
            "minDamage": 100,
            "maxDamage": 120,
            "minPercent": 50.0,
            "maxPercent": 60.0,
            "koChance": "2HKO",
        }

        calc_damage = mock_mcp.tools["calc_damage"]
        result = await calc_damage(
            attacker="Urshifu",
            attacker_evs="252/252/4/0/0/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
            attacker_atk_boost=1,
            defender_def_boost=-1,
        )

        # Verify boosts were passed to calculator
        call_args = mock_calc.call_args
        assert call_args[1].get("attacker_boosts") == {"atk": 1, "spa": 0}
        assert call_args[1].get("defender_boosts") == {"def": -1, "spd": 0}


class TestAnalyzeMatchup:
    """Tests for analyze_matchup tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    async def test_returns_matchup_analysis(self, mock_build_poke, mock_build_field, mock_calc, mock_mcp):
        """Test returning matchup analysis."""
        mock_build_poke.return_value = {"name": "Test"}
        mock_build_field.return_value = {"gameType": "Doubles"}

        mock_calc.return_value = {
            "success": True,
            "minPercent": 50.0,
            "maxPercent": 60.0,
            "koChance": "2HKO",
        }

        analyze_matchup = mock_mcp.tools["analyze_matchup"]
        result = await analyze_matchup(
            pokemon1="Urshifu",
            pokemon1_evs="0/252/0/0/4/252",
            pokemon1_nature="Jolly",
            pokemon1_moves=["Close Combat", "Surging Strikes"],
            pokemon2="Incineroar",
            pokemon2_evs="252/4/0/0/252/0",
            pokemon2_nature="Careful",
            pokemon2_moves=["Flare Blitz", "Knock Off"],
        )

        assert "pokemon1" in result
        assert "pokemon2" in result
        assert "summary" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    async def test_handles_empty_moves(self, mock_build_poke, mock_build_field, mock_calc, mock_mcp):
        """Test handling empty move slots."""
        mock_build_poke.return_value = {"name": "Test"}
        mock_build_field.return_value = {"gameType": "Doubles"}
        mock_calc.return_value = {"success": True, "minPercent": 50, "maxPercent": 60, "koChance": "2HKO"}

        analyze_matchup = mock_mcp.tools["analyze_matchup"]
        result = await analyze_matchup(
            pokemon1="Urshifu",
            pokemon1_evs="252/252/4/0/0/0",
            pokemon1_nature="Adamant",
            pokemon1_moves=["Close Combat", "", None],  # Some empty moves
            pokemon2="Incineroar",
            pokemon2_evs="252/4/0/0/252/0",
            pokemon2_nature="Careful",
            pokemon2_moves=["Flare Blitz"],
        )

        # Should not crash with empty moves
        assert "pokemon1" in result


class TestCheckOhko:
    """Tests for check_ohko tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    async def test_finds_ohko_threshold(self, mock_field, mock_poke, mock_calc, mock_mcp):
        """Test finding OHKO EV threshold."""
        mock_field.return_value = {"gameType": "Doubles"}
        mock_poke.return_value = {"name": "Test"}

        # Simulate increasing damage with more EVs
        def damage_by_evs(*args, **kwargs):
            # Return increasing damage based on mock call count
            ev_values = {
                0: {"success": True, "minPercent": 70, "maxPercent": 85},
                52: {"success": True, "minPercent": 80, "maxPercent": 95},
                100: {"success": True, "minPercent": 90, "maxPercent": 105},
                156: {"success": True, "minPercent": 100, "maxPercent": 115},
                196: {"success": True, "minPercent": 105, "maxPercent": 120},
                252: {"success": True, "minPercent": 110, "maxPercent": 130},
            }
            # Return some default for the test
            return {"success": True, "minPercent": 85, "maxPercent": 100}

        mock_calc.side_effect = damage_by_evs

        check_ohko = mock_mcp.tools["check_ohko"]
        result = await check_ohko(
            attacker="Urshifu",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
        )

        assert "attacker" in result
        assert "defender" in result
        assert "ev_investments" in result

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    async def test_reports_when_cannot_ohko(self, mock_field, mock_poke, mock_calc, mock_mcp):
        """Test reporting when OHKO is impossible."""
        mock_field.return_value = {"gameType": "Doubles"}
        mock_poke.return_value = {"name": "Test"}

        # Never reaches OHKO threshold
        mock_calc.return_value = {
            "success": True,
            "minPercent": 40,
            "maxPercent": 50,
        }

        check_ohko = mock_mcp.tools["check_ohko"]
        result = await check_ohko(
            attacker="Pikachu",
            attacker_nature="Modest",
            defender="Blissey",
            defender_evs="252/4/252/0/0/0",
            defender_nature="Bold",
            move="Thunderbolt",
        )

        assert result["can_ohko_with_max_evs"] is False


class TestCalcDamageAfterIntimidate:
    """Tests for calc_damage_after_intimidate tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    async def test_compares_normal_vs_intimidated(self, mock_field, mock_poke, mock_calc, mock_mcp):
        """Test comparing normal vs intimidated damage."""
        mock_field.return_value = {"gameType": "Doubles"}
        mock_poke.return_value = {"name": "Test"}

        # First call is normal, second is intimidated
        mock_calc.side_effect = [
            {
                "success": True,
                "minPercent": 100,
                "maxPercent": 120,
                "koChance": "guaranteed OHKO",
            },
            {
                "success": True,
                "minPercent": 67,
                "maxPercent": 80,
                "koChance": "2HKO",
            },
        ]

        calc_damage_after_intimidate = mock_mcp.tools["calc_damage_after_intimidate"]
        result = await calc_damage_after_intimidate(
            attacker="Urshifu",
            attacker_evs="0/252/0/0/4/252",
            attacker_nature="Jolly",
            defender="Incineroar",
            defender_evs="252/4/84/0/92/76",
            defender_nature="Careful",
            move="Close Combat",
        )

        assert "normal" in result
        assert "after_intimidate" in result
        assert "damage_reduction" in result
        assert result["normal"]["ko_chance"] == "guaranteed OHKO"
        assert result["after_intimidate"]["ko_chance"] == "2HKO"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    async def test_returns_error_on_failure(self, mock_field, mock_poke, mock_calc, mock_mcp):
        """Test returning error when calculation fails."""
        mock_field.return_value = {"gameType": "Doubles"}
        mock_poke.return_value = {"name": "Test"}
        mock_calc.return_value = {"success": False, "error": "Invalid move"}

        calc_damage_after_intimidate = mock_mcp.tools["calc_damage_after_intimidate"]
        result = await calc_damage_after_intimidate(
            attacker="Urshifu",
            attacker_evs="252/252/4/0/0/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="InvalidMove",
        )

        assert "error" in result


class TestDamageRangesInTools:
    """Test that damage tools handle damage ranges correctly.

    Pokemon damage calculations always produce a range due to the
    85-100% random damage roll (16 possible values).
    """

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_damage_tool_returns_range(self, mock_calc, mock_mcp):
        """Test that calc_damage returns min and max damage."""
        # Simulate real damage roll: min is ~85% of max
        mock_calc.return_value = {
            "success": True,
            "minDamage": 174,  # 85% roll
            "maxDamage": 206,  # 100% roll (max is ~1.18x min)
            "minPercent": 87.4,
            "maxPercent": 103.5,
            "koChance": "75% chance to OHKO",
        }

        calc_damage = mock_mcp.tools["calc_damage"]
        result = await calc_damage(
            attacker="Urshifu",
            attacker_evs="252/252/4/0/0/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
        )

        # Verify range format
        assert "-" in result["damage_range"]
        assert "-" in result["percent_range"]

        # Parse and verify the range makes sense
        min_dmg, max_dmg = result["damage_range"].split("-")
        assert int(max_dmg) > int(min_dmg)
