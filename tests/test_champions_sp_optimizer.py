"""Tests for calculator/champions_sp_optimizer.py - Champions SP optimization."""

from smogon_vgc_mcp.calculator.champions_sp_optimizer import (
    HpThresholdGoal,
    MaximizeGoal,
    SpeedGoal,
    optimize_champions_sp,
    suggest_hp_sp,
)


class TestSuggestHpSp:
    """Tests for HP SP suggestion based on item divisibility."""

    def test_leftovers_base_80(self):
        """Leftovers: base 80 → HP 140. 140 % 16 = 12, need +4 → 144 % 16 == 0."""
        result = suggest_hp_sp(base_hp=80, item="Leftovers", level=50)
        assert result["recommended_sp"] == 4
        assert result["resulting_hp"] == 144
        assert result["resulting_hp"] % 16 == 0

    def test_black_sludge_base_80(self):
        """Black Sludge uses same rule as Leftovers."""
        result = suggest_hp_sp(base_hp=80, item="Black Sludge", level=50)
        assert result["recommended_sp"] == 4
        assert result["resulting_hp"] == 144
        assert result["resulting_hp"] % 16 == 0

    def test_life_orb_base_80(self):
        """Life Orb: base 80 → HP 140. 140 % 10 = 0, need +1 → 141 % 10 == 1."""
        result = suggest_hp_sp(base_hp=80, item="Life Orb", level=50)
        assert result["recommended_sp"] == 1
        assert result["resulting_hp"] == 141
        assert result["resulting_hp"] % 10 == 1

    def test_sitrus_berry_base_80(self):
        """Sitrus Berry: base 80 → HP 140. 140 % 4 == 0 already, sp=0."""
        result = suggest_hp_sp(base_hp=80, item="Sitrus Berry", level=50)
        assert result["recommended_sp"] == 0
        assert result["resulting_hp"] == 140
        assert result["resulting_hp"] % 4 == 0

    def test_no_item(self):
        """No item → recommended_sp = 0."""
        result = suggest_hp_sp(base_hp=80, item=None, level=50)
        assert result["recommended_sp"] == 0

    def test_unknown_item(self):
        """Unknown item → recommended_sp = 0."""
        result = suggest_hp_sp(base_hp=80, item="Choice Band", level=50)
        assert result["recommended_sp"] == 0

    def test_sp_capped_at_32(self):
        """SP should never exceed 32 even if divisibility requires more."""
        # Find a base where leftovers would need >32 SP... unlikely but test the cap
        # base_hp=1 → HP = floor((2*1)*50/100)+50+10 = 61. 61%16=13, need +3 → 64
        result = suggest_hp_sp(base_hp=1, item="Leftovers", level=50)
        assert result["recommended_sp"] <= 32


class TestOptimizeChampionsSp:
    """Tests for full SP optimization."""

    def test_single_speed_goal_outspeed(self):
        """Outspeed target 105 with base spe 100, neutral nature."""
        # base_speed_no_sp = floor((100+5)*1.0) = 105
        # Need 106. sp_needed = 106 - 105 = 1
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 100}
        goals = [SpeedGoal(target_speed=105)]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is True
        assert result["sp_spread"]["spe"] == 1
        assert result["total_sp"] == 1

    def test_maximize_after_speed(self):
        """Speed goal + maximize SpA."""
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 100}
        goals = [SpeedGoal(target_speed=105), MaximizeGoal(stat="spa")]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is True
        assert result["sp_spread"]["spe"] == 1
        # Remaining: 66 - 1 = 65, but max per stat is 32
        assert result["sp_spread"]["spa"] == 32
        assert result["total_sp"] == 33

    def test_hp_threshold_goal(self):
        """HP threshold with Leftovers."""
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80}
        goals = [HpThresholdGoal(item="Leftovers")]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is True
        assert result["sp_spread"]["hp"] == 4

    def test_impossible_speed_goal(self):
        """Speed goal that can't be met returns failure."""
        # base spe 50 → base_speed = floor((50+5)*1.0) = 55
        # Need to outspeed 200 → sp_needed = 201 - 55 = 146, way over 32
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 50}
        goals = [SpeedGoal(target_speed=200)]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is False

    def test_total_sp_never_exceeds_66(self):
        """Multiple maximize goals shouldn't exceed total 66 SP."""
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80}
        goals = [
            MaximizeGoal(stat="spa"),
            MaximizeGoal(stat="spe"),
            MaximizeGoal(stat="hp"),
        ]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is True
        assert result["total_sp"] <= 66
        assert result["sp_spread"]["spa"] == 32
        assert result["sp_spread"]["spe"] == 32
        assert result["sp_spread"]["hp"] == 2  # 66 - 32 - 32 = 2

    def test_underspeed_goal(self):
        """Underspeed mode: want speed BELOW target."""
        # base spe 100, neutral → base_speed = 105
        # Underspeed 100 means we want our speed <= 99
        # With SP system you can't reduce speed below base, so this should be
        # already satisfied if base_speed_no_sp < target (sp=0)
        # base_speed = 105 > 100, can't underspeed → fail
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 100}
        goals = [SpeedGoal(target_speed=100, mode="underspeed")]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is False

    def test_underspeed_already_slow(self):
        """Underspeed goal already met at 0 SP."""
        # base spe 30, neutral → base_speed = floor((30+5)*1.0) = 35
        # Underspeed 50 → 35 < 50, already under, sp=0
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 30}
        goals = [SpeedGoal(target_speed=50, mode="underspeed")]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is True
        assert result["sp_spread"]["spe"] == 0

    def test_goal_results_populated(self):
        """Each goal produces a result entry."""
        base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80}
        goals = [MaximizeGoal(stat="spa"), HpThresholdGoal(item="Leftovers")]
        result = optimize_champions_sp(base_stats, nature="Hardy", goals=goals, level=50)
        assert result["success"] is True
        assert len(result["goal_results"]) == 2
