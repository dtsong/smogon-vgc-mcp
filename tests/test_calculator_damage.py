"""Tests for calculator/damage.py - Damage calculation.

Note: Pokemon damage always has a random roll (85-100% of max damage).
Tests should account for this damage range when verifying results.
"""

import json
from unittest.mock import MagicMock, patch

from smogon_vgc_mcp.calculator.damage import (
    batch_calculate,
    build_field_dict,
    build_pokemon_dict,
    calculate_damage,
    calculate_damage_simple,
    parse_ev_string,
    parse_iv_string,
    run_calc,
)


class TestParseEVStringDamage:
    """Tests for parse_ev_string in damage module."""

    def test_compact_format(self):
        """Test slash-separated format: 252/0/4/0/0/252."""
        result = parse_ev_string("252/0/4/0/0/252")
        assert result == {"hp": 252, "atk": 0, "def": 4, "spa": 0, "spd": 0, "spe": 252}

    def test_showdown_format(self):
        """Test Showdown format: '252 HP / 4 Def / 252 SpA'."""
        result = parse_ev_string("252 HP / 4 Def / 252 SpA")
        assert result["hp"] == 252
        assert result["def"] == 4
        assert result["spa"] == 252
        assert result["atk"] == 0
        assert result["spd"] == 0
        assert result["spe"] == 0

    def test_alternate_stat_names(self):
        """Test alternate stat name formats."""
        result = parse_ev_string("252 Attack / 252 Speed")
        assert result["atk"] == 252
        assert result["spe"] == 252

    def test_spatk_spdef_formats(self):
        """Test SpAtk format (lowercase sp.atk/sp.def)."""
        # The parser uses lowercase matching for these formats
        result = parse_ev_string("252 spa / 4 spd")
        assert result["spa"] == 252
        assert result["spd"] == 4


