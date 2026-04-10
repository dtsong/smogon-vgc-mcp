"""Tests for Pikalytics Champions usage parser."""

from pathlib import Path

import pytest

from smogon_vgc_mcp.fetcher.pikalytics_champions import parse_pikalytics_page

FIXTURE = Path(__file__).parent / "fixtures" / "pikalytics_incineroar.html"


@pytest.fixture
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_returns_usage_dict(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert result["pokemon"] == "incineroar"
    assert result["usage_percent"] is not None
    assert 0 < result["usage_percent"] <= 100


def test_parse_extracts_moves(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert isinstance(result["moves"], list)
    assert len(result["moves"]) > 0
    name, pct = result["moves"][0]
    assert isinstance(name, str) and name
    assert isinstance(pct, float)


def test_parse_extracts_items_abilities_teammates(html: str) -> None:
    result = parse_pikalytics_page(html, pokemon_slug="incineroar")
    assert result is not None
    assert len(result["items"]) > 0
    assert len(result["abilities"]) > 0
    assert len(result["teammates"]) > 0


def test_parse_handles_404() -> None:
    assert parse_pikalytics_page("", pokemon_slug="missingno") is None
    assert parse_pikalytics_page("<html>Not Found</html>", pokemon_slug="missingno") is None
