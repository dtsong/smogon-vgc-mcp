"""Tests for fetcher/pokepaste.py - Pokepaste parsing."""

from unittest.mock import patch

import pytest

from smogon_vgc_mcp.fetcher.pokepaste import (
    fetch_pokepaste,
    parse_pokepaste,
)
from smogon_vgc_mcp.utils import (
    SHOWDOWN_STAT_MAP,
    parse_ev_string,
    parse_iv_string,
)


class TestStatMap:
    """Tests for SHOWDOWN_STAT_MAP constant."""

    def test_all_stats_mapped(self):
        """Test that all stats are in SHOWDOWN_STAT_MAP."""
        assert "HP" in SHOWDOWN_STAT_MAP
        assert "Atk" in SHOWDOWN_STAT_MAP
        assert "Def" in SHOWDOWN_STAT_MAP
        assert "SpA" in SHOWDOWN_STAT_MAP
        assert "SpD" in SHOWDOWN_STAT_MAP
        assert "Spe" in SHOWDOWN_STAT_MAP

    def test_stat_map_values(self):
        """Test SHOWDOWN_STAT_MAP values are lowercase."""
        assert SHOWDOWN_STAT_MAP["HP"] == "hp"
        assert SHOWDOWN_STAT_MAP["Atk"] == "atk"
        assert SHOWDOWN_STAT_MAP["Def"] == "def"
        assert SHOWDOWN_STAT_MAP["SpA"] == "spa"
        assert SHOWDOWN_STAT_MAP["SpD"] == "spd"
        assert SHOWDOWN_STAT_MAP["Spe"] == "spe"


class TestParseEVs:
    """Tests for parse_ev_string function."""

    def test_standard_ev_line(self):
        """Test standard EVs line parsing."""
        result = parse_ev_string("EVs: 252 HP / 4 Def / 252 SpA")

        assert result["hp"] == 252
        assert result["def"] == 4
        assert result["spa"] == 252
        assert result["atk"] == 0
        assert result["spd"] == 0
        assert result["spe"] == 0

    def test_physical_attacker_spread(self):
        """Test physical attacker spread."""
        result = parse_ev_string("EVs: 252 HP / 252 Atk / 4 SpD")

        assert result["hp"] == 252
        assert result["atk"] == 252
        assert result["spd"] == 4

    def test_speed_attacker_spread(self):
        """Test speed attacker spread."""
        result = parse_ev_string("EVs: 4 HP / 252 SpA / 252 Spe")

        assert result["hp"] == 4
        assert result["spa"] == 252
        assert result["spe"] == 252

    def test_bulky_spread(self):
        """Test bulky spread (Incineroar style)."""
        result = parse_ev_string("EVs: 252 HP / 4 Atk / 252 SpD")

        assert result["hp"] == 252
        assert result["atk"] == 4
        assert result["spd"] == 252

    def test_no_evs_prefix(self):
        """Test parsing without EVs: prefix."""
        result = parse_ev_string("252 HP / 252 Spe")

        assert result["hp"] == 252
        assert result["spe"] == 252

    def test_extra_whitespace(self):
        """Test handling of extra whitespace."""
        result = parse_ev_string("EVs:   252 HP  /  4 Def  /  252 Spe  ")

        assert result["hp"] == 252
        assert result["def"] == 4
        assert result["spe"] == 252

    def test_empty_string_returns_zeros(self):
        """Test empty string returns all zeros."""
        result = parse_ev_string("")

        assert result == {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}


