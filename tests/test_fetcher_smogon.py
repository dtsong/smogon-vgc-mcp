"""Tests for fetcher/smogon.py - Smogon stats parsing."""


class TestParseSpread:
    """Tests for parse_spread function."""

    def test_parses_valid_spread(self):
        """Test parsing a valid spread string."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        result = parse_spread("Careful:252/4/140/0/76/36")

        assert result is not None
        assert result["nature"] == "Careful"
        assert result["hp"] == 252
        assert result["atk"] == 4
        assert result["def"] == 140
        assert result["spa"] == 0
        assert result["spd"] == 76
        assert result["spe"] == 36

    def test_parses_max_hp_speed(self):
        """Test parsing common max HP/Speed spread."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        result = parse_spread("Timid:4/0/0/252/0/252")

        assert result is not None
        assert result["nature"] == "Timid"
        assert result["hp"] == 4
        assert result["atk"] == 0
        assert result["def"] == 0
        assert result["spa"] == 252
        assert result["spd"] == 0
        assert result["spe"] == 252

    def test_parses_all_natures(self):
        """Test parsing various nature names."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        natures = [
            "Adamant",
            "Jolly",
            "Modest",
            "Timid",
            "Brave",
            "Quiet",
            "Bold",
            "Impish",
            "Calm",
            "Careful",
            "Sassy",
            "Relaxed",
            "Naive",
            "Hasty",
            "Hardy",
        ]

        for nature in natures:
            spread = f"{nature}:252/4/0/0/0/252"
            result = parse_spread(spread)
            assert result is not None
            assert result["nature"] == nature

    def test_returns_none_for_invalid_format(self):
        """Test returning None for invalid format."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        # Missing nature
        assert parse_spread("252/4/0/0/0/252") is None

        # Wrong delimiter
        assert parse_spread("Adamant-252/4/0/0/0/252") is None

        # Missing EV values
        assert parse_spread("Adamant:252/4/0") is None

        # Non-numeric EVs
        assert parse_spread("Adamant:abc/4/0/0/0/252") is None

    def test_returns_none_for_empty_string(self):
        """Test returning None for empty string."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        assert parse_spread("") is None

    def test_handles_zero_evs(self):
        """Test handling spreads with all zero EVs."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        result = parse_spread("Serious:0/0/0/0/0/0")

        assert result is not None
        assert result["nature"] == "Serious"
        assert all(result[stat] == 0 for stat in ["hp", "atk", "def", "spa", "spd", "spe"])

    def test_handles_max_evs(self):
        """Test handling maximum EV investment."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        result = parse_spread("Adamant:252/252/0/0/4/0")

        assert result is not None
        assert result["hp"] == 252
        assert result["atk"] == 252
        assert result["spd"] == 4


class TestSmogonDataStructure:
    """Tests for understanding Smogon data structure."""

    def test_spread_total_evs_should_not_exceed_508(self):
        """Test that EV spreads are valid (total <= 508)."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        # Valid common spreads
        spreads = [
            "Careful:252/4/0/0/252/0",  # 508
            "Timid:4/0/0/252/0/252",  # 508
            "Adamant:252/252/4/0/0/0",  # 508
            "Bold:252/0/252/4/0/0",  # 508
            "Modest:0/0/0/252/4/252",  # 508
        ]

        for spread_str in spreads:
            result = parse_spread(spread_str)
            assert result is not None
            total = sum(
                [
                    result["hp"],
                    result["atk"],
                    result["def"],
                    result["spa"],
                    result["spd"],
                    result["spe"],
                ]
            )
            # EVs should not exceed 508 (though Smogon data might have edge cases)
            assert total <= 508

    def test_spread_individual_evs_should_not_exceed_252(self):
        """Test that individual EVs don't exceed 252."""
        from smogon_vgc_mcp.fetcher.smogon import parse_spread

        # This is a valid spread
        result = parse_spread("Adamant:252/252/4/0/0/0")
        assert result is not None

        for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            assert result[stat] <= 252
