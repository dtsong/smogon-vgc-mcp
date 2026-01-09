"""Tests for formats.py - VGC format configuration."""

import pytest

from smogon_vgc_mcp.formats import (
    DEFAULT_FORMAT,
    FORMATS,
    FormatConfig,
    get_current_format,
    get_format,
    get_moveset_url,
    get_sheet_csv_url,
    get_smogon_stats_url,
)


class TestFormatRegistry:
    """Tests for format registry and constants."""

    def test_default_format_exists(self):
        """Test that default format exists in registry."""
        assert DEFAULT_FORMAT in FORMATS

    def test_default_format_is_regf(self):
        """Test that default format is regf."""
        assert DEFAULT_FORMAT == "regf"

    def test_regf_format_config(self):
        """Test Regulation F format configuration."""
        regf = FORMATS["regf"]
        assert regf.code == "regf"
        assert regf.name == "Regulation F"
        assert regf.smogon_format_id == "gen9vgc2026regfbo3"
        assert regf.is_current is True
        assert regf.team_id_prefix == "F"

    def test_format_has_available_months(self):
        """Test that format has available months."""
        regf = FORMATS["regf"]
        assert len(regf.available_months) > 0
        assert "2025-12" in regf.available_months

    def test_format_has_available_elos(self):
        """Test that format has available ELO brackets."""
        regf = FORMATS["regf"]
        assert 0 in regf.available_elos
        assert 1500 in regf.available_elos
        assert 1630 in regf.available_elos
        assert 1760 in regf.available_elos


class TestGetFormat:
    """Tests for get_format function."""

    def test_get_valid_format(self):
        """Test getting a valid format."""
        fmt = get_format("regf")
        assert fmt.code == "regf"
        assert fmt.name == "Regulation F"

    def test_get_invalid_format_raises(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError):
            get_format("invalid_format")

    def test_get_format_returns_format_config(self):
        """Test that get_format returns FormatConfig instance."""
        fmt = get_format("regf")
        assert isinstance(fmt, FormatConfig)


class TestGetCurrentFormat:
    """Tests for get_current_format function."""

    def test_current_format_returns_format_config(self):
        """Test that current format is returned."""
        fmt = get_current_format()
        assert isinstance(fmt, FormatConfig)
        assert fmt.is_current is True

    def test_current_format_is_regf(self):
        """Test that current format is regf."""
        fmt = get_current_format()
        assert fmt.code == "regf"


class TestGetSmogonStatsURL:
    """Tests for Smogon stats URL generation."""

    def test_basic_url_generation(self):
        """Test basic URL generation."""
        url = get_smogon_stats_url("regf", "2025-12", 1500)
        assert "smogon.com/stats" in url
        assert "2025-12" in url
        assert "gen9vgc2026regfbo3" in url
        assert "1500" in url

    def test_url_format_chaos_json(self):
        """Test URL ends with correct format."""
        url = get_smogon_stats_url("regf", "2025-12", 1500)
        assert url.endswith(".json")
        assert "/chaos/" in url

    def test_different_elo_brackets(self):
        """Test URL generation with different ELO brackets."""
        url_0 = get_smogon_stats_url("regf", "2025-12", 0)
        url_1500 = get_smogon_stats_url("regf", "2025-12", 1500)
        url_1760 = get_smogon_stats_url("regf", "2025-12", 1760)

        assert "-0.json" in url_0
        assert "-1500.json" in url_1500
        assert "-1760.json" in url_1760

    def test_different_months(self):
        """Test URL generation with different months."""
        url_nov = get_smogon_stats_url("regf", "2025-11", 1500)
        url_dec = get_smogon_stats_url("regf", "2025-12", 1500)

        assert "2025-11" in url_nov
        assert "2025-12" in url_dec


class TestGetMovesetURL:
    """Tests for moveset URL generation."""

    def test_basic_moveset_url(self):
        """Test basic moveset URL generation."""
        url = get_moveset_url("regf", "2025-12", 1500)
        assert "smogon.com/stats" in url
        assert "moveset" in url
        assert "2025-12" in url

    def test_moveset_url_txt_format(self):
        """Test moveset URL ends with .txt."""
        url = get_moveset_url("regf", "2025-12", 1500)
        assert url.endswith(".txt")


class TestGetSheetCSVURL:
    """Tests for Google Sheet CSV URL generation."""

    def test_regf_has_sheet_url(self):
        """Test that regf format has a sheet URL."""
        url = get_sheet_csv_url("regf")
        assert url is not None
        assert "docs.google.com/spreadsheets" in url

    def test_sheet_url_contains_gid(self):
        """Test that sheet URL contains the gid parameter."""
        url = get_sheet_csv_url("regf")
        assert "gid=" in url

    def test_sheet_url_export_format(self):
        """Test that sheet URL has CSV export format."""
        url = get_sheet_csv_url("regf")
        assert "out:csv" in url or "format=csv" in url
