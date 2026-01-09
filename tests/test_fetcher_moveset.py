"""Tests for fetcher/moveset.py - Moveset data parsing."""


class TestParsePokemonBlocks:
    """Tests for parse_pokemon_blocks function."""

    def test_parses_single_pokemon(self):
        """Test parsing a single Pokemon block."""
        from smogon_vgc_mcp.fetcher.moveset import parse_pokemon_blocks

        text = """
 +----------------------------------------+
 | Flutter Mane                           |
 +----------------------------------------+
 | Raw count: 50000                       |
 | Abilities                              |
 | Protosynthesis 100.0%                  |
 +----------------------------------------+
        """

        blocks = parse_pokemon_blocks(text)

        assert len(blocks) == 1
        assert blocks[0][0] == "Flutter Mane"
        assert "Raw count" in blocks[0][1]

    def test_parses_multiple_pokemon(self):
        """Test parsing multiple Pokemon blocks."""
        from smogon_vgc_mcp.fetcher.moveset import parse_pokemon_blocks

        text = """
 +----------------------------------------+
 | Flutter Mane                           |
 +----------------------------------------+
 | Stats for Flutter Mane                 |
 +----------------------------------------+
 | Incineroar                             |
 +----------------------------------------+
 | Stats for Incineroar                   |
 +----------------------------------------+
 | Raging Bolt                            |
 +----------------------------------------+
 | Stats for Raging Bolt                  |
        """

        blocks = parse_pokemon_blocks(text)

        assert len(blocks) == 3
        pokemon_names = [b[0] for b in blocks]
        assert "Flutter Mane" in pokemon_names
        assert "Incineroar" in pokemon_names
        assert "Raging Bolt" in pokemon_names

    def test_handles_empty_text(self):
        """Test handling empty text."""
        from smogon_vgc_mcp.fetcher.moveset import parse_pokemon_blocks

        blocks = parse_pokemon_blocks("")
        assert blocks == []

    def test_handles_text_without_pokemon(self):
        """Test handling text with no Pokemon headers."""
        from smogon_vgc_mcp.fetcher.moveset import parse_pokemon_blocks

        text = "Some random text without Pokemon blocks"
        blocks = parse_pokemon_blocks(text)
        assert blocks == []


class TestParseTeraTypes:
    """Tests for parse_tera_types function."""

    def test_parses_tera_types(self):
        """Test parsing Tera Types section."""
        from smogon_vgc_mcp.fetcher.moveset import parse_tera_types

        block = """
 | Tera Types                             |
 | Fairy 87.893%                          |
 | Grass  7.504%                          |
 | Ghost  3.128%                          |
 +----------------------------------------+
        """

        tera_types = parse_tera_types(block)

        assert len(tera_types) == 3
        assert ("Fairy", 87.893) in tera_types
        assert ("Grass", 7.504) in tera_types
        assert ("Ghost", 3.128) in tera_types

    def test_excludes_other_tera_type(self):
        """Test that 'Other' tera type is excluded."""
        from smogon_vgc_mcp.fetcher.moveset import parse_tera_types

        block = """
 | Tera Types                             |
 | Fairy 80.000%                          |
 | Other 20.000%                          |
 +----------------------------------------+
        """

        tera_types = parse_tera_types(block)

        assert len(tera_types) == 1
        assert ("Fairy", 80.0) in tera_types

    def test_handles_no_tera_types_section(self):
        """Test handling block without Tera Types section."""
        from smogon_vgc_mcp.fetcher.moveset import parse_tera_types

        block = """
 | Abilities                              |
 | Intimidate 100.0%                      |
        """

        tera_types = parse_tera_types(block)
        assert tera_types == []

    def test_handles_empty_block(self):
        """Test handling empty block."""
        from smogon_vgc_mcp.fetcher.moveset import parse_tera_types

        tera_types = parse_tera_types("")
        assert tera_types == []


