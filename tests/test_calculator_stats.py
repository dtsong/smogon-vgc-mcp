"""Tests for calculator/stats.py - Pokemon stat calculations."""

from unittest.mock import patch

from smogon_vgc_mcp.calculator.stats import (
    calculate_all_stats,
    calculate_hp,
    calculate_stat,
    format_stats,
    parse_ev_string,
    parse_iv_string,
)


class TestCalculateHP:
    """Tests for HP calculation formula."""

    def test_standard_hp_252_evs(self):
        """Test HP calculation with 252 EVs (common VGC spread)."""
        # Incineroar: base 95 HP, 31 IV, 252 EV, level 50
        # HP = floor((2*95 + 31 + floor(252/4)) * 50/100) + 50 + 10
        # HP = floor((190 + 31 + 63) * 0.5) + 60 = floor(142) + 60 = 202
        result = calculate_hp(base=95, iv=31, ev=252, level=50)
        assert result == 202

    def test_zero_evs_hp(self):
        """Test HP calculation with 0 EVs."""
        # Incineroar: base 95 HP, 31 IV, 0 EV, level 50
        # HP = floor((190 + 31 + 0) * 0.5) + 60 = floor(110.5) + 60 = 170
        result = calculate_hp(base=95, iv=31, ev=0, level=50)
        assert result == 170

    def test_zero_ivs_hp(self):
        """Test HP calculation with 0 IVs."""
        # Incineroar: base 95 HP, 0 IV, 252 EV, level 50
        # HP = floor((190 + 0 + 63) * 0.5) + 60 = 126 + 60 = 186
        result = calculate_hp(base=95, iv=0, ev=252, level=50)
        assert result == 186  # Lower than with 31 IVs (202)

    def test_flutter_mane_hp(self):
        """Test HP calculation for Flutter Mane (low base HP)."""
        # Flutter Mane: base 55 HP, 31 IV, 4 EV, level 50
        # HP = floor((110 + 31 + 1) * 0.5) + 60 = floor(71) + 60 = 131
        result = calculate_hp(base=55, iv=31, ev=4, level=50)
        assert result == 131

    def test_level_100_hp(self):
        """Test HP calculation at level 100."""
        # Incineroar: base 95 HP, 31 IV, 252 EV, level 100
        result = calculate_hp(base=95, iv=31, ev=252, level=100)
        assert result == 394  # Significantly higher at level 100


class TestCalculateStat:
    """Tests for non-HP stat calculation formula."""

    def test_standard_attack_252_evs_neutral(self):
        """Test Attack with 252 EVs, neutral nature."""
        # Incineroar: base 115 Atk, 31 IV, 252 EV, nature 1.0, level 50
        # Stat = floor((floor((230 + 31 + 63) * 0.5) + 5) * 1.0) = floor(167)
        result = calculate_stat(base=115, iv=31, ev=252, nature_multiplier=1.0, level=50)
        assert result == 167

    def test_attack_boosting_nature(self):
        """Test Attack with boosting nature (+10%)."""
        # Same but with 1.1 nature
        result = calculate_stat(base=115, iv=31, ev=252, nature_multiplier=1.1, level=50)
        assert result == 183  # floor(167 * 1.1) = 183

    def test_attack_hindering_nature(self):
        """Test Attack with hindering nature (-10%)."""
        result = calculate_stat(base=115, iv=31, ev=252, nature_multiplier=0.9, level=50)
        assert result == 150  # floor(167 * 0.9) = 150

    def test_speed_flutter_mane_max(self):
        """Test Flutter Mane max speed."""
        # Flutter Mane: base 135 Spe, 31 IV, 252 EV, Timid (+Spe), level 50
        result = calculate_stat(base=135, iv=31, ev=252, nature_multiplier=1.1, level=50)
        assert result == 205

    def test_zero_evs_zero_ivs(self):
        """Test stat with no investment."""
        # Base 115, 0 IV, 0 EV
        result = calculate_stat(base=115, iv=0, ev=0, nature_multiplier=1.0, level=50)
        assert result == 120  # floor((230 * 0.5) + 5) = 120


class TestParseEVString:
    """Tests for EV string parsing."""

    def test_compact_format_full(self):
        """Test slash-separated format: 252/4/0/252/0/0."""
        result = parse_ev_string("252/4/0/252/0/0")
        assert result == {"hp": 252, "atk": 4, "def": 0, "spa": 252, "spd": 0, "spe": 0}

    def test_compact_format_standard_physical(self):
        """Test standard physical spread."""
        result = parse_ev_string("252/252/0/0/4/0")
        assert result == {"hp": 252, "atk": 252, "def": 0, "spa": 0, "spd": 4, "spe": 0}

    def test_compact_format_speed_special(self):
        """Test speed/special spread."""
        result = parse_ev_string("4/0/0/252/0/252")
        assert result == {"hp": 4, "atk": 0, "def": 0, "spa": 252, "spd": 0, "spe": 252}

    def test_showdown_format_basic(self):
        """Test Showdown format: '252 HP / 4 Def / 252 SpA'."""
        result = parse_ev_string("252 HP / 4 Def / 252 SpA")
        assert result["hp"] == 252
        assert result["def"] == 4
        assert result["spa"] == 252
        assert result["atk"] == 0
        assert result["spd"] == 0
        assert result["spe"] == 0

    def test_showdown_format_speed(self):
        """Test Showdown format with Speed."""
        result = parse_ev_string("4 HP / 252 SpA / 252 Spe")
        assert result["hp"] == 4
        assert result["spa"] == 252
        assert result["spe"] == 252

    def test_showdown_format_attack(self):
        """Test Showdown format with Attack."""
        result = parse_ev_string("252 HP / 252 Atk / 4 SpD")
        assert result["hp"] == 252
        assert result["atk"] == 252
        assert result["spd"] == 4

    def test_empty_string_returns_zeros(self):
        """Test empty string returns all zeros."""
        result = parse_ev_string("")
        assert result == {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}


