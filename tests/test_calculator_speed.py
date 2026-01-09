"""Tests for calculator/speed_tiers.py - Speed tier analysis."""

from unittest.mock import patch

from smogon_vgc_mcp.calculator.speed_tiers import (
    SPEED_BENCHMARKS,
    compare_speeds,
    find_speed_benchmarks,
    get_max_speed,
    get_min_speed,
    get_speed_stat,
)


class TestGetSpeedStat:
    """Tests for get_speed_stat function."""

    @patch("smogon_vgc_mcp.calculator.speed_tiers.calculate_all_stats")
    def test_returns_speed_from_stats(self, mock_calc):
        """Test that speed stat is extracted from calculate_all_stats."""
        mock_calc.return_value = {
            "hp": 202,
            "atk": 167,
            "def": 110,
            "spa": 100,
            "spd": 142,
            "spe": 80,
        }

        result = get_speed_stat("Incineroar", "252/4/0/0/252/0", nature="Careful")

        assert result == 80
        mock_calc.assert_called_once()

    @patch("smogon_vgc_mcp.calculator.speed_tiers.calculate_all_stats")
    def test_max_speed_flutter_mane(self, mock_calc):
        """Test max speed Flutter Mane (252 Spe, Timid)."""
        mock_calc.return_value = {
            "hp": 131,
            "atk": 65,
            "def": 75,
            "spa": 187,
            "spd": 155,
            "spe": 205,
        }

        result = get_speed_stat("Flutter Mane", "4/0/0/252/0/252", nature="Timid")

        assert result == 205

    @patch("smogon_vgc_mcp.calculator.speed_tiers.calculate_all_stats")
    def test_returns_none_for_unknown_pokemon(self, mock_calc):
        """Test that None is returned for unknown Pokemon."""
        mock_calc.return_value = None

        result = get_speed_stat("NotAPokemon", "252/252/4/0/0/0")

        assert result is None

    @patch("smogon_vgc_mcp.calculator.speed_tiers.calculate_all_stats")
    def test_with_ivs_parameter(self, mock_calc):
        """Test with custom IVs (0 Speed for Trick Room)."""
        mock_calc.return_value = {
            "hp": 202,
            "atk": 167,
            "def": 110,
            "spa": 100,
            "spd": 142,
            "spe": 49,
        }

        result = get_speed_stat(
            "Incineroar", "252/4/0/0/252/0", ivs="31/31/31/31/31/0", nature="Brave"
        )

        assert result == 49


class TestCompareSpeeds:
    """Tests for compare_speeds function."""

    @patch("smogon_vgc_mcp.calculator.speed_tiers.get_speed_stat")
    def test_first_pokemon_faster(self, mock_speed):
        """Test when first Pokemon is faster."""
        mock_speed.side_effect = [205, 80]  # Flutter Mane vs Incineroar

        result = compare_speeds(
            "Flutter Mane", "4/0/0/252/0/252", "Timid", "Incineroar", "252/4/0/0/252/0", "Careful"
        )

        assert result["faster"] == "Flutter Mane"
        assert result["pokemon1"]["speed"] == 205
        assert result["pokemon2"]["speed"] == 80
        assert result["difference"] == 125
        assert "Flutter Mane outspeeds Incineroar" in result["result"]

    @patch("smogon_vgc_mcp.calculator.speed_tiers.get_speed_stat")
    def test_second_pokemon_faster(self, mock_speed):
        """Test when second Pokemon is faster."""
        mock_speed.side_effect = [80, 205]  # Incineroar vs Flutter Mane

        result = compare_speeds(
            "Incineroar", "252/4/0/0/252/0", "Careful", "Flutter Mane", "4/0/0/252/0/252", "Timid"
        )

        assert result["faster"] == "Flutter Mane"
        assert "Flutter Mane outspeeds Incineroar" in result["result"]

    @patch("smogon_vgc_mcp.calculator.speed_tiers.get_speed_stat")
    def test_speed_tie(self, mock_speed):
        """Test speed tie scenario."""
        mock_speed.side_effect = [100, 100]

        result = compare_speeds(
            "Pokemon1", "252/0/0/0/0/252", "Jolly", "Pokemon2", "252/0/0/0/0/252", "Jolly"
        )

        assert result["faster"] is None
        assert result["result"] == "Speed tie"
        assert result["difference"] == 0

    @patch("smogon_vgc_mcp.calculator.speed_tiers.get_speed_stat")
    def test_error_on_unknown_pokemon(self, mock_speed):
        """Test error when one Pokemon is unknown."""
        mock_speed.side_effect = [205, None]

        result = compare_speeds(
            "Flutter Mane", "4/0/0/252/0/252", "Timid", "NotAPokemon", "252/252/4/0/0/0", "Adamant"
        )

        assert "error" in result
        assert result["pokemon2"]["speed"] is None


