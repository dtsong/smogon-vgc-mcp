"""Tests for fetcher/serebii_parser.py — Serebii Champions HTML parser."""

import pytest

from smogon_vgc_mcp.fetcher.serebii_parser import parse_serebii_pokemon_page


# ---------------------------------------------------------------------------
# HTML fixtures: minimal but realistic fragments modelled after Serebii's
# structure. Each fixture covers the key extraction targets.
# ---------------------------------------------------------------------------

CHARIZARD_HTML = """
<!DOCTYPE html>
<html>
<head><title>Charizard - Pokemon Champions Pokédex</title></head>
<body>
<h1>Charizard</h1>
<p>No. 006</p>
<table>
  <tr>
    <td><a href="/type/fire.shtml"><img src="/pokedex-bw/type/fire.png" alt="Fire Type"></a></td>
    <td><a href="/type/flying.shtml"><img src="/pokedex-bw/type/flying.png" alt="Flying Type"></a></td>
  </tr>
</table>
<table>
  <tr><td>HP</td><td>78</td></tr>
  <tr><td>Attack</td><td>84</td></tr>
  <tr><td>Defense</td><td>78</td></tr>
  <tr><td>Sp. Atk</td><td>109</td></tr>
  <tr><td>Sp. Def</td><td>85</td></tr>
  <tr><td>Speed</td><td>100</td></tr>
</table>
<p>Abilities: Blaze | Solar Power</p>
<p>Height: 1.70m</p>
<p>Weight: 90.5kg</p>
<p>Mega Evolutions:</p>
<a href="/champions/pokemon/charizard-mega-x.shtml">Mega Charizard X</a>
<a href="/champions/pokemon/charizard-mega-y.shtml">Mega Charizard Y</a>
</body>
</html>
"""

CHARIZARD_MEGA_X_HTML = """
<!DOCTYPE html>
<html>
<head><title>Charizard Mega X - Pokemon Champions Pokédex</title></head>
<body>
<h1>Mega Charizard X</h1>
<p>No. 006</p>
<table>
  <tr>
    <td><a href="/type/fire.shtml"><img src="/type/fire.png" alt="Fire Type"></a></td>
    <td><a href="/type/dragon.shtml"><img src="/type/dragon.png" alt="Dragon Type"></a></td>
  </tr>
</table>
<table>
  <tr><td>HP</td><td>78</td></tr>
  <tr><td>Attack</td><td>130</td></tr>
  <tr><td>Defense</td><td>111</td></tr>
  <tr><td>Sp. Atk</td><td>130</td></tr>
  <tr><td>Sp. Def</td><td>85</td></tr>
  <tr><td>Speed</td><td>100</td></tr>
</table>
<p>Abilities: Tough Claws</p>
<p>Mega Stone: Charizardite X</p>
<p>Height: 1.70m</p>
<p>Weight: 110.5kg</p>
</body>
</html>
"""

VENUSAUR_HTML = """
<!DOCTYPE html>
<html>
<head><title>Venusaur - Pokemon Champions Pokédex</title></head>
<body>
<h1>Venusaur</h1>
<p>No. 003</p>
<table>
  <tr>
    <td><a href="/type/grass.shtml"><img src="/type/grass.png" alt="Grass Type"></a></td>
    <td><a href="/type/poison.shtml"><img src="/type/poison.png" alt="Poison Type"></a></td>
  </tr>
</table>
<table>
  <tr><td>HP</td><td>80</td></tr>
  <tr><td>Attack</td><td>82</td></tr>
  <tr><td>Defense</td><td>83</td></tr>
  <tr><td>Sp. Atk</td><td>100</td></tr>
  <tr><td>Sp. Def</td><td>100</td></tr>
  <tr><td>Speed</td><td>80</td></tr>
</table>
<p>Abilities: Overgrow</p>
<p>Hidden Ability: Chlorophyll</p>
<p>Height: 2.00m</p>
<p>Weight: 100.0kg</p>
<a href="/champions/pokemon/venusaur-mega.shtml">Mega Venusaur</a>
</body>
</html>
"""

SINGLE_TYPE_HTML = """
<!DOCTYPE html>
<html>
<body>
<h1>Snorlax</h1>
<p>No. 143</p>
<table>
  <tr>
    <td><a href="/type/normal.shtml"><img src="/type/normal.png" alt="Normal Type"></a></td>
  </tr>
</table>
<table>
  <tr><td>HP</td><td>160</td></tr>
  <tr><td>Attack</td><td>110</td></tr>
  <tr><td>Defense</td><td>65</td></tr>
  <tr><td>Sp. Atk</td><td>65</td></tr>
  <tr><td>Sp. Def</td><td>110</td></tr>
  <tr><td>Speed</td><td>30</td></tr>
</table>
<p>Abilities: Immunity | Thick Fat</p>
<p>Height: 2.10m</p>
<p>Weight: 460.0kg</p>
</body>
</html>
"""

