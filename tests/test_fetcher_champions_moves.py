"""Tests for Serebii Champions move changes scraper."""

from pathlib import Path

import pytest

from smogon_vgc_mcp.fetcher.champions_moves import parse_serebii_moves_page

FIXTURE = Path(__file__).parent / "fixtures" / "serebii_champions_moves.html"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="latin-1")


def test_parse_returns_list_of_moves(fixture_html: str) -> None:
    moves = parse_serebii_moves_page(fixture_html)
    assert isinstance(moves, list)
    assert len(moves) > 0


def test_parsed_moves_have_required_fields(fixture_html: str) -> None:
    moves = parse_serebii_moves_page(fixture_html)
    for m in moves:
        assert m["id"]
        assert m["name"]
        assert m["type"]
        assert m["category"] in ("Physical", "Special", "Status")
        assert "base_power" in m
        assert "accuracy" in m
        assert "pp" in m


def test_parse_handles_empty_html() -> None:
    assert parse_serebii_moves_page("") == []
    assert parse_serebii_moves_page("<html></html>") == []
