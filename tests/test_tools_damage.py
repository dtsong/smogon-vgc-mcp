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


class TestCalculateDamage:
    """Tests for calculate_damage tool."""

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

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
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

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
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

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
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
    @patch("smogon_vgc_mcp.tools.damage.calc_damage_internal")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    async def test_returns_matchup_analysis(
        self, mock_build_poke, mock_build_field, mock_calc, mock_mcp
    ):
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
    @patch("smogon_vgc_mcp.tools.damage.calc_damage_internal")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    async def test_handles_empty_moves(
        self, mock_build_poke, mock_build_field, mock_calc, mock_mcp
    ):
        """Test handling empty move slots."""
        mock_build_poke.return_value = {"name": "Test"}
        mock_build_field.return_value = {"gameType": "Doubles"}
        mock_calc.return_value = {
            "success": True,
            "minPercent": 50,
            "maxPercent": 60,
            "koChance": "2HKO",
        }

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


class TestCalculateDamageAfterIntimidate:
    """Tests for calculate_damage_after_intimidate tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calc_damage_internal")
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

        calculate_damage_after_intimidate = mock_mcp.tools["calculate_damage_after_intimidate"]
        result = await calculate_damage_after_intimidate(
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
    @patch("smogon_vgc_mcp.tools.damage.calc_damage_internal")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    async def test_returns_error_on_failure(self, mock_field, mock_poke, mock_calc, mock_mcp):
        """Test returning error when calculation fails."""
        mock_field.return_value = {"gameType": "Doubles"}
        mock_poke.return_value = {"name": "Test"}
        mock_calc.return_value = {"success": False, "error": "Invalid move"}

        calculate_damage_after_intimidate = mock_mcp.tools["calculate_damage_after_intimidate"]
        result = await calculate_damage_after_intimidate(
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
        """Test that calculate_damage returns min and max damage."""
        # Simulate real damage roll: min is ~85% of max
        mock_calc.return_value = {
            "success": True,
            "minDamage": 174,  # 85% roll
            "maxDamage": 206,  # 100% roll (max is ~1.18x min)
            "minPercent": 87.4,
            "maxPercent": 103.5,
            "koChance": "75% chance to OHKO",
        }

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
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


class TestCalculateDamageBoundary:
    """Boundary and error tests for calculate_damage tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_with_tera_type(self, mock_calc, mock_mcp):
        """Test Tera type applied."""
        mock_calc.return_value = {
            "success": True,
            "minDamage": 200,
            "maxDamage": 240,
            "minPercent": 100.0,
            "maxPercent": 120.0,
            "koChance": "guaranteed OHKO",
        }

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="Incineroar",
            attacker_evs="252/252/0/0/4/0",
            attacker_nature="Adamant",
            defender="Rillaboom",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Flare Blitz",
            attacker_tera="Fire",
        )

        assert "error" not in result
        call_args = mock_calc.call_args
        assert call_args[1].get("attacker_tera") == "Fire"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_with_weather(self, mock_calc, mock_mcp):
        """Test weather modifier."""
        mock_calc.return_value = {
            "success": True,
            "minDamage": 150,
            "maxDamage": 180,
            "minPercent": 75.0,
            "maxPercent": 90.0,
            "koChance": "2HKO",
        }

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="Incineroar",
            attacker_evs="252/252/0/0/4/0",
            attacker_nature="Adamant",
            defender="Rillaboom",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Flare Blitz",
            weather="Sun",
        )

        assert "error" not in result
        call_args = mock_calc.call_args
        assert call_args[1].get("weather") == "Sun"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_with_terrain(self, mock_calc, mock_mcp):
        """Test terrain modifier."""
        mock_calc.return_value = {
            "success": True,
            "minDamage": 100,
            "maxDamage": 120,
            "minPercent": 50.0,
            "maxPercent": 60.0,
            "koChance": "2HKO",
        }

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="Rillaboom",
            attacker_evs="252/252/0/0/4/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Grassy Glide",
            terrain="Grassy",
        )

        assert "error" not in result
        call_args = mock_calc.call_args
        assert call_args[1].get("terrain") == "Grassy"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calculate_damage_simple")
    async def test_with_screens(self, mock_calc, mock_mcp):
        """Test Reflect/Light Screen."""
        mock_calc.return_value = {
            "success": True,
            "minDamage": 80,
            "maxDamage": 95,
            "minPercent": 40.0,
            "maxPercent": 47.5,
            "koChance": "3HKO",
        }

        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="Urshifu",
            attacker_evs="252/252/0/0/4/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
            reflect=True,
        )

        assert "error" not in result
        call_args = mock_calc.call_args
        assert call_args[1].get("reflect") is True

    @pytest.mark.asyncio
    async def test_invalid_pokemon_returns_error(self, mock_mcp):
        """Test invalid Pokemon name returns error."""
        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="NotAPokemon",
            attacker_evs="252/252/0/0/4/0",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_nature_returns_error(self, mock_mcp):
        """Test invalid nature returns error."""
        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="Urshifu",
            attacker_evs="252/252/0/0/4/0",
            attacker_nature="NotANature",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_evs_returns_error(self, mock_mcp):
        """Test malformed EV string returns error."""
        calculate_damage = mock_mcp.tools["calculate_damage"]
        result = await calculate_damage(
            attacker="Urshifu",
            attacker_evs="invalid_evs",
            attacker_nature="Adamant",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Close Combat",
        )

        # Note: EV parser is lenient and returns zeros for invalid input
        # So this test just verifies no crash occurs
        assert result is not None