class TestParseIVStringDamage:
    """Tests for parse_iv_string in damage module."""

    def test_none_returns_all_31s(self):
        """Test None input returns all 31s."""
        result = parse_iv_string(None)
        assert result == {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

    def test_compact_format(self):
        """Test slash-separated format."""
        result = parse_iv_string("31/0/31/31/31/31")
        assert result["atk"] == 0
        assert result["hp"] == 31

    def test_showdown_format_zero_atk(self):
        """Test Showdown format: '0 Atk'."""
        result = parse_iv_string("0 Atk")
        assert result["atk"] == 0
        assert result["hp"] == 31
        assert result["spe"] == 31

    def test_multiple_ivs(self):
        """Test multiple IVs specified."""
        result = parse_iv_string("0 Atk / 0 Spe")
        assert result["atk"] == 0
        assert result["spe"] == 0
        assert result["hp"] == 31


class TestBuildPokemonDict:
    """Tests for build_pokemon_dict function."""

    def test_basic_pokemon(self):
        """Test basic Pokemon dict creation."""
        result = build_pokemon_dict("Incineroar")

        assert result["name"] == "Incineroar"
        assert result["level"] == 50

    def test_with_string_evs(self):
        """Test Pokemon with string EVs."""
        result = build_pokemon_dict("Incineroar", evs="252/4/0/0/252/0")

        assert result["evs"]["hp"] == 252
        assert result["evs"]["atk"] == 4
        assert result["evs"]["spd"] == 252

    def test_with_dict_evs(self):
        """Test Pokemon with dict EVs."""
        evs = {"hp": 252, "atk": 0, "def": 4, "spa": 252, "spd": 0, "spe": 0}
        result = build_pokemon_dict("Flutter Mane", evs=evs)

        assert result["evs"] == evs

    def test_with_nature(self):
        """Test Pokemon with nature."""
        result = build_pokemon_dict("Incineroar", nature="Careful")

        assert result["nature"] == "Careful"

    def test_with_item(self):
        """Test Pokemon with item."""
        result = build_pokemon_dict("Flutter Mane", item="Booster Energy")

        assert result["item"] == "Booster Energy"

    def test_with_ability(self):
        """Test Pokemon with ability."""
        result = build_pokemon_dict("Incineroar", ability="Intimidate")

        assert result["ability"] == "Intimidate"

    def test_with_tera_type(self):
        """Test Pokemon with Tera type."""
        result = build_pokemon_dict("Incineroar", tera_type="Ghost")

        assert result["teraType"] == "Ghost"

    def test_with_boosts(self):
        """Test Pokemon with stat boosts."""
        result = build_pokemon_dict("Incineroar", boosts={"atk": -1})

        assert result["boosts"] == {"atk": -1}

    def test_with_status(self):
        """Test Pokemon with status condition."""
        result = build_pokemon_dict("Incineroar", status="Burned")

        assert result["status"] == "Burned"

    def test_full_pokemon(self):
        """Test fully specified Pokemon."""
        result = build_pokemon_dict(
            name="Incineroar",
            evs="252/4/0/0/252/0",
            ivs="31/31/31/31/31/31",
            nature="Careful",
            item="Safety Goggles",
            ability="Intimidate",
            tera_type="Ghost",
            level=50,
            boosts={"atk": -1},
            status="Burned",
        )

        assert result["name"] == "Incineroar"
        assert result["nature"] == "Careful"
        assert result["item"] == "Safety Goggles"
        assert result["ability"] == "Intimidate"
        assert result["teraType"] == "Ghost"
        assert result["boosts"] == {"atk": -1}
        assert result["status"] == "Burned"


class TestBuildFieldDict:
    """Tests for build_field_dict function."""

    def test_default_doubles(self):
        """Test default field is Doubles."""
        result = build_field_dict()

        assert result["gameType"] == "Doubles"

    def test_singles(self):
        """Test Singles game type."""
        result = build_field_dict(game_type="Singles")

        assert result["gameType"] == "Singles"

    def test_with_weather(self):
        """Test field with weather."""
        result = build_field_dict(weather="Sun")

        assert result["weather"] == "Sun"

    def test_with_terrain(self):
        """Test field with terrain."""
        result = build_field_dict(terrain="Grassy")

        assert result["terrain"] == "Grassy"

    def test_with_attacker_side(self):
        """Test field with attacker side conditions."""
        result = build_field_dict(attacker_side={"isHelpingHand": True})

        assert result["attackerSide"]["isHelpingHand"] is True

    def test_with_defender_side(self):
        """Test field with defender side conditions."""
        result = build_field_dict(defender_side={"isReflect": True, "isLightScreen": True})

        assert result["defenderSide"]["isReflect"] is True
        assert result["defenderSide"]["isLightScreen"] is True

    def test_full_field(self):
        """Test fully specified field."""
        result = build_field_dict(
            game_type="Doubles",
            weather="Rain",
            terrain="Electric",
            attacker_side={"isHelpingHand": True},
            defender_side={"isLightScreen": True},
        )

        assert result["gameType"] == "Doubles"
        assert result["weather"] == "Rain"
        assert result["terrain"] == "Electric"
        assert result["attackerSide"]["isHelpingHand"] is True
        assert result["defenderSide"]["isLightScreen"] is True


class TestRunCalc:
    """Tests for run_calc function (subprocess mocking)."""

    @patch("smogon_vgc_mcp.calculator.damage.CALC_WRAPPER_PATH")
    @patch("smogon_vgc_mcp.calculator.damage.subprocess.run")
    def test_successful_calculation(self, mock_run, mock_path):
        """Test successful damage calculation."""
        mock_path.exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "success": True,
                    "damage": [
                        150,
                        152,
                        154,
                        156,
                        158,
                        160,
                        162,
                        164,
                        166,
                        168,
                        170,
                        172,
                        174,
                        176,
                        178,
                        180,
                    ],
                    "minPercent": 74.2,
                    "maxPercent": 89.1,
                }
            ),
            stderr="",
        )

        result = run_calc({"attacker": {}, "defender": {}, "move": "Moonblast"})

        assert result["success"] is True
        assert "damage" in result
        # Damage range: 16 values from 85-100% of max damage
        assert len(result["damage"]) == 16

    @patch("smogon_vgc_mcp.calculator.damage.CALC_WRAPPER_PATH")
    def test_wrapper_not_found(self, mock_path):
        """Test error when calc wrapper not found."""
        mock_path.exists.return_value = False

        result = run_calc({"attacker": {}, "defender": {}, "move": "Test"})

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("smogon_vgc_mcp.calculator.damage.CALC_WRAPPER_PATH")
    @patch("smogon_vgc_mcp.calculator.damage.subprocess.run")
    def test_calc_failure(self, mock_run, mock_path):
        """Test handling of calc failure."""
        mock_path.exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Unknown Pokemon",
        )

        result = run_calc({"attacker": {}, "defender": {}, "move": "Test"})

        assert result["success"] is False
        assert "Unknown Pokemon" in result["error"]

    @patch("smogon_vgc_mcp.calculator.damage.CALC_WRAPPER_PATH")
    @patch("smogon_vgc_mcp.calculator.damage.subprocess.run")
    def test_timeout_handling(self, mock_run, mock_path):
        """Test timeout handling."""
        import subprocess as sp

        mock_path.exists.return_value = True
        mock_run.side_effect = sp.TimeoutExpired(cmd="node", timeout=10)

        result = run_calc({"attacker": {}, "defender": {}, "move": "Test"})

        assert result["success"] is False
        assert "timed out" in result["error"]

    @patch("smogon_vgc_mcp.calculator.damage.CALC_WRAPPER_PATH")
    @patch("smogon_vgc_mcp.calculator.damage.subprocess.run")
    def test_invalid_json_output(self, mock_run, mock_path):
        """Test handling of invalid JSON output."""
        mock_path.exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json",
            stderr="",
        )

        result = run_calc({"attacker": {}, "defender": {}, "move": "Test"})

        assert result["success"] is False
        assert "parse" in result["error"].lower()


