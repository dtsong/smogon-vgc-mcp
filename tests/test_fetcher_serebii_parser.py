"""Tests for fetcher/champions_dex.py — Serebii Champions HTML parser."""

from smogon_vgc_mcp.fetcher.champions_dex import parse_serebii_pokemon_page

# ---------------------------------------------------------------------------
# HTML fixtures: minimal but realistic fragments modelled after the real
# Serebii Champions Pokedex HTML structure (dextable/fooinfo/fooleft classes).
# ---------------------------------------------------------------------------

CHARIZARD_HTML = """
<!DOCTYPE html>
<html>
<head><title>Charizard - Pokemon Champions Pokédex</title></head>
<body>
<h1>#006 Charizard</h1>
<table class="dextable">
  <tr>
    <td class="fooinfo">#006</td>
  </tr>
  <tr>
    <td class="cen">
      <img class="typeimg" alt="Fire-type">
      <img class="typeimg" alt="Flying-type">
    </td>
  </tr>
  <tr>
    <td class="fooleft">Abilities: <a>Blaze</a> <a>Solar Power</a></td>
  </tr>
  <tr>
    <td class="fooinfo">1.7m / 5'07"</td>
    <td class="fooinfo">90.5kg / 199.5 lbs</td>
  </tr>
  <tr>
    <td class="fooinfo">Base Stats - Total: 534</td>
    <td class="fooinfo">78</td>
    <td class="fooinfo">84</td>
    <td class="fooinfo">78</td>
    <td class="fooinfo">109</td>
    <td class="fooinfo">85</td>
    <td class="fooinfo">100</td>
  </tr>
</table>
</body>
</html>
"""

CHARIZARD_WITH_MEGA_HTML = """
<!DOCTYPE html>
<html>
<head><title>Charizard - Pokemon Champions Pokédex</title></head>
<body>
<h1>#006 Charizard</h1>
<table class="dextable">
  <tr>
    <td class="fooinfo">#006</td>
  </tr>
  <tr>
    <td class="cen">
      <img class="typeimg" alt="Fire-type">
      <img class="typeimg" alt="Flying-type">
    </td>
  </tr>
  <tr>
    <td class="fooleft">Abilities: <a>Blaze</a> <a>Solar Power</a></td>
  </tr>
  <tr>
    <td class="fooinfo">1.7m / 5'07"</td>
    <td class="fooinfo">90.5kg / 199.5 lbs</td>
  </tr>
  <tr>
    <td class="fooinfo">Base Stats - Total: 534</td>
    <td class="fooinfo">78</td>
    <td class="fooinfo">84</td>
    <td class="fooinfo">78</td>
    <td class="fooinfo">109</td>
    <td class="fooinfo">85</td>
    <td class="fooinfo">100</td>
  </tr>
</table>
<a name="mega"></a>
<table class="dextable">
  <tr>
    <td class="fooevo"><h3>Mega Charizard X</h3></td>
  </tr>
  <tr>
    <td class="cen">
      <img src="/type/fire.gif">
      <img src="/type/dragon.gif">
    </td>
  </tr>
  <tr>
    <td class="fooleft">Abilities: <a>Tough Claws</a></td>
  </tr>
  <tr>
    <td class="fooinfo">Base Stats - Total: 634</td>
    <td class="fooinfo">78</td>
    <td class="fooinfo">130</td>
    <td class="fooinfo">111</td>
    <td class="fooinfo">130</td>
    <td class="fooinfo">85</td>
    <td class="fooinfo">100</td>
  </tr>
</table>
</body>
</html>
"""

VENUSAUR_HTML = """
<!DOCTYPE html>
<html>
<head><title>Venusaur - Pokemon Champions Pokédex</title></head>
<body>
<h1>#003 Venusaur</h1>
<table class="dextable">
  <tr>
    <td class="fooinfo">#003</td>
  </tr>
  <tr>
    <td class="cen">
      <img class="typeimg" alt="Grass-type">
      <img class="typeimg" alt="Poison-type">
    </td>
  </tr>
  <tr>
    <td class="fooleft">Abilities: <a>Overgrow</a></td>
  </tr>
  <tr>
    <td class="fooinfo">2.0m / 6'07"</td>
    <td class="fooinfo">100.0kg / 220.5 lbs</td>
  </tr>
  <tr>
    <td class="fooinfo">Base Stats - Total: 525</td>
    <td class="fooinfo">80</td>
    <td class="fooinfo">82</td>
    <td class="fooinfo">83</td>
    <td class="fooinfo">100</td>
    <td class="fooinfo">100</td>
    <td class="fooinfo">80</td>
  </tr>
</table>
</body>
</html>
"""

