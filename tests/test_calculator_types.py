"""Tests for calculator/types.py - Type analysis."""

from unittest.mock import patch

from smogon_vgc_mcp.calculator.types import (
    analyze_team_types,
    get_offensive_coverage,
    get_pokemon_resistances,
    get_pokemon_weaknesses,
)


class TestGetPokemonWeaknesses:
    """Tests for get_pokemon_weaknesses function."""

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    @patch("smogon_vgc_mcp.calculator.types.get_weaknesses")
    @patch("smogon_vgc_mcp.calculator.types.get_resistances")
    def test_fire_dark_pokemon(self, mock_resist, mock_weak, mock_types):
        """Test Fire/Dark type (Incineroar)."""
        mock_types.return_value = ["Fire", "Dark"]
        mock_weak.return_value = [("Water", 2), ("Fighting", 2), ("Ground", 2), ("Rock", 2)]
        mock_resist.return_value = [
            ("Fire", 0.5),
            ("Grass", 0.5),
            ("Ice", 0.5),
            ("Ghost", 0.5),
            ("Dark", 0.5),
            ("Steel", 0.5),
            ("Psychic", 0),
        ]

        result = get_pokemon_weaknesses("Incineroar")

        assert result["pokemon"] == "Incineroar"
        assert result["types"] == ["Fire", "Dark"]
        assert "Water" in result["2x_weak"]
        assert "Fighting" in result["2x_weak"]
        assert "Psychic" in result["immunities"]
        assert len(result["4x_weak"]) == 0

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    @patch("smogon_vgc_mcp.calculator.types.get_weaknesses")
    @patch("smogon_vgc_mcp.calculator.types.get_resistances")
    def test_grass_steel_pokemon(self, mock_resist, mock_weak, mock_types):
        """Test Grass/Steel type with 4x weakness (Ferrothorn)."""
        mock_types.return_value = ["Grass", "Steel"]
        mock_weak.return_value = [("Fire", 4), ("Fighting", 2)]
        mock_resist.return_value = [
            ("Normal", 0.5),
            ("Water", 0.5),
            ("Electric", 0.5),
            ("Grass", 0.25),
            ("Psychic", 0.5),
            ("Rock", 0.5),
            ("Dragon", 0.5),
            ("Steel", 0.5),
            ("Fairy", 0.5),
            ("Poison", 0),
        ]

        result = get_pokemon_weaknesses("Ferrothorn")

        assert "Fire" in result["4x_weak"]
        assert "Fighting" in result["2x_weak"]
        assert "Grass" in result["4x_resists"]
        assert "Poison" in result["immunities"]

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    def test_unknown_pokemon_returns_error(self, mock_types):
        """Test unknown Pokemon returns error."""
        mock_types.return_value = None

        result = get_pokemon_weaknesses("NotAPokemon")

        assert "error" in result


class TestGetPokemonResistances:
    """Tests for get_pokemon_resistances function."""

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    @patch("smogon_vgc_mcp.calculator.types.get_weaknesses")
    @patch("smogon_vgc_mcp.calculator.types.get_resistances")
    def test_returns_same_as_weaknesses(self, mock_resist, mock_weak, mock_types):
        """Test that get_pokemon_resistances returns same info as get_pokemon_weaknesses."""
        mock_types.return_value = ["Fire", "Dark"]
        mock_weak.return_value = [("Water", 2)]
        mock_resist.return_value = [("Psychic", 0)]

        weak_result = get_pokemon_weaknesses("Incineroar")
        resist_result = get_pokemon_resistances("Incineroar")

        assert weak_result == resist_result


