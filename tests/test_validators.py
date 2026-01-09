"""Tests for input validation utilities."""

import pytest

from smogon_vgc_mcp.utils.validators import (
    VALID_ELO_BRACKETS,
    VALID_TERRAIN,
    VALID_WEATHER,
    ValidationError,
    validate_elo_bracket,
    validate_ev_spread,
    validate_format_code,
    validate_iv_spread,
    validate_level,
    validate_limit,
    validate_nature,
    validate_pokemon_list,
    validate_pokemon_name,
    validate_stat_boost,
    validate_stat_boosts,
    validate_terrain,
    validate_type_list,
    validate_type_name,
    validate_weather,
)


class TestValidationError:
    def test_error_with_message_only(self):
        err = ValidationError("Test error")
        assert err.message == "Test error"
        assert err.hint is None

    def test_error_with_hint(self):
        err = ValidationError("Test error", hint="Try this")
        assert err.message == "Test error"
        assert err.hint == "Try this"


class TestValidatePokemonName:
    def test_valid_pokemon(self):
        result = validate_pokemon_name("Incineroar")
        assert result == "Incineroar"

    def test_case_insensitive(self):
        result = validate_pokemon_name("INCINEROAR")
        assert result == "INCINEROAR"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_pokemon_name("")
        assert "cannot be empty" in exc.value.message

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_pokemon_name("   ")
        assert "cannot be empty" in exc.value.message

    def test_unknown_pokemon_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_pokemon_name("NotARealPokemon")
        assert "not found" in exc.value.message
        assert exc.value.hint is not None


class TestValidateTypeName:
    def test_valid_type(self):
        result = validate_type_name("Fire")
        assert result == "Fire"

    def test_normalizes_case(self):
        result = validate_type_name("fire")
        assert result == "Fire"

    def test_empty_type_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_type_name("")
        assert "cannot be empty" in exc.value.message

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_type_name("NotAType")
        assert "Invalid type" in exc.value.message
        assert exc.value.hint is not None


class TestValidateNature:
    def test_valid_nature(self):
        result = validate_nature("Adamant")
        assert result == "Adamant"

    def test_normalizes_case(self):
        result = validate_nature("adamant")
        assert result == "Adamant"

    def test_empty_nature_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_nature("")
        assert "cannot be empty" in exc.value.message

    def test_invalid_nature_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_nature("NotANature")
        assert "Invalid nature" in exc.value.message
        assert exc.value.hint is not None


class TestValidateFormatCode:
    def test_valid_format(self):
        result = validate_format_code("regf")
        assert result == "regf"

    def test_normalizes_case(self):
        result = validate_format_code("REGF")
        assert result == "regf"

    def test_empty_format_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_format_code("")
        assert "cannot be empty" in exc.value.message

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_format_code("notaformat")
        assert "Unknown format" in exc.value.message
        assert exc.value.hint is not None


class TestValidateWeather:
    def test_valid_weather(self):
        for weather in VALID_WEATHER:
            result = validate_weather(weather)
            assert result == weather

    def test_normalizes_case(self):
        result = validate_weather("sun")
        assert result == "Sun"

    def test_none_returns_none(self):
        result = validate_weather(None)
        assert result is None

    def test_empty_string_returns_none(self):
        result = validate_weather("")
        assert result is None

    def test_invalid_weather_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_weather("NotWeather")
        assert "Invalid weather" in exc.value.message


class TestValidateTerrain:
    def test_valid_terrain(self):
        for terrain in VALID_TERRAIN:
            result = validate_terrain(terrain)
            assert result == terrain

    def test_normalizes_case(self):
        result = validate_terrain("grassy")
        assert result == "Grassy"

    def test_none_returns_none(self):
        result = validate_terrain(None)
        assert result is None

    def test_empty_string_returns_none(self):
        result = validate_terrain("")
        assert result is None

    def test_invalid_terrain_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_terrain("NotTerrain")
        assert "Invalid terrain" in exc.value.message


class TestValidateEVSpread:
    def test_valid_compact_format(self):
        result = validate_ev_spread("252/4/0/0/0/252")
        assert result["hp"] == 252
        assert result["atk"] == 4
        assert result["spe"] == 252

    def test_valid_showdown_format(self):
        result = validate_ev_spread("252 HP / 252 SpA / 4 Spe")
        assert result["hp"] == 252
        assert result["spa"] == 252
        assert result["spe"] == 4

    def test_empty_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_ev_spread("")
        assert "cannot be empty" in exc.value.message

    def test_exceeds_252_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_ev_spread("300/0/0/0/0/0")
        assert "Invalid EV value" in exc.value.message

    def test_exceeds_510_total_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_ev_spread("252/252/252/0/0/0")
        assert "exceed maximum of 510" in exc.value.message