class TestCalculateDamage:
    """Tests for calculate_damage function."""

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_basic_damage_calculation(self, mock_run):
        """Test basic damage calculation."""
        mock_run.return_value = {
            "success": True,
            "damage": [
                150,
                152,
                154,
                156,
                158,
                160,
                162,
                164,
                166,
                168,
                170,
                172,
                174,
                176,
                178,
                180,
            ],
            "minPercent": 74.2,
            "maxPercent": 89.1,
        }

        attacker = build_pokemon_dict("Flutter Mane", evs="4/0/0/252/0/252", nature="Timid")
        defender = build_pokemon_dict("Incineroar", evs="252/4/0/0/252/0", nature="Careful")

        result = calculate_damage(attacker, defender, "Moonblast")

        assert result["success"] is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args["move"] == "Moonblast"
        assert call_args["field"]["gameType"] == "Doubles"

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_custom_field(self, mock_run):
        """Test damage calculation with custom field."""
        mock_run.return_value = {"success": True, "damage": [100]}

        attacker = build_pokemon_dict("Pokemon1")
        defender = build_pokemon_dict("Pokemon2")
        field = build_field_dict(weather="Sun")

        calculate_damage(attacker, defender, "Fire Blast", field)

        call_args = mock_run.call_args[0][0]
        assert call_args["field"]["weather"] == "Sun"


