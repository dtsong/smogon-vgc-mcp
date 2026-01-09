"""Tests for data/pokemon_data.py - Pokemon reference data."""

import json
from unittest.mock import mock_open, patch

from smogon_vgc_mcp.data.pokemon_data import (
    ALL_TYPES,
    NATURE_MODIFIERS,
    TYPE_CHART,
    get_base_stats,
    get_nature_modifiers,
    get_nature_multiplier,
    get_pokemon_types,
    get_resistances,
    get_type_effectiveness,
    get_weaknesses,
    normalize_pokemon_name,
)


class TestNormalizePokemonName:
    """Tests for normalize_pokemon_name function."""

    def test_lowercase(self):
        """Test name is lowercased."""
        assert normalize_pokemon_name("Incineroar") == "incineroar"
        assert normalize_pokemon_name("FLUTTER MANE") == "fluttermane"

    def test_removes_spaces(self):
        """Test spaces are removed."""
        assert normalize_pokemon_name("Flutter Mane") == "fluttermane"
        assert normalize_pokemon_name("Raging Bolt") == "ragingbolt"

    def test_removes_hyphens(self):
        """Test hyphens are removed."""
        assert normalize_pokemon_name("Urshifu-Rapid-Strike") == "urshifurapidstrike"
        assert normalize_pokemon_name("Ho-Oh") == "hooh"

    def test_already_normalized(self):
        """Test already normalized names."""
        assert normalize_pokemon_name("incineroar") == "incineroar"
        assert normalize_pokemon_name("fluttermane") == "fluttermane"

    def test_mixed_case_and_special(self):
        """Test mixed case with spaces and hyphens."""
        assert normalize_pokemon_name("Flutter-Mane") == "fluttermane"


class TestGetBaseStats:
    """Tests for get_base_stats function."""

    @patch("smogon_vgc_mcp.data.pokemon_data._base_stats", None)
    @patch(
        "builtins.open",
        mock_open(
            read_data=json.dumps(
                {
                    "incineroar": {
                        "hp": 95,
                        "atk": 115,
                        "def": 90,
                        "spa": 80,
                        "spd": 90,
                        "spe": 60,
                    },
                    "fluttermane": {
                        "hp": 55,
                        "atk": 55,
                        "def": 55,
                        "spa": 135,
                        "spd": 135,
                        "spe": 135,
                    },
                }
            )
        ),
    )
    def test_get_existing_pokemon(self):
        """Test getting stats for existing Pokemon."""
        result = get_base_stats("Incineroar")

        assert result is not None
        assert result["hp"] == 95
        assert result["atk"] == 115
        assert result["spe"] == 60

    @patch("smogon_vgc_mcp.data.pokemon_data._base_stats", None)
    @patch(
        "builtins.open",
        mock_open(
            read_data=json.dumps(
                {
                    "incineroar": {
                        "hp": 95,
                        "atk": 115,
                        "def": 90,
                        "spa": 80,
                        "spd": 90,
                        "spe": 60,
                    },
                }
            )
        ),
    )
    def test_case_insensitive(self):
        """Test case-insensitive lookup."""
        result1 = get_base_stats("Incineroar")
        # Reset cache for second test
        import smogon_vgc_mcp.data.pokemon_data as module

        module._base_stats = {
            "incineroar": {"hp": 95, "atk": 115, "def": 90, "spa": 80, "spd": 90, "spe": 60}
        }
        result2 = get_base_stats("INCINEROAR")
        result3 = get_base_stats("incineroar")

        assert result1 == result2 == result3

    @patch("smogon_vgc_mcp.data.pokemon_data._base_stats", {"incineroar": {"hp": 95}})
    def test_unknown_pokemon_returns_none(self):
        """Test unknown Pokemon returns None."""
        result = get_base_stats("NotAPokemon")
        assert result is None

    @patch(
        "smogon_vgc_mcp.data.pokemon_data._base_stats",
        {"fluttermane": {"hp": 55, "atk": 55, "def": 55, "spa": 135, "spd": 135, "spe": 135}},
    )
    def test_normalized_name_lookup(self):
        """Test Pokemon with spaces are normalized."""
        result = get_base_stats("Flutter Mane")
        assert result is not None
        assert result["spa"] == 135