MISSING_STATS_HTML = """
<!DOCTYPE html>
<html>
<body>
<h1>Error Page</h1>
<p>Page not found.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseBasePokemon:
    """Tests for base-form Pokemon pages."""

    def test_name_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["name"] == "Charizard"

    def test_dex_number_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["num"] == 6

    def test_types_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["type1"] == "Fire"
        assert result["type2"] == "Flying"

    def test_base_stats_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["hp"] == 78
        assert result["atk"] == 84
        assert result["def"] == 78
        assert result["spa"] == 109
        assert result["spd"] == 85
        assert result["spe"] == 100

    def test_abilities_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["ability1"] == "Blaze"
        assert result["ability2"] == "Solar Power"
        assert result["ability_hidden"] is None

    def test_height_weight_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["height_m"] == 1.7
        assert result["weight_kg"] == 90.5

    def test_is_mega_false_for_base(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["is_mega"] is False

    def test_base_form_id_none_for_base(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["base_form_id"] is None

    def test_mega_links_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert "charizard-mega-x" in result["mega_links"]
        assert "charizard-mega-y" in result["mega_links"]

    def test_id_matches_slug(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["id"] == "charizard"


class TestParseMegaPokemon:
    """Tests for Mega Evolution form pages."""

    def test_mega_name_extracted(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert "Charizard" in result["name"]

    def test_mega_types_differ_from_base(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert result["type1"] == "Fire"
        assert result["type2"] == "Dragon"

    def test_mega_stats_higher_than_base(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert result["atk"] == 130
        assert result["def"] == 111

    def test_is_mega_true(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert result["is_mega"] is True

    def test_base_form_id_set(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert result["base_form_id"] == "charizard"

    def test_mega_stone_extracted_from_text(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert result["mega_stone"] == "Charizardite X"

    def test_mega_links_empty_for_mega_form(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert result["mega_links"] == []


class TestParseHiddenAbility:
    """Tests for Pokemon with a hidden ability."""

    def test_hidden_ability_extracted(self):
        result = parse_serebii_pokemon_page(VENUSAUR_HTML, "venusaur")
        assert result["ability_hidden"] == "Chlorophyll"

    def test_regular_ability_not_duplicated_in_hidden(self):
        result = parse_serebii_pokemon_page(VENUSAUR_HTML, "venusaur")
        assert result["ability1"] == "Overgrow"
        assert result["ability2"] is None  # only one regular ability

    def test_venusaur_mega_link(self):
        result = parse_serebii_pokemon_page(VENUSAUR_HTML, "venusaur")
        assert "venusaur-mega" in result["mega_links"]


class TestSingleType:
    """Tests for single-type Pokemon."""

    def test_single_type_parsed(self):
        result = parse_serebii_pokemon_page(SINGLE_TYPE_HTML, "snorlax")
        assert result["type1"] == "Normal"
        assert result["type2"] is None

    def test_snorlax_stats(self):
        result = parse_serebii_pokemon_page(SINGLE_TYPE_HTML, "snorlax")
        assert result["hp"] == 160
        assert result["spe"] == 30

    def test_snorlax_two_regular_abilities(self):
        result = parse_serebii_pokemon_page(SINGLE_TYPE_HTML, "snorlax")
        assert result["ability1"] == "Immunity"
        assert result["ability2"] == "Thick Fat"


class TestMissingStats:
    """Tests for error/missing-data pages."""

    def test_raises_on_no_stats(self):
        with pytest.raises(ValueError, match="No stat data found"):
            parse_serebii_pokemon_page(MISSING_STATS_HTML, "unknown")


class TestReturnSchema:
    """Tests that the returned dict has all expected keys."""

    EXPECTED_KEYS = {
        "id", "num", "name", "type1", "type2",
        "hp", "atk", "def", "spa", "spd", "spe",
        "ability1", "ability2", "ability_hidden",
        "base_form_id", "is_mega", "mega_stone",
        "height_m", "weight_kg", "mega_links",
    }

    def test_all_keys_present(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert self.EXPECTED_KEYS <= set(result.keys())

    def test_all_keys_present_mega(self):
        result = parse_serebii_pokemon_page(
            CHARIZARD_MEGA_X_HTML, "charizard-mega-x",
            is_mega=True, base_form_id="charizard"
        )
        assert self.EXPECTED_KEYS <= set(result.keys())