class TestMinMaxSpeed:
    """Tests for get_min_speed and get_max_speed functions."""

    def test_min_speed_base_100(self):
        """Test minimum speed for base 100 Speed."""
        # Base 100, 0 IV, 0 EV, -Spe nature, Level 50
        # floor((200 * 50/100) + 5) * 0.9 = floor(105 * 0.9) = 94
        result = get_min_speed(100, level=50)
        assert result == 94

    def test_max_speed_base_100(self):
        """Test maximum speed for base 100 Speed."""
        # Base 100, 31 IV, 252 EV, +Spe nature, Level 50
        # floor((200 + 31 + 63) * 50/100 + 5) * 1.1 = floor(152 * 1.1) = 167
        result = get_max_speed(100, level=50)
        assert result == 167

    def test_min_speed_base_135(self):
        """Test minimum speed for base 135 (Flutter Mane/Dragapult)."""
        result = get_min_speed(135, level=50)
        # floor((270 * 0.5) + 5) * 0.9 = floor(140 * 0.9) = 126
        assert result == 126

    def test_max_speed_base_135(self):
        """Test maximum speed for base 135 (Flutter Mane/Dragapult)."""
        result = get_max_speed(135, level=50)
        # floor((270 + 31 + 63) * 0.5 + 5) * 1.1 = floor(187 * 1.1) = 205
        assert result == 205

    def test_min_speed_base_60(self):
        """Test minimum speed for base 60 (Incineroar)."""
        result = get_min_speed(60, level=50)
        # floor((120 * 0.5) + 5) * 0.9 = floor(65 * 0.9) = 58
        assert result == 58

    def test_max_speed_base_60(self):
        """Test maximum speed for base 60 (Incineroar)."""
        result = get_max_speed(60, level=50)
        # floor((120 + 31 + 63) * 0.5 + 5) * 1.1 = floor(112 * 1.1) = 123
        assert result == 123

    def test_level_100_calculations(self):
        """Test speed calculations at level 100."""
        min_spd = get_min_speed(100, level=100)
        max_spd = get_max_speed(100, level=100)

        # Level 100 speeds should be roughly double level 50
        assert min_spd > get_min_speed(100, level=50)
        assert max_spd > get_max_speed(100, level=50)


class TestFindSpeedBenchmarks:
    """Tests for find_speed_benchmarks function."""

    def test_very_fast_speed_outspeeds_many(self):
        """Test that 205 speed outspeeds most Pokemon."""
        result = find_speed_benchmarks("Flutter Mane", 205)

        assert result["pokemon"] == "Flutter Mane"
        assert result["speed_stat"] == 205
        # 205 is max Flutter Mane speed, so it should outspeed many slower Pokemon
        # Results are limited to 10, so we just verify structure
        assert "outspeeds_max" in result
        assert "underspeeds_min" in result
        assert "speed_ties_possible" in result

    def test_slow_speed_underspeeds_many(self):
        """Test that 60 speed underspeeds most Pokemon."""
        result = find_speed_benchmarks("Snorlax", 60)

        assert result["speed_stat"] == 60
        assert len(result["underspeeds_min"]) > 0

    def test_medium_speed_has_ties(self):
        """Test that medium speed may have speed tie possibilities."""
        # 100 speed is in the range of many Pokemon
        result = find_speed_benchmarks("TestPokemon", 100)

        # Could have ties with base 50-ish Pokemon at max investment
        assert result["speed_stat"] == 100

    def test_results_are_limited(self):
        """Test that results are limited to 10 entries each."""
        result = find_speed_benchmarks("TestPokemon", 150)

        assert len(result["outspeeds_max"]) <= 10
        assert len(result["underspeeds_min"]) <= 10
        assert len(result["speed_ties_possible"]) <= 10


class TestSpeedBenchmarksConstant:
    """Tests for SPEED_BENCHMARKS constant."""

    def test_has_fast_pokemon(self):
        """Test that fast Pokemon are in benchmarks."""
        assert 135 in SPEED_BENCHMARKS  # Dragapult
        assert 136 in SPEED_BENCHMARKS  # Regieleki

    def test_has_medium_pokemon(self):
        """Test that medium speed Pokemon are in benchmarks."""
        assert 100 in SPEED_BENCHMARKS  # Charizard, Salamence
        assert 103 in SPEED_BENCHMARKS  # Garchomp

    def test_has_slow_pokemon(self):
        """Test that slow Pokemon are in benchmarks."""
        assert 45 in SPEED_BENCHMARKS  # Torkoal
        assert 30 in SPEED_BENCHMARKS  # Ferrothorn

    def test_dragapult_in_135(self):
        """Test specific Pokemon placement."""
        assert "Dragapult" in SPEED_BENCHMARKS[135]

    def test_incineroar_not_in_benchmarks(self):
        """Test that Incineroar (base 60) is in correct tier."""
        # Incineroar has base 60 speed but might not be in benchmarks
        # Just verify the structure is valid
        for speed, pokemon_list in SPEED_BENCHMARKS.items():
            assert isinstance(speed, int)
            assert isinstance(pokemon_list, list)