class TestValidateIVSpread:
    def test_valid_compact_format(self):
        result = validate_iv_spread("31/31/31/31/31/31")
        assert all(v == 31 for v in result.values())

    def test_valid_zero_attack(self):
        result = validate_iv_spread("31/0/31/31/31/31")
        assert result["atk"] == 0
        assert result["hp"] == 31

    def test_empty_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_iv_spread("")
        assert "cannot be empty" in exc.value.message

    def test_exceeds_31_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_iv_spread("31/35/31/31/31/31")
        assert "Invalid IV value" in exc.value.message


class TestValidateLevel:
    def test_valid_level(self):
        result = validate_level(50)
        assert result == 50

    def test_min_level(self):
        result = validate_level(1)
        assert result == 1

    def test_max_level(self):
        result = validate_level(100)
        assert result == 100

    def test_below_min_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_level(0)
        assert "Invalid level" in exc.value.message

    def test_above_max_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_level(101)
        assert "Invalid level" in exc.value.message

    def test_non_integer_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_level("50")
        assert "must be an integer" in exc.value.message


class TestValidateStatBoost:
    def test_valid_boost(self):
        result = validate_stat_boost(2)
        assert result == 2

    def test_negative_boost(self):
        result = validate_stat_boost(-1)
        assert result == -1

    def test_max_boost(self):
        result = validate_stat_boost(6)
        assert result == 6

    def test_min_boost(self):
        result = validate_stat_boost(-6)
        assert result == -6

    def test_exceeds_max_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_stat_boost(7)
        assert "Stat boosts must be -6 to +6" in exc.value.hint

    def test_below_min_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_stat_boost(-7)
        assert "Stat boosts must be -6 to +6" in exc.value.hint


class TestValidateEloBracket:
    def test_valid_brackets(self):
        for elo in VALID_ELO_BRACKETS:
            result = validate_elo_bracket(elo)
            assert result == elo

    def test_invalid_bracket_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_elo_bracket(1600)
        assert "Invalid ELO bracket" in exc.value.message


class TestValidateLimit:
    def test_valid_limit(self):
        result = validate_limit(10)
        assert result == 10

    def test_caps_at_max(self):
        result = validate_limit(100, max_limit=50)
        assert result == 50

    def test_zero_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_limit(0)
        assert "must be a positive integer" in exc.value.hint

    def test_negative_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_limit(-1)
        assert "must be a positive integer" in exc.value.hint


class TestValidatePokemonList:
    def test_valid_list(self):
        result = validate_pokemon_list(["Incineroar", "Flutter Mane"])
        assert len(result) == 2

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_pokemon_list([])
        assert "too short" in exc.value.message

    def test_exceeds_max_raises(self):
        pokemon = ["Incineroar"] * 7
        with pytest.raises(ValidationError) as exc:
            validate_pokemon_list(pokemon, max_size=6)
        assert "too long" in exc.value.message

    def test_invalid_pokemon_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_pokemon_list(["Incineroar", "NotARealPokemon"])
        assert "position 2" in exc.value.message


class TestValidateTypeList:
    def test_valid_list(self):
        result = validate_type_list(["Fire", "Water"])
        assert len(result) == 2

    def test_normalizes_types(self):
        result = validate_type_list(["fire", "water"])
        assert result == ["Fire", "Water"]

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_type_list([])
        assert "too short" in exc.value.message

    def test_exceeds_max_raises(self):
        types = ["Fire", "Water", "Grass", "Electric", "Ice"]
        with pytest.raises(ValidationError) as exc:
            validate_type_list(types, max_size=4)
        assert "too long" in exc.value.message


class TestValidateStatBoosts:
    def test_none_returns_none(self):
        result = validate_stat_boosts(None)
        assert result is None

    def test_valid_boosts(self):
        result = validate_stat_boosts({"atk": 1, "def": -1})
        assert result["atk"] == 1
        assert result["def"] == -1

    def test_invalid_stat_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_stat_boosts({"notastat": 1})
        assert "Invalid stat name" in exc.value.message

    def test_invalid_boost_value_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_stat_boosts({"atk": 10})
        assert "Stat boosts must be -6 to +6" in exc.value.hint
