"""Tests for calculator/champions_stats.py - Champions format stat calculations."""

import pytest

from smogon_vgc_mcp.calculator.champions_stats import (
    MAX_SP_PER_STAT,
    MAX_TOTAL_SP,
    calculate_all_champions_stats,
    calculate_champions_hp,
    calculate_champions_stat,
    format_champions_stats,
)


class TestCalculateChampionsHP:
    """Tests for Champions HP formula."""

    def test_base_100_no_sp(self):
        """Base 100, SP 0, level 100: floor((2*100)*100/100) + 100 + 10 + 0 = 310."""
        assert calculate_champions_hp(base=100, sp=0, level=100) == 310

    def test_base_100_max_sp(self):
        """Base 100, SP 32, level 100: 310 + 32 = 342."""
        assert calculate_champions_hp(base=100, sp=32, level=100) == 342

    def test_base_80_no_sp(self):
        """Base 80, SP 0, level 100: floor((2*80)*100/100) + 100 + 10 + 0 = 270."""
        assert calculate_champions_hp(base=80, sp=0, level=100) == 270

    def test_sp_validation_too_high(self):
        """SP > 32 raises ValueError."""
        with pytest.raises(ValueError):
            calculate_champions_hp(base=100, sp=33, level=100)

    def test_sp_validation_negative(self):
        """SP < 0 raises ValueError."""
        with pytest.raises(ValueError):
            calculate_champions_hp(base=100, sp=-1, level=100)


class TestCalculateChampionsStat:
    """Tests for Champions non-HP stat formula."""

    def test_neutral_nature(self):
        """Base 100, SP 0, neutral, level 100: floor((floor((2*100)*100/100)+5)*1.0)+0 = 205."""
        assert calculate_champions_stat(base=100, sp=0, nature_multiplier=1.0, level=100) == 205

    def test_boosted_nature(self):
        """Base 100, SP 0, boosted, level 100: floor(205*1.1)+0 = floor(225.5) = 225."""
        assert calculate_champions_stat(base=100, sp=0, nature_multiplier=1.1, level=100) == 225

    def test_reduced_nature(self):
        """Base 100, SP 0, reduced, level 100: floor(205*0.9)+0 = floor(184.5) = 184."""
        assert calculate_champions_stat(base=100, sp=0, nature_multiplier=0.9, level=100) == 184

    def test_sp_added_after_nature(self):
        """SP is added AFTER nature multiplier. Base 100, SP 10, boosted.
        floor(205*1.1) + 10 = 225 + 10 = 235, NOT floor((205+10)*1.1) = floor(236.5) = 236."""
        result = calculate_champions_stat(base=100, sp=10, nature_multiplier=1.1, level=100)
        assert result == 235

    def test_sp_validation_too_high(self):
        """SP > 32 raises ValueError."""
        with pytest.raises(ValueError):
            calculate_champions_stat(base=100, sp=33, nature_multiplier=1.0, level=100)

    def test_sp_validation_negative(self):
        """SP < 0 raises ValueError."""
        with pytest.raises(ValueError):
            calculate_champions_stat(base=100, sp=-1, nature_multiplier=1.0, level=100)


class TestCalculateAllChampionsStats:
    """Tests for all-stats calculation."""

    def test_zero_sp_neutral(self):
        """All zero SP with neutral nature."""
        base_stats = {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
        sp_spread = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        result = calculate_all_champions_stats(base_stats, sp_spread, nature="Hardy", level=100)
        assert result is not None
        assert result["hp"] == 310
        assert result["atk"] == 205
        assert result["def"] == 205
        assert result["spa"] == 205
        assert result["spd"] == 205
        assert result["spe"] == 205

    def test_modest_mixed_sp(self):
        """Modest (+SpA, -Atk) with mixed SP spread."""
        base_stats = {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
        sp_spread = {"hp": 10, "atk": 0, "def": 6, "spa": 20, "spd": 10, "spe": 20}
        # Total SP = 66, valid
        result = calculate_all_champions_stats(base_stats, sp_spread, nature="Modest", level=100)
        assert result is not None
        assert result["hp"] == 320  # 310 + 10
        # Atk reduced: floor(205*0.9) + 0 = 184
        assert result["atk"] == 184
        assert result["def"] == 205 + 6  # 211
        # SpA boosted: floor(205*1.1) + 20 = 225 + 20 = 245
        assert result["spa"] == 245
        assert result["spd"] == 205 + 10  # 215
        assert result["spe"] == 205 + 20  # 225

    def test_total_sp_over_66_raises(self):
        """Total SP > 66 raises ValueError."""
        base_stats = {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
        sp_spread = {"hp": 32, "atk": 32, "def": 3, "spa": 0, "spd": 0, "spe": 0}
        # Total = 67, invalid
        with pytest.raises(ValueError):
            calculate_all_champions_stats(base_stats, sp_spread, nature="Hardy", level=100)

    def test_invalid_nature_returns_none(self):
        """Invalid nature name returns None."""
        base_stats = {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
        sp_spread = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        result = calculate_all_champions_stats(
            base_stats, sp_spread, nature="FakeNature", level=100
        )
        assert result is None


class TestFormatChampionsStats:
    """Tests for stat formatting."""

    def test_format_output(self):
        """Verify format string."""
        stats = {"hp": 310, "atk": 205, "def": 205, "spa": 205, "spd": 205, "spe": 205}
        result = format_champions_stats(stats)
        assert result == "HP: 310 / Atk: 205 / Def: 205 / SpA: 205 / SpD: 205 / Spe: 205"


class TestConstants:
    """Tests for module constants."""

    def test_max_sp_per_stat(self):
        assert MAX_SP_PER_STAT == 32

    def test_max_total_sp(self):
        assert MAX_TOTAL_SP == 66
