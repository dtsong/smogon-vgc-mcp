"""Tests for champions_dex fetch orchestrator functions."""

from unittest.mock import AsyncMock, patch

import pytest

from smogon_vgc_mcp.fetcher.champions_dex import (
    fetch_and_store_champions_dex,
    fetch_champions_pokemon_page,
)
from smogon_vgc_mcp.resilience.errors import FetchResult

_VENUSAUR_PARSE_OUTPUT = {
    "id": "venusaur",
    "num": 3,
    "name": "Venusaur",
    "types": ["Grass", "Poison"],
    "base_stats": {"hp": 80, "atk": 82, "def": 83, "spa": 100, "spd": 100, "spe": 80},
    "abilities": ["Overgrow"],
    "ability_hidden": None,
    "height_m": 2.0,
    "weight_kg": 100.0,
    "mega_forms": [],
}

# Minimal Serebii-style HTML for venusaur
_VENUSAUR_HTML = """
<!DOCTYPE html><html><body>
<h1>#003 Venusaur</h1>
<table class="dextable">
  <tr><td class="fooinfo">#003</td></tr>
  <tr><td class="cen"><img class="typeimg" alt="Grass-type">
  <img class="typeimg" alt="Poison-type"></td></tr>
  <tr><td class="fooleft">Abilities: <a>Overgrow</a></td></tr>
  <tr><td class="fooinfo">2.0m</td><td class="fooinfo">100.0kg</td></tr>
  <tr>
    <td class="fooinfo">Base Stats - Total: 525</td>
    <td class="fooinfo">80</td><td class="fooinfo">82</td><td class="fooinfo">83</td>
    <td class="fooinfo">100</td><td class="fooinfo">100</td><td class="fooinfo">80</td>
  </tr>
</table>
</body></html>
"""


class TestFetchChampionsPokemonPage:
    """Tests for fetch_champions_pokemon_page()."""

    @pytest.mark.asyncio
    async def test_returns_none_on_failed_fetch(self):
        failed = FetchResult(success=False, data=None, error=None)
        with patch(
            "smogon_vgc_mcp.fetcher.champions_dex.fetch_text_resilient",
            new=AsyncMock(return_value=failed),
        ):
            result = await fetch_champions_pokemon_page("venusaur")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_parsed_dict_on_success(self):
        ok = FetchResult(success=True, data=_VENUSAUR_HTML, error=None)
        with patch(
            "smogon_vgc_mcp.fetcher.champions_dex.fetch_text_resilient",
            new=AsyncMock(return_value=ok),
        ):
            result = await fetch_champions_pokemon_page("venusaur")
        assert result is not None
        assert result["id"] == "venusaur"
        assert result["name"] == "Venusaur"
        assert "Grass" in result["types"]


class TestFetchAndStoreChampionsDex:
    """Tests for fetch_and_store_champions_dex() in dry-run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_results_without_storing(self, tmp_path):
        db_path = tmp_path / "test.db"
        ok = FetchResult(success=True, data=_VENUSAUR_HTML, error=None)
        with patch(
            "smogon_vgc_mcp.fetcher.champions_dex.fetch_text_resilient",
            new=AsyncMock(return_value=ok),
        ):
            result = await fetch_and_store_champions_dex(
                db_path=db_path,
                dry_run=True,
                dry_run_names=["venusaur"],
                request_delay=0,
            )

        assert result["dry_run"] is True
        assert result["stored"] == 0
        assert result["fetched"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "venusaur"

    @pytest.mark.asyncio
    async def test_dry_run_errors_on_failed_fetch(self, tmp_path):
        db_path = tmp_path / "test.db"
        failed = FetchResult(success=False, data=None, error=None)
        with patch(
            "smogon_vgc_mcp.fetcher.champions_dex.fetch_text_resilient",
            new=AsyncMock(return_value=failed),
        ):
            result = await fetch_and_store_champions_dex(
                db_path=db_path,
                dry_run=True,
                dry_run_names=["venusaur"],
                request_delay=0,
            )

        assert result["fetched"] == 0
        assert len(result["errors"]) == 1
        assert result["errors"][0]["slug"] == "venusaur"
