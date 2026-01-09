"""Tests for fetcher/sheets.py - Google Sheets team data."""

import re
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTeamIdPattern:
    """Tests for team ID pattern matching."""

    def test_matches_valid_reg_f_team_ids(self):
        """Test matching valid Regulation F team IDs."""
        pattern = r"^F\d+$"

        valid_ids = ["F1", "F123", "F999", "F10"]
        for team_id in valid_ids:
            assert re.match(pattern, team_id), f"{team_id} should match"

    def test_rejects_invalid_team_ids(self):
        """Test rejecting invalid team IDs."""
        pattern = r"^F\d+$"

        invalid_ids = ["", "123", "F", "FF1", "F1a", "f123", " F1"]
        for team_id in invalid_ids:
            assert not re.match(pattern, team_id), f"{team_id} should not match"

    def test_different_format_prefixes(self):
        """Test different format prefixes."""
        # Each format has a different prefix
        patterns = {
            "regf": r"^F\d+$",
            "regg": r"^G\d+$",
        }

        assert re.match(patterns["regf"], "F123")
        assert not re.match(patterns["regf"], "G123")
        assert re.match(patterns["regg"], "G456")


class TestPokepasteUrlExtraction:
    """Tests for pokepaste URL extraction."""

    def test_extracts_pokepaste_url(self):
        """Test extracting pokepaste URL from cell."""
        cell = "https://pokepast.es/abc123def"
        match = re.search(r"https?://pokepast\.es/[a-zA-Z0-9]+", cell)

        assert match is not None
        assert match.group(0) == "https://pokepast.es/abc123def"

    def test_extracts_url_with_extra_content(self):
        """Test extracting URL when cell has extra content."""
        cell = "Team paste: https://pokepast.es/xyz789 (shared)"
        match = re.search(r"https?://pokepast\.es/[a-zA-Z0-9]+", cell)

        assert match is not None
        assert match.group(0) == "https://pokepast.es/xyz789"

    def test_handles_http_url(self):
        """Test handling HTTP URLs (should still match)."""
        cell = "http://pokepast.es/abc123"
        match = re.search(r"https?://pokepast\.es/[a-zA-Z0-9]+", cell)

        assert match is not None

    def test_no_match_for_invalid_urls(self):
        """Test no match for invalid URLs."""
        invalid_cells = [
            "pokepast.es/abc123",  # Missing protocol
            "https://pokepaste.com/abc",  # Wrong domain
            "https://pokepast.es/",  # Missing ID
        ]

        for cell in invalid_cells:
            match = re.search(r"https?://pokepast\.es/[a-zA-Z0-9]+", cell)
            assert match is None, f"Should not match: {cell}"


class TestRentalCodeExtraction:
    """Tests for rental code extraction."""

    def test_matches_valid_rental_codes(self):
        """Test matching valid rental codes."""
        valid_codes = ["ABC123", "XYZ789", "000000", "AAAAAA"]

        for code in valid_codes:
            assert re.match(r"^[A-Z0-9]{6}$", code), f"{code} should match"

    def test_rejects_invalid_rental_codes(self):
        """Test rejecting invalid rental codes."""
        invalid_codes = [
            "abc123",  # Lowercase
            "ABC12",  # Too short
            "ABC1234",  # Too long
            "ABC-123",  # Contains dash
            "",  # Empty
        ]

        for code in invalid_codes:
            assert not re.match(r"^[A-Z0-9]{6}$", code.strip()), f"{code} should not match"


class TestCSVParsing:
    """Tests for CSV row parsing logic."""

    def test_extracts_fields_from_row(self):
        """Test extracting fields from CSV row."""
        # Simulated row structure based on sheets.py
        row = ["F123", "Top 8 Worlds", "", "PlayerName", "ABC123", "https://pokepast.es/xyz"]

        team_id = row[0].strip()
        description = row[1].strip() if len(row) > 1 else ""
        owner = row[3].strip() if len(row) > 3 else ""

        assert team_id == "F123"
        assert description == "Top 8 Worlds"
        assert owner == "PlayerName"

    def test_handles_short_rows(self):
        """Test handling rows with missing fields."""
        row = ["F123"]

        team_id = row[0].strip()
        description = row[1].strip() if len(row) > 1 else ""
        owner = row[3].strip() if len(row) > 3 else ""

        assert team_id == "F123"
        assert description == ""
        assert owner == ""

    def test_handles_empty_row(self):
        """Test handling empty row."""
        row = []

        assert len(row) == 0 or not row


class TestStoreTeam:
    """Tests for store_team function."""

    @pytest.mark.asyncio
    async def test_store_team_returns_none_for_missing_id(self):
        """Test that store_team returns None when team_id is missing."""
        from smogon_vgc_mcp.fetcher.sheets import store_team

        mock_db = AsyncMock()

        team = {"description": "Test", "owner": "Player"}  # No team_id

        result = await store_team(mock_db, "regf", team)

        assert result is None
        # DB should not be called
        mock_db.execute.assert_not_called()


class TestStoreTeamPokemon:
    """Tests for store_team_pokemon function."""

    @pytest.mark.asyncio
    async def test_store_team_pokemon_clears_existing(self):
        """Test that store_team_pokemon clears existing Pokemon first."""
        from smogon_vgc_mcp.fetcher.sheets import store_team_pokemon

        mock_db = AsyncMock()

        # Create mock Pokemon
        mock_pokemon = MagicMock()
        mock_pokemon.slot = 1
        mock_pokemon.pokemon = "Incineroar"
        mock_pokemon.item = "Safety Goggles"
        mock_pokemon.ability = "Intimidate"
        mock_pokemon.tera_type = "Ghost"
        mock_pokemon.nature = "Careful"
        mock_pokemon.hp_ev = 252
        mock_pokemon.atk_ev = 4
        mock_pokemon.def_ev = 0
        mock_pokemon.spa_ev = 0
        mock_pokemon.spd_ev = 252
        mock_pokemon.spe_ev = 0
        mock_pokemon.hp_iv = 31
        mock_pokemon.atk_iv = 31
        mock_pokemon.def_iv = 31
        mock_pokemon.spa_iv = 31
        mock_pokemon.spd_iv = 31
        mock_pokemon.spe_iv = 31
        mock_pokemon.move1 = "Fake Out"
        mock_pokemon.move2 = "Knock Off"
        mock_pokemon.move3 = "Flare Blitz"
        mock_pokemon.move4 = "Parting Shot"

        await store_team_pokemon(mock_db, 42, [mock_pokemon])

        # Verify DELETE was called first
        calls = mock_db.execute.call_args_list
        assert len(calls) >= 2

        # First call should be DELETE
        first_call = calls[0]
        assert "DELETE" in str(first_call)

    @pytest.mark.asyncio
    async def test_store_team_pokemon_handles_empty_list(self):
        """Test that store_team_pokemon handles empty Pokemon list."""
        from smogon_vgc_mcp.fetcher.sheets import store_team_pokemon

        mock_db = AsyncMock()

        await store_team_pokemon(mock_db, 42, [])

        # Should only call DELETE, no INSERT
        assert mock_db.execute.call_count == 1