class TestAnalyzeTeamTypes:
    """Tests for analyze_team_types function."""

    def test_empty_team_returns_error(self):
        """Test empty team returns error."""
        result = analyze_team_types([])
        assert "error" in result

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_single_pokemon_team(self, mock_eff, mock_types):
        """Test team with single Pokemon."""
        mock_types.return_value = ["Fire", "Dark"]
        mock_eff.return_value = 1.0  # Neutral for simplicity

        result = analyze_team_types(["Incineroar"])

        assert result["team"] == ["Incineroar"]
        assert "Incineroar" in result["pokemon_types"]
        assert result["errors"] is None

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_team_with_unknown_pokemon(self, mock_eff, mock_types):
        """Test team with unknown Pokemon."""

        def mock_get_types(pokemon):
            if pokemon == "Incineroar":
                return ["Fire", "Dark"]
            return None

        mock_types.side_effect = mock_get_types
        mock_eff.return_value = 1.0

        result = analyze_team_types(["Incineroar", "NotAPokemon"])

        assert result["errors"] is not None
        assert len(result["errors"]) == 1
        assert "NotAPokemon" in result["errors"][0]

    @patch("smogon_vgc_mcp.calculator.types.get_pokemon_types")
    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_shared_weakness_detection(self, mock_eff, mock_types):
        """Test detection of shared weaknesses."""

        def mock_get_types(pokemon):
            types = {
                "Incineroar": ["Fire", "Dark"],
                "Charizard": ["Fire", "Flying"],
            }
            return types.get(pokemon)

        def mock_effectiveness(atk_type, def_types):
            # Water is SE against Fire
            if atk_type == "Water" and "Fire" in def_types:
                return 2.0
            return 1.0

        mock_types.side_effect = mock_get_types
        mock_eff.side_effect = mock_effectiveness

        result = analyze_team_types(["Incineroar", "Charizard"])

        # Both Pokemon are weak to Water
        assert "Water" in result["shared_weaknesses"]
        assert result["shared_weaknesses"]["Water"]["count"] == 2


class TestGetOffensiveCoverage:
    """Tests for get_offensive_coverage function."""

    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_single_move_type(self, mock_eff):
        """Test coverage with single move type."""

        def mock_effectiveness(atk_type, def_types):
            if atk_type == "Fire":
                if def_types == ["Grass"]:
                    return 2.0
                elif def_types == ["Water"]:
                    return 0.5
                elif def_types == ["Rock"]:
                    return 0.5
            return 1.0

        mock_eff.side_effect = mock_effectiveness

        result = get_offensive_coverage(["Fire"])

        assert result["move_types"] == ["Fire"]
        assert "Grass" in result["super_effective_against"]

    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_dual_stab_coverage(self, mock_eff):
        """Test coverage with dual STAB."""

        def mock_effectiveness(atk_type, def_types):
            # Fire hits Grass, Ice, Steel, Bug SE
            if atk_type == "Fire" and def_types[0] in ["Grass", "Ice", "Steel", "Bug"]:
                return 2.0
            # Dark hits Ghost, Psychic SE
            if atk_type == "Dark" and def_types[0] in ["Ghost", "Psychic"]:
                return 2.0
            return 1.0

        mock_eff.side_effect = mock_effectiveness

        result = get_offensive_coverage(["Fire", "Dark"])

        assert "Grass" in result["super_effective_against"]
        assert "Ghost" in result["super_effective_against"]
        assert "Psychic" in result["super_effective_against"]

    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_coverage_gaps(self, mock_eff):
        """Test detection of coverage gaps."""

        def mock_effectiveness(atk_type, def_types):
            # Normal doesn't hit anything SE
            return 1.0

        mock_eff.side_effect = mock_effectiveness

        result = get_offensive_coverage(["Normal"])

        # Normal doesn't hit anything SE, so no_super_effective_coverage should have all types
        assert len(result["no_super_effective_coverage"]) > 0

    @patch("smogon_vgc_mcp.calculator.types.get_type_effectiveness")
    def test_immunity_detection(self, mock_eff):
        """Test detection of immune types."""

        def mock_effectiveness(atk_type, def_types):
            # Normal doesn't affect Ghost
            if atk_type == "Normal" and def_types == ["Ghost"]:
                return 0
            # Ground doesn't affect Flying
            if atk_type == "Ground" and def_types == ["Flying"]:
                return 0
            return 1.0

        mock_eff.side_effect = mock_effectiveness

        result = get_offensive_coverage(["Normal", "Ground"])

        assert "Ghost" in result["immune_types"]
        assert "Flying" in result["immune_types"]
