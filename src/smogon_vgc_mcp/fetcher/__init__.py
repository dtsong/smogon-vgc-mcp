"""Smogon data fetcher module."""

from smogon_vgc_mcp.fetcher.moveset import fetch_and_store_moveset_all
from smogon_vgc_mcp.fetcher.pokedex import fetch_and_store_pokedex_all
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste, parse_pokepaste
from smogon_vgc_mcp.fetcher.sheets import fetch_and_store_pokepaste_teams
from smogon_vgc_mcp.fetcher.smogon import fetch_and_store_all, fetch_vgc_data

__all__ = [
    "fetch_vgc_data",
    "fetch_and_store_all",
    "fetch_and_store_moveset_all",
    "fetch_and_store_pokedex_all",
    "fetch_pokepaste",
    "parse_pokepaste",
    "fetch_and_store_pokepaste_teams",
]