class TestGetPokemonTypes:
    """Tests for get_pokemon_types function."""

    @patch(
        "smogon_vgc_mcp.data.pokemon_data._types",
        {
            "incineroar": ["Fire", "Dark"],
            "fluttermane": ["Ghost", "Fairy"],
        },
    )
    def test_dual_type_pokemon(self):
        """Test getting types for dual-type Pokemon."""
        result = get_pokemon_types("Incineroar")

        assert result == ["Fire", "Dark"]

    @patch(
        "smogon_vgc_mcp.data.pokemon_data._types",
        {
            "pikachu": ["Electric"],
        },
    )
    def test_single_type_pokemon(self):
        """Test getting types for single-type Pokemon."""
        result = get_pokemon_types("Pikachu")

        assert result == ["Electric"]

    @patch("smogon_vgc_mcp.data.pokemon_data._types", {"incineroar": ["Fire", "Dark"]})
    def test_unknown_pokemon_returns_none(self):
        """Test unknown Pokemon returns None."""
        result = get_pokemon_types("NotAPokemon")
        assert result is None

    @patch("smogon_vgc_mcp.data.pokemon_data._types", {"fluttermane": ["Ghost", "Fairy"]})
    def test_spaces_in_name(self):
        """Test Pokemon with spaces in name."""
        result = get_pokemon_types("Flutter Mane")
        assert result == ["Ghost", "Fairy"]


class TestNatureModifiers:
    """Tests for NATURE_MODIFIERS constant and related functions."""

    def test_all_25_natures_present(self):
        """Test all 25 natures are defined."""
        assert len(NATURE_MODIFIERS) == 25

    def test_neutral_natures(self):
        """Test neutral natures have no modifier."""
        neutral = ["hardy", "docile", "serious", "bashful", "quirky"]
        for nature in neutral:
            assert NATURE_MODIFIERS[nature] is None

    def test_attack_boosting_natures(self):
        """Test attack-boosting natures."""
        # Adamant: +Atk, -SpA
        assert NATURE_MODIFIERS["adamant"] == ("atk", "spa")
        # Brave: +Atk, -Spe
        assert NATURE_MODIFIERS["brave"] == ("atk", "spe")

    def test_speed_boosting_natures(self):
        """Test speed-boosting natures."""
        # Jolly: +Spe, -SpA
        assert NATURE_MODIFIERS["jolly"] == ("spe", "spa")
        # Timid: +Spe, -Atk
        assert NATURE_MODIFIERS["timid"] == ("spe", "atk")

    def test_special_attack_boosting_natures(self):
        """Test special attack-boosting natures."""
        # Modest: +SpA, -Atk
        assert NATURE_MODIFIERS["modest"] == ("spa", "atk")
        # Quiet: +SpA, -Spe (Trick Room)
        assert NATURE_MODIFIERS["quiet"] == ("spa", "spe")

    def test_special_defense_boosting_natures(self):
        """Test special defense-boosting natures."""
        # Careful: +SpD, -SpA (common on Incineroar)
        assert NATURE_MODIFIERS["careful"] == ("spd", "spa")
        # Sassy: +SpD, -Spe (Trick Room)
        assert NATURE_MODIFIERS["sassy"] == ("spd", "spe")


class TestGetNatureModifiers:
    """Tests for get_nature_modifiers function."""

    def test_neutral_nature(self):
        """Test neutral nature returns None."""
        assert get_nature_modifiers("Hardy") is None
        assert get_nature_modifiers("Serious") is None

    def test_boosting_nature(self):
        """Test boosting nature returns tuple."""
        result = get_nature_modifiers("Adamant")
        assert result == ("atk", "spa")

    def test_case_insensitive(self):
        """Test case-insensitive lookup."""
        assert get_nature_modifiers("ADAMANT") == ("atk", "spa")
        assert get_nature_modifiers("adamant") == ("atk", "spa")
        assert get_nature_modifiers("Adamant") == ("atk", "spa")