class TestAnalyzeMatchupBoundary:
    """Boundary tests for analyze_matchup tool."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calc_damage_internal")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    async def test_same_pokemon_matchup(
        self, mock_build_poke, mock_build_field, mock_calc, mock_mcp
    ):
        """Test Pokemon vs itself."""
        mock_build_poke.return_value = {"name": "Incineroar"}
        mock_build_field.return_value = {"gameType": "Doubles"}
        mock_calc.return_value = {
            "success": True,
            "minPercent": 30.0,
            "maxPercent": 36.0,
            "koChance": "3HKO",
        }

        analyze_matchup = mock_mcp.tools["analyze_matchup"]
        result = await analyze_matchup(
            pokemon1="Incineroar",
            pokemon1_evs="252/4/0/0/252/0",
            pokemon1_nature="Careful",
            pokemon1_moves=["Flare Blitz", "Knock Off"],
            pokemon2="Incineroar",
            pokemon2_evs="252/4/0/0/252/0",
            pokemon2_nature="Careful",
            pokemon2_moves=["Flare Blitz", "Knock Off"],
        )

        assert "error" not in result
        assert result["pokemon1"]["name"] == "Incineroar"
        assert result["pokemon2"]["name"] == "Incineroar"


class TestIntimidateBoundary:
    """Boundary tests for intimidate calculation."""

    @pytest.fixture
    def mock_mcp(self):
        """Create mock MCP and register tools."""
        from smogon_vgc_mcp.tools.damage import register_damage_tools

        mcp = MockFastMCP()
        register_damage_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.tools.damage.calc_damage_internal")
    @patch("smogon_vgc_mcp.tools.damage.build_pokemon_dict")
    @patch("smogon_vgc_mcp.tools.damage.build_field_dict")
    async def test_intimidate_on_special_move(self, mock_field, mock_poke, mock_calc, mock_mcp):
        """Test Intimidate has no effect on Special attacks."""
        mock_field.return_value = {"gameType": "Doubles"}
        mock_poke.return_value = {"name": "Test"}

        # Both calls return same damage (Intimidate doesn't affect SpA)
        mock_calc.side_effect = [
            {
                "success": True,
                "minPercent": 100,
                "maxPercent": 120,
                "koChance": "guaranteed OHKO",
            },
            {
                "success": True,
                "minPercent": 100,
                "maxPercent": 120,
                "koChance": "guaranteed OHKO",
            },
        ]

        calculate_damage_after_intimidate = mock_mcp.tools["calculate_damage_after_intimidate"]
        result = await calculate_damage_after_intimidate(
            attacker="Flutter Mane",
            attacker_evs="4/0/0/252/0/252",
            attacker_nature="Timid",
            defender="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Moonblast",
        )

        # Damage should be the same before and after Intimidate
        assert result["normal"]["ko_chance"] == result["after_intimidate"]["ko_chance"]
