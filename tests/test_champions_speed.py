"""Tests for calculator/champions_speed.py - Champions format speed tier tools."""

from smogon_vgc_mcp.calculator.champions_speed import (
    CHAMPIONS_SPEED_TIERS,
    compare_champions_speeds,
    find_champions_speed_benchmarks,
    find_champions_speed_sp,
    get_champions_speed,
)


class TestGetChampionsSpeed:
    """Tests for Champions speed stat calculation."""

    def test_gengar_max_sp_plus_nature(self):
        """Gengar base 110, +nature (Timid), 32 SP = 158."""
        assert get_champions_speed(base_spe=110, sp=32, nature="Timid") == 158

    def test_incineroar_no_sp_neutral(self):
        """Incineroar base 60, neutral, 0 SP = 65."""
        assert get_champions_speed(base_spe=60, sp=0, nature="Hardy") == 65

    def test_incineroar_max_sp_neutral(self):
        """Incineroar base 60, neutral, 32 SP = 97."""
        assert get_champions_speed(base_spe=60, sp=32, nature="Hardy") == 97

    def test_dragonite_brave_minus_nature(self):
        """Dragonite base 80, Brave (-spe), 0 SP = 76."""
        assert get_champions_speed(base_spe=80, sp=0, nature="Brave") == 76


class TestCompareChampionsSpeeds:
    """Tests for speed comparison."""

    def test_faster_wins(self):
        """Pokemon with higher speed is faster."""
        result = compare_champions_speeds(
            pokemon1="Gengar",
            base_spe1=110,
            sp1=32,
            nature1="Timid",
            pokemon2="Incineroar",
            base_spe2=60,
            sp2=0,
            nature2="Hardy",
        )
        assert result["result"] == "pokemon1_faster"
        assert result["pokemon1"]["speed"] == 158
        assert result["pokemon2"]["speed"] == 65
        assert result["difference"] == 93

    def test_tie(self):
        """Same speed results in tie."""
        result = compare_champions_speeds(
            pokemon1="A",
            base_spe1=60,
            sp1=0,
            nature1="Hardy",
            pokemon2="B",
            base_spe2=60,
            sp2=0,
            nature2="Hardy",
        )
        assert result["result"] == "tie"
        assert result["difference"] == 0

    def test_slower_loses(self):
        """Pokemon with lower speed is slower."""
        result = compare_champions_speeds(
            pokemon1="Incineroar",
            base_spe1=60,
            sp1=0,
            nature1="Hardy",
            pokemon2="Gengar",
            base_spe2=110,
            sp2=32,
            nature2="Timid",
        )
        assert result["result"] == "pokemon2_faster"
        assert result["difference"] == 93


class TestFindChampionsSpeedBenchmarks:
    """Tests for speed benchmark lookups."""

    def test_returns_outspeeds_underspeeds_ties(self):
        """Result contains all three lists."""
        result = find_champions_speed_benchmarks("TestMon", 150)
        assert "outspeeds" in result
        assert "underspeeds" in result
        assert "speed_ties" in result

    def test_high_speed_outspeeds_many(self):
        """A very high speed outspeeds many benchmarks."""
        result = find_champions_speed_benchmarks("FastMon", 300)
        assert len(result["outspeeds"]) > 10
        assert len(result["underspeeds"]) == 0

    def test_low_speed_underspeeds_many(self):
        """A very low speed underspeeds many benchmarks."""
        result = find_champions_speed_benchmarks("SlowMon", 50)
        assert len(result["underspeeds"]) > 10
        assert len(result["outspeeds"]) == 0

    def test_speed_tie_detected(self):
        """Exact match on a benchmark registers as tie."""
        result = find_champions_speed_benchmarks("TieMon", 132)
        assert len(result["speed_ties"]) > 0
        tie_names = [t["pokemon"] for t in result["speed_ties"]]
        assert "Dragonite" in tie_names

    def test_deduplication(self):
        """Entries are deduplicated (no repeated pokemon+speed combos in a category)."""
        result = find_champions_speed_benchmarks("TestMon", 265)
        # 264 appears multiple times in tiers, outspeeds should have them all
        # but each entry should be unique (speed, pokemon, notes tuple)
        outspeeds_tuples = [(e["speed"], e["pokemon"], e["notes"]) for e in result["outspeeds"]]
        assert len(outspeeds_tuples) == len(set(outspeeds_tuples))


class TestFindChampionsSpeedSp:
    """Tests for SP requirement calculation."""

    def test_outspeed_target(self):
        """Base 80, +nature (Jolly) needs 11 SP to outspeed 103."""
        result = find_champions_speed_sp(
            base_spe=80,
            target_speed=103,
            nature="Jolly",
            goal="outspeed",
        )
        assert result["success"] is True
        assert result["sp_needed"] == 11
        assert result["resulting_speed"] == 104
        assert result["target_speed"] == 103

    def test_impossible_underspeed(self):
        """Cannot underspeed a target slower than your 0 SP speed."""
        # Base 110, Timid: floor((110+5)*1.1) = 126. Can't underspeed 130.
        result = find_champions_speed_sp(
            base_spe=110,
            target_speed=130,
            nature="Timid",
            goal="underspeed",
        )
        assert result["success"] is True
        assert result["sp_needed"] == 0
        assert result["resulting_speed"] == 126

    def test_already_outspeeds(self):
        """Already outspeeds with 0 SP => sp_needed=0."""
        # Base 110, Timid, 0 SP = 126. Target 100 => already outspeeds.
        result = find_champions_speed_sp(
            base_spe=110,
            target_speed=100,
            nature="Timid",
            goal="outspeed",
        )
        assert result["success"] is True
        assert result["sp_needed"] == 0
        assert result["resulting_speed"] == 126

    def test_outspeed_impossible_too_high(self):
        """Cannot outspeed a target even with max SP."""
        # Base 30, neutral: floor((30+5)*1.0) = 35. Max SP=32 => 67.
        # Target 70 => need 71-35=36 SP, exceeds 32.
        result = find_champions_speed_sp(
            base_spe=30,
            target_speed=70,
            nature="Hardy",
            goal="outspeed",
        )
        assert result["success"] is False

    def test_underspeed_impossible(self):
        """Base speed already faster than target, can't underspeed."""
        # Base 110, Timid: 126 at 0 SP. Target 100 => can't go below 126.
        result = find_champions_speed_sp(
            base_spe=110,
            target_speed=100,
            nature="Timid",
            goal="underspeed",
        )
        assert result["success"] is False


class TestChampionsSpeedTiers:
    """Tests for the speed tier constant."""

    def test_is_list_of_tuples(self):
        assert isinstance(CHAMPIONS_SPEED_TIERS, list)
        assert all(isinstance(t, tuple) and len(t) == 3 for t in CHAMPIONS_SPEED_TIERS)

    def test_sorted_descending(self):
        speeds = [t[0] for t in CHAMPIONS_SPEED_TIERS]
        assert speeds == sorted(speeds, reverse=True)

    def test_contains_known_entries(self):
        entries = {(t[0], t[1]) for t in CHAMPIONS_SPEED_TIERS}
        assert (280, "Excadrill") in entries
        assert (102, "Kingambit") in entries