class TestGetNatureMultiplier:
    """Tests for get_nature_multiplier function."""

    def test_boosted_stat(self):
        """Test boosted stat returns 1.1."""
        # Adamant boosts Attack
        assert get_nature_multiplier("Adamant", "atk") == 1.1
        # Timid boosts Speed
        assert get_nature_multiplier("Timid", "spe") == 1.1

    def test_reduced_stat(self):
        """Test reduced stat returns 0.9."""
        # Adamant reduces Special Attack
        assert get_nature_multiplier("Adamant", "spa") == 0.9
        # Timid reduces Attack
        assert get_nature_multiplier("Timid", "atk") == 0.9

    def test_neutral_stat(self):
        """Test unaffected stat returns 1.0."""
        # Adamant doesn't affect HP
        assert get_nature_multiplier("Adamant", "hp") == 1.0
        # Adamant doesn't affect Defense
        assert get_nature_multiplier("Adamant", "def") == 1.0

    def test_neutral_nature(self):
        """Test neutral nature returns 1.0 for all stats."""
        stats = ["hp", "atk", "def", "spa", "spd", "spe"]
        for stat in stats:
            assert get_nature_multiplier("Hardy", stat) == 1.0

    def test_common_vgc_natures(self):
        """Test common VGC nature multipliers."""
        # Careful Incineroar
        assert get_nature_multiplier("Careful", "spd") == 1.1
        assert get_nature_multiplier("Careful", "spa") == 0.9

        # Timid Flutter Mane
        assert get_nature_multiplier("Timid", "spe") == 1.1
        assert get_nature_multiplier("Timid", "atk") == 0.9

        # Modest special attacker
        assert get_nature_multiplier("Modest", "spa") == 1.1
        assert get_nature_multiplier("Modest", "atk") == 0.9


class TestTypeChart:
    """Tests for TYPE_CHART constant."""

    def test_all_types_present(self):
        """Test all 18 types are in the chart."""
        expected_types = [
            "Normal",
            "Fire",
            "Water",
            "Electric",
            "Grass",
            "Ice",
            "Fighting",
            "Poison",
            "Ground",
            "Flying",
            "Psychic",
            "Bug",
            "Rock",
            "Ghost",
            "Dragon",
            "Dark",
            "Steel",
            "Fairy",
        ]
        assert len(TYPE_CHART) == 18
        for t in expected_types:
            assert t in TYPE_CHART

    def test_all_types_list(self):
        """Test ALL_TYPES list matches TYPE_CHART keys."""
        assert set(ALL_TYPES) == set(TYPE_CHART.keys())

    def test_fire_effectiveness(self):
        """Test Fire type effectiveness."""
        fire = TYPE_CHART["Fire"]
        assert fire["Grass"] == 2  # Super effective
        assert fire["Water"] == 0.5  # Not very effective
        assert fire["Steel"] == 2  # Super effective
        assert fire.get("Normal", 1) == 1  # Neutral

    def test_ground_effectiveness(self):
        """Test Ground type effectiveness (includes immunity)."""
        ground = TYPE_CHART["Ground"]
        assert ground["Flying"] == 0  # Immunity
        assert ground["Electric"] == 2  # Super effective

    def test_ghost_effectiveness(self):
        """Test Ghost type effectiveness."""
        ghost = TYPE_CHART["Ghost"]
        assert ghost["Normal"] == 0  # Immunity
        assert ghost["Psychic"] == 2  # Super effective
        assert ghost["Ghost"] == 2  # Super effective


class TestGetTypeEffectiveness:
    """Tests for get_type_effectiveness function."""

    def test_neutral_matchup(self):
        """Test neutral type matchup returns 1.0."""
        result = get_type_effectiveness("Normal", ["Dragon"])
        assert result == 1.0

    def test_super_effective(self):
        """Test super effective returns 2.0."""
        result = get_type_effectiveness("Fire", ["Grass"])
        assert result == 2.0

    def test_not_very_effective(self):
        """Test not very effective returns 0.5."""
        result = get_type_effectiveness("Fire", ["Water"])
        assert result == 0.5

    def test_immunity(self):
        """Test immunity returns 0."""
        result = get_type_effectiveness("Ground", ["Flying"])
        assert result == 0

    def test_dual_type_both_weak(self):
        """Test 4x weakness (dual type both weak)."""
        # Fire vs Grass/Steel (4x effective)
        result = get_type_effectiveness("Fire", ["Grass", "Steel"])
        assert result == 4.0

    def test_dual_type_one_weak_one_resist(self):
        """Test dual type with one weak and one resist (1x)."""
        # Fire vs Grass/Water (2x * 0.5x = 1x)
        result = get_type_effectiveness("Fire", ["Grass", "Water"])
        assert result == 1.0

    def test_dual_type_both_resist(self):
        """Test 0.25x resistance (dual type both resist)."""
        # Fire vs Fire/Water (0.5x * 0.5x = 0.25x)
        result = get_type_effectiveness("Fire", ["Fire", "Water"])
        assert result == 0.25

    def test_immunity_overrides_weakness(self):
        """Test immunity overrides everything."""
        # Ground vs Flying/Water - Flying is immune
        result = get_type_effectiveness("Ground", ["Flying", "Water"])
        assert result == 0

    def test_case_insensitive(self):
        """Test case-insensitive type names."""
        result1 = get_type_effectiveness("fire", ["grass"])
        result2 = get_type_effectiveness("FIRE", ["GRASS"])
        assert result1 == result2 == 2.0