SINGLE_TYPE_HTML = """
<!DOCTYPE html>
<html>
<body>
<h1>#143 Snorlax</h1>
<table class="dextable">
  <tr>
    <td class="fooinfo">#143</td>
  </tr>
  <tr>
    <td class="cen">
      <img class="typeimg" alt="Normal-type">
    </td>
  </tr>
  <tr>
    <td class="fooleft">Abilities: <a>Immunity</a> <a>Thick Fat</a></td>
  </tr>
  <tr>
    <td class="fooinfo">2.1m / 6'11"</td>
    <td class="fooinfo">460.0kg / 1014.1 lbs</td>
  </tr>
  <tr>
    <td class="fooinfo">Base Stats - Total: 540</td>
    <td class="fooinfo">160</td>
    <td class="fooinfo">110</td>
    <td class="fooinfo">65</td>
    <td class="fooinfo">65</td>
    <td class="fooinfo">110</td>
    <td class="fooinfo">30</td>
  </tr>
</table>
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
        assert "Fire" in result["types"]
        assert "Flying" in result["types"]

    def test_base_stats_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        stats = result["base_stats"]
        assert stats["hp"] == 78
        assert stats["atk"] == 84
        assert stats["def"] == 78
        assert stats["spa"] == 109
        assert stats["spd"] == 85
        assert stats["spe"] == 100

    def test_abilities_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert "Blaze" in result["abilities"]
        assert "Solar Power" in result["abilities"]
        assert result["ability_hidden"] is None

    def test_height_weight_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["height_m"] == 1.7
        assert result["weight_kg"] == 90.5

    def test_no_mega_forms_for_base_without_megas(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["mega_forms"] == []

    def test_id_matches_slug(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert result["id"] == "charizard"


class TestParseMegaPokemon:
    """Tests for pages with Mega Evolution forms embedded."""

    def test_mega_form_found(self):
        result = parse_serebii_pokemon_page(CHARIZARD_WITH_MEGA_HTML, "charizard")
        assert len(result["mega_forms"]) >= 1

    def test_mega_name_extracted(self):
        result = parse_serebii_pokemon_page(CHARIZARD_WITH_MEGA_HTML, "charizard")
        mega = result["mega_forms"][0]
        assert "Charizard" in mega["name"]

    def test_mega_types_differ_from_base(self):
        result = parse_serebii_pokemon_page(CHARIZARD_WITH_MEGA_HTML, "charizard")
        mega = result["mega_forms"][0]
        assert "Dragon" in mega["types"]

    def test_mega_stats_higher_than_base(self):
        result = parse_serebii_pokemon_page(CHARIZARD_WITH_MEGA_HTML, "charizard")
        mega = result["mega_forms"][0]
        assert mega["stats"]["atk"] == 130
        assert mega["stats"]["def"] == 111

    def test_mega_slug_contains_base(self):
        result = parse_serebii_pokemon_page(CHARIZARD_WITH_MEGA_HTML, "charizard")
        mega = result["mega_forms"][0]
        assert "charizard" in mega["slug"]
        assert "mega" in mega["slug"]


class TestSingleType:
    """Tests for single-type Pokemon."""

    def test_single_type_parsed(self):
        result = parse_serebii_pokemon_page(SINGLE_TYPE_HTML, "snorlax")
        assert result["types"] == ["Normal"]

    def test_snorlax_stats(self):
        result = parse_serebii_pokemon_page(SINGLE_TYPE_HTML, "snorlax")
        assert result["base_stats"]["hp"] == 160
        assert result["base_stats"]["spe"] == 30

    def test_snorlax_two_regular_abilities(self):
        result = parse_serebii_pokemon_page(SINGLE_TYPE_HTML, "snorlax")
        assert "Immunity" in result["abilities"]
        assert "Thick Fat" in result["abilities"]


class TestMissingStats:
    """Tests for error/missing-data pages."""

    def test_returns_none_on_no_dextable(self):
        result = parse_serebii_pokemon_page(MISSING_STATS_HTML, "unknown")
        assert result is None


class TestReturnSchema:
    """Tests that the returned dict has all expected keys."""

    EXPECTED_KEYS = {
        "id",
        "num",
        "name",
        "types",
        "base_stats",
        "abilities",
        "ability_hidden",
        "height_m",
        "weight_kg",
        "mega_forms",
    }

    def test_all_keys_present(self):
        result = parse_serebii_pokemon_page(CHARIZARD_HTML, "charizard")
        assert self.EXPECTED_KEYS <= set(result.keys())