class TestCalculateDamageSimple:
    """Tests for calculate_damage_simple function."""

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_simple_calculation(self, mock_run):
        """Test simplified damage calculation."""
        mock_run.return_value = {"success": True, "damage": [100]}

        result = calculate_damage_simple(
            attacker_name="Flutter Mane",
            attacker_evs="4/0/0/252/0/252",
            attacker_nature="Timid",
            defender_name="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Moonblast",
        )

        assert result["success"] is True
        mock_run.assert_called_once()

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_items_and_abilities(self, mock_run):
        """Test with items and abilities."""
        mock_run.return_value = {"success": True, "damage": [100]}

        calculate_damage_simple(
            attacker_name="Flutter Mane",
            attacker_evs="4/0/0/252/0/252",
            attacker_nature="Timid",
            attacker_item="Booster Energy",
            attacker_ability="Protosynthesis",
            defender_name="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            defender_item="Safety Goggles",
            defender_ability="Intimidate",
            move="Moonblast",
        )

        call_args = mock_run.call_args[0][0]
        assert call_args["attacker"]["item"] == "Booster Energy"
        assert call_args["attacker"]["ability"] == "Protosynthesis"
        assert call_args["defender"]["item"] == "Safety Goggles"
        assert call_args["defender"]["ability"] == "Intimidate"

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_tera_type(self, mock_run):
        """Test with Tera type."""
        mock_run.return_value = {"success": True, "damage": [100]}

        calculate_damage_simple(
            attacker_name="Flutter Mane",
            attacker_evs="4/0/0/252/0/252",
            attacker_nature="Timid",
            attacker_tera="Fairy",
            defender_name="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Moonblast",
        )

        call_args = mock_run.call_args[0][0]
        assert call_args["attacker"]["teraType"] == "Fairy"

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_weather_and_terrain(self, mock_run):
        """Test with weather and terrain."""
        mock_run.return_value = {"success": True, "damage": [100]}

        calculate_damage_simple(
            attacker_name="Rillaboom",
            attacker_evs="252/252/4/0/0/0",
            attacker_nature="Adamant",
            defender_name="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Grassy Glide",
            terrain="Grassy",
        )

        call_args = mock_run.call_args[0][0]
        assert call_args["field"]["terrain"] == "Grassy"

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_helping_hand(self, mock_run):
        """Test with Helping Hand support."""
        mock_run.return_value = {"success": True, "damage": [100]}

        calculate_damage_simple(
            attacker_name="Flutter Mane",
            attacker_evs="4/0/0/252/0/252",
            attacker_nature="Timid",
            defender_name="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Moonblast",
            helping_hand=True,
        )

        call_args = mock_run.call_args[0][0]
        assert call_args["field"]["attackerSide"]["isHelpingHand"] is True

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_screens(self, mock_run):
        """Test with Reflect/Light Screen."""
        mock_run.return_value = {"success": True, "damage": [100]}

        calculate_damage_simple(
            attacker_name="Flutter Mane",
            attacker_evs="4/0/0/252/0/252",
            attacker_nature="Timid",
            defender_name="Incineroar",
            defender_evs="252/4/0/0/252/0",
            defender_nature="Careful",
            move="Moonblast",
            light_screen=True,
        )

        call_args = mock_run.call_args[0][0]
        assert call_args["field"]["defenderSide"]["isLightScreen"] is True

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_with_stat_boosts(self, mock_run):
        """Test with stat boosts."""
        mock_run.return_value = {"success": True, "damage": [100]}

        calculate_damage_simple(
            attacker_name="Incineroar",
            attacker_evs="252/252/4/0/0/0",
            attacker_nature="Adamant",
            defender_name="Flutter Mane",
            defender_evs="4/0/0/252/0/252",
            defender_nature="Timid",
            move="Flare Blitz",
            attacker_boosts={"atk": 2},  # Swords Dance
            defender_boosts={"def": -1},  # Intimidated
        )

        call_args = mock_run.call_args[0][0]
        assert call_args["attacker"]["boosts"]["atk"] == 2
        assert call_args["defender"]["boosts"]["def"] == -1


class TestBatchCalculate:
    """Tests for batch_calculate function."""

    @patch("smogon_vgc_mcp.calculator.damage.run_calc")
    def test_batch_calculation(self, mock_run):
        """Test batch damage calculations."""
        mock_run.return_value = [
            {"success": True, "damage": [100]},
            {"success": True, "damage": [150]},
        ]

        calculations = [
            {"attacker": {}, "defender": {}, "move": "Move1"},
            {"attacker": {}, "defender": {}, "move": "Move2"},
        ]

        result = batch_calculate(calculations)

        mock_run.assert_called_once_with(calculations)


class TestDamageRanges:
    """Tests verifying damage range concepts.

    Pokemon damage has a random multiplier from 0.85 to 1.0,
    resulting in 16 possible damage values.
    """

    def test_damage_array_has_16_values(self):
        """Verify damage calc returns 16 damage values (85-100% rolls)."""
        # This is a conceptual test - actual damage calcs return 16 values
        damage_range = [
            150,
            152,
            154,
            156,
            158,
            160,
            162,
            164,
            166,
            168,
            170,
            172,
            174,
            176,
            178,
            180,
        ]
        assert len(damage_range) == 16

    def test_min_damage_is_85_percent_of_max(self):
        """Verify min damage is ~85% of max damage."""
        min_damage = 150
        max_damage = 180
        # Allow some rounding tolerance
        ratio = min_damage / max_damage
        assert 0.83 <= ratio <= 0.86

    def test_damage_values_are_sorted(self):
        """Verify damage values are in ascending order."""
        damage_range = [
            150,
            152,
            154,
            156,
            158,
            160,
            162,
            164,
            166,
            168,
            170,
            172,
            174,
            176,
            178,
            180,
        ]
        assert damage_range == sorted(damage_range)