class TestGetWeaknesses:
    """Tests for get_weaknesses function."""

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_fire_dark_weaknesses(self, mock_types):
        """Test Fire/Dark weaknesses (Incineroar)."""
        mock_types.return_value = ["Fire", "Dark"]

        result = get_weaknesses("Incineroar")

        # Fire/Dark is weak to: Water, Fighting, Ground, Rock
        weak_types = [t for t, m in result]
        assert "Water" in weak_types
        assert "Fighting" in weak_types
        assert "Ground" in weak_types
        assert "Rock" in weak_types

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_ghost_fairy_weaknesses(self, mock_types):
        """Test Ghost/Fairy weaknesses (Flutter Mane)."""
        mock_types.return_value = ["Ghost", "Fairy"]

        result = get_weaknesses("Flutter Mane")

        weak_types = [t for t, m in result]
        assert "Ghost" in weak_types
        assert "Steel" in weak_types

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_4x_weakness(self, mock_types):
        """Test 4x weakness detection."""
        mock_types.return_value = ["Grass", "Steel"]

        result = get_weaknesses("Ferrothorn")

        # Grass/Steel is 4x weak to Fire
        fire_entry = next((t, m) for t, m in result if t == "Fire")
        assert fire_entry[1] == 4.0

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_weaknesses_sorted_by_severity(self, mock_types):
        """Test weaknesses are sorted by multiplier (4x before 2x)."""
        mock_types.return_value = ["Grass", "Steel"]

        result = get_weaknesses("Ferrothorn")

        # First weakness should be 4x (Fire)
        assert result[0][1] == 4.0

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_unknown_pokemon(self, mock_types):
        """Test unknown Pokemon returns empty list."""
        mock_types.return_value = None

        result = get_weaknesses("NotAPokemon")

        assert result == []


class TestGetResistances:
    """Tests for get_resistances function."""

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_fire_dark_resistances(self, mock_types):
        """Test Fire/Dark resistances (Incineroar)."""
        mock_types.return_value = ["Fire", "Dark"]

        result = get_resistances("Incineroar")

        resist_types = [t for t, m in result]
        # Fire/Dark resists: Fire, Grass, Ice, Ghost, Dark, Steel
        assert "Fire" in resist_types
        assert "Ghost" in resist_types
        # Fire/Dark is immune to Psychic
        assert "Psychic" in resist_types

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_immunity_in_resistances(self, mock_types):
        """Test immunity appears in resistances."""
        mock_types.return_value = ["Fire", "Dark"]

        result = get_resistances("Incineroar")

        # Fire/Dark is immune to Psychic (0x)
        psychic_entry = next((t, m) for t, m in result if t == "Psychic")
        assert psychic_entry[1] == 0

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_4x_resistance(self, mock_types):
        """Test 4x resistance detection."""
        mock_types.return_value = ["Grass", "Steel"]

        result = get_resistances("Ferrothorn")

        # Grass/Steel 4x resists Grass
        grass_entry = next((t, m) for t, m in result if t == "Grass")
        assert grass_entry[1] == 0.25

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_resistances_sorted_by_multiplier(self, mock_types):
        """Test resistances sorted (0x first, then 0.25x, then 0.5x)."""
        mock_types.return_value = ["Grass", "Steel"]

        result = get_resistances("Ferrothorn")

        # First should be immunity (0) if any, then 0.25x, then 0.5x
        multipliers = [m for t, m in result]
        assert multipliers == sorted(multipliers)

    @patch("smogon_vgc_mcp.data.pokemon_data.get_pokemon_types")
    def test_unknown_pokemon(self, mock_types):
        """Test unknown Pokemon returns empty list."""
        mock_types.return_value = None

        result = get_resistances("NotAPokemon")

        assert result == []