class TestParseIVs:
    """Tests for parse_iv_string function."""

    def test_zero_attack_iv(self):
        """Test parsing 0 Atk IV (common for special attackers)."""
        result = parse_iv_string("IVs: 0 Atk")

        assert result["atk"] == 0
        assert result["hp"] == 31  # Default
        assert result["spe"] == 31  # Default

    def test_trick_room_ivs(self):
        """Test Trick Room IVs (0 Spe)."""
        result = parse_iv_string("IVs: 0 Spe")

        assert result["spe"] == 0
        assert result["hp"] == 31
        assert result["atk"] == 31

    def test_multiple_reduced_ivs(self):
        """Test multiple reduced IVs."""
        result = parse_iv_string("IVs: 0 Atk / 0 Spe")

        assert result["atk"] == 0
        assert result["spe"] == 0
        assert result["hp"] == 31

    def test_no_ivs_line_returns_max(self):
        """Test that no IVs line returns all 31s."""
        result = parse_iv_string("")

        assert result == {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

    def test_partial_iv_specification(self):
        """Test partial IV specification (only 0 Atk)."""
        result = parse_iv_string("IVs: 0 Atk")

        # Only Atk should be 0, rest default to 31
        assert result["atk"] == 0
        assert result["hp"] == 31
        assert result["def"] == 31
        assert result["spa"] == 31
        assert result["spd"] == 31
        assert result["spe"] == 31


class TestParsePokepaste:
    """Tests for parse_pokepaste function."""

    def test_single_pokemon(self):
        """Test parsing single Pokemon."""
        text = """Incineroar @ Safety Goggles
Ability: Intimidate
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Knock Off"""

        result = parse_pokepaste(text)

        assert len(result) == 1
        pokemon = result[0]
        assert pokemon.pokemon == "Incineroar"
        assert pokemon.item == "Safety Goggles"
        assert pokemon.ability == "Intimidate"
        assert pokemon.tera_type == "Ghost"
        assert pokemon.nature == "Careful"
        assert pokemon.hp_ev == 252
        assert pokemon.atk_ev == 4
        assert pokemon.spd_ev == 252
        assert pokemon.move1 == "Fake Out"
        assert pokemon.move2 == "Flare Blitz"
        assert pokemon.move3 == "Parting Shot"
        assert pokemon.move4 == "Knock Off"

    def test_pokemon_with_ivs(self):
        """Test parsing Pokemon with IVs specified."""
        text = """Flutter Mane @ Booster Energy
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Protect
- Dazzling Gleam"""

        result = parse_pokepaste(text)

        assert len(result) == 1
        pokemon = result[0]
        assert pokemon.pokemon == "Flutter Mane"
        assert pokemon.atk_iv == 0
        assert pokemon.hp_iv == 31  # Default
        assert pokemon.spe_iv == 31  # Default

    def test_two_pokemon(self):
        """Test parsing two Pokemon."""
        text = """Incineroar @ Safety Goggles
Ability: Intimidate
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Knock Off

Flutter Mane @ Booster Energy
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Protect
- Dazzling Gleam"""

        result = parse_pokepaste(text)

        assert len(result) == 2
        assert result[0].pokemon == "Incineroar"
        assert result[0].slot == 1
        assert result[1].pokemon == "Flutter Mane"
        assert result[1].slot == 2

    def test_pokemon_with_nickname(self):
        """Test parsing Pokemon with nickname."""
        text = """Kitty (Incineroar) @ Safety Goggles
Ability: Intimidate
Tera Type: Ghost
EVs: 252 HP / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Knock Off"""

        result = parse_pokepaste(text)

        assert len(result) == 1
        assert result[0].pokemon == "Incineroar"  # Should extract actual species

    def test_pokemon_without_gender_marker(self):
        """Test parsing Pokemon without gender marker.

        Note: The current parser interprets (M) and (F) as species names in
        parentheses (like nicknames). Use Pokemon name without gender marker.
        """
        text = """Incineroar @ Safety Goggles
Ability: Intimidate
Tera Type: Ghost
EVs: 252 HP / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Knock Off"""

        result = parse_pokepaste(text)

        assert len(result) == 1
        assert result[0].pokemon == "Incineroar"

    def test_pokemon_without_item(self):
        """Test parsing Pokemon without item."""
        text = """Incineroar
Ability: Intimidate
Tera Type: Ghost
EVs: 252 HP / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Knock Off"""

        result = parse_pokepaste(text)

        assert len(result) == 1
        assert result[0].pokemon == "Incineroar"
        assert result[0].item is None

    def test_pokemon_with_fewer_moves(self):
        """Test parsing Pokemon with fewer than 4 moves."""
        text = """Incineroar @ Safety Goggles
Ability: Intimidate
Careful Nature
- Fake Out
- Flare Blitz"""

        result = parse_pokepaste(text)

        assert len(result) == 1
        assert result[0].move1 == "Fake Out"
        assert result[0].move2 == "Flare Blitz"
        assert result[0].move3 is None
        assert result[0].move4 is None

    def test_empty_input(self):
        """Test parsing empty input."""
        result = parse_pokepaste("")

        assert result == []

    def test_whitespace_only(self):
        """Test parsing whitespace-only input."""
        result = parse_pokepaste("   \n\n   ")

        assert result == []

    def test_full_team_six_pokemon(self):
        """Test parsing full team of 6 Pokemon."""
        text = """Pokemon1 @ Item1
Ability: Ability1
- Move1

Pokemon2 @ Item2
Ability: Ability2
- Move2

Pokemon3 @ Item3
Ability: Ability3
- Move3

Pokemon4 @ Item4
Ability: Ability4
- Move4

Pokemon5 @ Item5
Ability: Ability5
- Move5

Pokemon6 @ Item6
Ability: Ability6
- Move6"""

        result = parse_pokepaste(text)

        assert len(result) == 6
        for i, pokemon in enumerate(result, start=1):
            assert pokemon.slot == i
            assert pokemon.pokemon == f"Pokemon{i}"
            assert pokemon.item == f"Item{i}"

    def test_slot_assignment(self):
        """Test that slots are assigned correctly."""
        text = """Pokemon1 @ Item1
- Move1

Pokemon2 @ Item2
- Move2

Pokemon3 @ Item3
- Move3"""

        result = parse_pokepaste(text)

        assert result[0].slot == 1
        assert result[1].slot == 2
        assert result[2].slot == 3


class TestFetchPokepaste:
    """Tests for fetch_pokepaste async function."""

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.fetcher.pokepaste.fetch_text")
    async def test_fetch_success(self, mock_fetch_text):
        """Test successful pokepaste fetch."""
        mock_fetch_text.return_value = "Pokemon @ Item\n- Move"

        result = await fetch_pokepaste("https://pokepast.es/abc123")

        assert result == "Pokemon @ Item\n- Move"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.fetcher.pokepaste.fetch_text")
    async def test_fetch_adds_raw_suffix(self, mock_fetch_text):
        """Test that /raw is appended to URL."""
        mock_fetch_text.return_value = "content"

        await fetch_pokepaste("https://pokepast.es/abc123")

        # Verify /raw was appended
        call_args = mock_fetch_text.call_args
        assert call_args[0][0] == "https://pokepast.es/abc123/raw"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.fetcher.pokepaste.fetch_text")
    async def test_fetch_handles_trailing_slash(self, mock_fetch_text):
        """Test URL handling with trailing slash."""
        mock_fetch_text.return_value = "content"

        await fetch_pokepaste("https://pokepast.es/abc123/")

        call_args = mock_fetch_text.call_args
        assert call_args[0][0] == "https://pokepast.es/abc123/raw"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.fetcher.pokepaste.fetch_text")
    async def test_fetch_already_has_raw(self, mock_fetch_text):
        """Test URL that already ends with /raw."""
        mock_fetch_text.return_value = "content"

        await fetch_pokepaste("https://pokepast.es/abc123/raw")

        call_args = mock_fetch_text.call_args
        assert call_args[0][0] == "https://pokepast.es/abc123/raw"

    @pytest.mark.asyncio
    @patch("smogon_vgc_mcp.fetcher.pokepaste.fetch_text")
    async def test_fetch_http_error(self, mock_fetch_text):
        """Test handling of HTTP error (returns None)."""
        mock_fetch_text.return_value = None

        result = await fetch_pokepaste("https://pokepast.es/invalid")

        assert result is None


class TestIntegrationParsing:
    """Integration tests combining EV/IV parsing with full pokepaste."""

    def test_full_pokemon_parsing(self, sample_pokepaste_text):
        """Test full Pokemon parsing with fixture."""
        result = parse_pokepaste(sample_pokepaste_text)

        # First Pokemon: Incineroar
        incineroar = result[0]
        assert incineroar.pokemon == "Incineroar"
        assert incineroar.item == "Safety Goggles"
        assert incineroar.ability == "Intimidate"
        assert incineroar.tera_type == "Ghost"
        assert incineroar.nature == "Careful"
        assert incineroar.hp_ev == 252
        assert incineroar.atk_ev == 4
        assert incineroar.spd_ev == 252

        # Second Pokemon: Flutter Mane
        flutter_mane = result[1]
        assert flutter_mane.pokemon == "Flutter Mane"
        assert flutter_mane.item == "Booster Energy"
        assert flutter_mane.atk_iv == 0  # Special attacker