class TestParseIVString:
    """Tests for IV string parsing."""

    def test_compact_format_all_31s(self):
        """Test slash-separated format: 31/31/31/31/31/31."""
        result = parse_iv_string("31/31/31/31/31/31")
        assert result == {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

    def test_compact_format_zero_attack(self):
        """Test with 0 Attack IV (common for special attackers)."""
        result = parse_iv_string("31/0/31/31/31/31")
        assert result["atk"] == 0
        assert result["hp"] == 31
        assert result["spa"] == 31

    def test_showdown_format_zero_atk(self):
        """Test Showdown format: '0 Atk'."""
        result = parse_iv_string("0 Atk")
        assert result["atk"] == 0
        assert result["hp"] == 31  # Default
        assert result["spe"] == 31  # Default

    def test_showdown_format_zero_speed(self):
        """Test Showdown format: '0 Spe' (trick room)."""
        result = parse_iv_string("0 Spe")
        assert result["spe"] == 0
        assert result["hp"] == 31
        assert result["atk"] == 31

    def test_empty_string_returns_max(self):
        """Test empty string returns all 31s (default)."""
        result = parse_iv_string("")
        assert result == {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

    def test_none_returns_max(self):
        """Test None input returns all 31s."""
        result = parse_iv_string(None)
        assert result == {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}


class TestCalculateAllStats:
    """Tests for calculate_all_stats function."""

    @patch("smogon_vgc_mcp.calculator.stats.get_base_stats")
    @patch("smogon_vgc_mcp.calculator.stats.get_nature_multiplier")
    def test_incineroar_careful(self, mock_nature, mock_base):
        """Test Careful Incineroar (252 HP / 4 Atk / 252 SpD)."""
        mock_base.return_value = {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}

        # Careful: +SpD, -SpA
        def nature_mult(nature, stat):
            if stat == "spd":
                return 1.1
            elif stat == "spa":
                return 0.9
            return 1.0

        mock_nature.side_effect = nature_mult

        result = calculate_all_stats(
            pokemon="Incineroar",
            evs="252/4/0/0/252/0",
            nature="Careful",
            level=50,
        )

        assert result is not None
        assert result["hp"] == 202  # 252 HP EVs
        assert result["spd"] > result["spa"]  # Careful boosts SpD

    @patch("smogon_vgc_mcp.calculator.stats.get_base_stats")
    @patch("smogon_vgc_mcp.calculator.stats.get_nature_multiplier")
    def test_flutter_mane_timid(self, mock_nature, mock_base):
        """Test Timid Flutter Mane (4 HP / 252 SpA / 252 Spe)."""
        mock_base.return_value = {
            "hp": 55,
            "atk": 55,
            "def": 55,
            "spa": 135,
            "spd": 135,
            "spe": 135,
        }

        # Timid: +Spe, -Atk
        def nature_mult(nature, stat):
            if stat == "spe":
                return 1.1
            elif stat == "atk":
                return 0.9
            return 1.0

        mock_nature.side_effect = nature_mult

        result = calculate_all_stats(
            pokemon="Flutter Mane",
            evs="4/0/0/252/0/252",
            ivs="31/0/31/31/31/31",
            nature="Timid",
            level=50,
        )

        assert result is not None
        assert result["hp"] == 131  # Low base HP
        assert result["spe"] == 205  # Max speed with Timid

    @patch("smogon_vgc_mcp.calculator.stats.get_base_stats")
    def test_unknown_pokemon_returns_none(self, mock_base):
        """Test that unknown Pokemon returns None."""
        mock_base.return_value = None

        result = calculate_all_stats(
            pokemon="NotAPokemon",
            evs="252/252/4/0/0/0",
            nature="Adamant",
        )

        assert result is None

    @patch("smogon_vgc_mcp.calculator.stats.get_base_stats")
    @patch("smogon_vgc_mcp.calculator.stats.get_nature_multiplier")
    def test_dict_evs_input(self, mock_nature, mock_base):
        """Test with dict EVs instead of string."""
        mock_base.return_value = {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}
        mock_nature.return_value = 1.0

        evs_dict = {"hp": 252, "atk": 252, "def": 4, "spa": 0, "spd": 0, "spe": 0}

        result = calculate_all_stats(
            pokemon="Incineroar",
            evs=evs_dict,
            nature="Hardy",
            level=50,
        )

        assert result is not None
        assert result["hp"] == 202
        assert result["atk"] == 167


class TestFormatStats:
    """Tests for stats formatting function."""

    def test_format_stats_basic(self):
        """Test basic stats formatting."""
        stats = {"hp": 202, "atk": 167, "def": 110, "spa": 100, "spd": 142, "spe": 80}
        result = format_stats(stats)

        assert "HP: 202" in result
        assert "Atk: 167" in result
        assert "Def: 110" in result
        assert "SpA: 100" in result
        assert "SpD: 142" in result
        assert "Spe: 80" in result

    def test_format_stats_flutter_mane(self):
        """Test formatting Flutter Mane stats."""
        stats = {"hp": 131, "atk": 65, "def": 75, "spa": 187, "spd": 155, "spe": 205}
        result = format_stats(stats)

        assert "HP: 131" in result
        assert "Spe: 205" in result