class TestParseChecksCounters:
    """Tests for parse_checks_counters function."""

    def test_parses_checks_counters(self):
        """Test parsing Checks and Counters section."""
        from smogon_vgc_mcp.fetcher.moveset import parse_checks_counters

        block = """
 | Checks and Counters                    |
 | Rillaboom 52.526 (55.22±0.67)          |
 |   (34.3% KOed / 25.2% switched out)    |
 | Tatsugiri 52.715 (59.46+-1.69)         |
 |   (28.5% KOed / 30.1% switched out)    |
 +----------------------------------------+
        """

        counters = parse_checks_counters(block)

        assert len(counters) == 2

        rillaboom = next((c for c in counters if c["counter"] == "Rillaboom"), None)
        assert rillaboom is not None
        assert rillaboom["score"] == 52.526
        assert rillaboom["win_percent"] == 55.22
        assert rillaboom["ko_percent"] == 34.3
        assert rillaboom["switch_percent"] == 25.2

    def test_handles_pokemon_forms(self):
        """Test handling Pokemon with forms in names."""
        from smogon_vgc_mcp.fetcher.moveset import parse_checks_counters

        block = """
 | Checks and Counters                    |
 | Urshifu-Rapid-Strike 55.000 (60.00±1.00) |
 |   (40.0% KOed / 20.0% switched out)    |
 +----------------------------------------+
        """

        counters = parse_checks_counters(block)

        assert len(counters) == 1
        assert counters[0]["counter"] == "Urshifu-Rapid-Strike"

    def test_handles_no_checks_counters_section(self):
        """Test handling block without Checks and Counters section."""
        from smogon_vgc_mcp.fetcher.moveset import parse_checks_counters

        block = """
 | Abilities                              |
 | Intimidate 100.0%                      |
        """

        counters = parse_checks_counters(block)
        assert counters == []

    def test_handles_empty_block(self):
        """Test handling empty block."""
        from smogon_vgc_mcp.fetcher.moveset import parse_checks_counters

        counters = parse_checks_counters("")
        assert counters == []

    def test_handles_missing_ko_switch_line(self):
        """Test handling when KO/switch line is missing."""
        from smogon_vgc_mcp.fetcher.moveset import parse_checks_counters

        block = """
 | Checks and Counters                    |
 | Rillaboom 52.526 (55.22±0.67)          |
 +----------------------------------------+
        """

        counters = parse_checks_counters(block)

        assert len(counters) == 1
        assert counters[0]["counter"] == "Rillaboom"
        assert counters[0]["ko_percent"] == 0.0
        assert counters[0]["switch_percent"] == 0.0


class TestMovesetIntegration:
    """Integration tests for moveset parsing."""

    def test_full_pokemon_block_parsing(self):
        """Test parsing a complete Pokemon block."""
        from smogon_vgc_mcp.fetcher.moveset import (
            parse_checks_counters,
            parse_pokemon_blocks,
            parse_tera_types,
        )

        text = """
 +----------------------------------------+
 | Incineroar                             |
 +----------------------------------------+
 | Raw count: 48000                       |
 | Abilities                              |
 | Intimidate 98.5%                       |
 +----------------------------------------+
 | Tera Types                             |
 | Ghost 45.2%                            |
 | Grass 30.1%                            |
 | Water 15.5%                            |
 +----------------------------------------+
 | Checks and Counters                    |
 | Urshifu-Rapid-Strike 55.000 (60.00±1.00) |
 |   (40.0% KOed / 20.0% switched out)    |
 +----------------------------------------+
        """

        blocks = parse_pokemon_blocks(text)
        assert len(blocks) == 1

        pokemon_name, block_content = blocks[0]
        assert pokemon_name == "Incineroar"

        tera_types = parse_tera_types(block_content)
        assert len(tera_types) == 3
        assert ("Ghost", 45.2) in tera_types

        counters = parse_checks_counters(block_content)
        assert len(counters) == 1
        assert counters[0]["counter"] == "Urshifu-Rapid-Strike"
