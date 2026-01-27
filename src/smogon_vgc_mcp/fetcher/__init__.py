"""Smogon data fetcher module."""

from smogon_vgc_mcp.fetcher.moveset import fetch_and_store_moveset_all
from smogon_vgc_mcp.fetcher.pokedex import fetch_and_store_pokedex_all
from smogon_vgc_mcp.fetcher.pokepaste import fetch_pokepaste, parse_pokepaste
from smogon_vgc_mcp.fetcher.replay_list import (
    ReplayListEntry,
    ReplayListError,
    ReplayListResult,
    fetch_private_replay_list,
    fetch_public_replay_list,
)
from smogon_vgc_mcp.fetcher.sheets import fetch_and_store_pokepaste_teams
from smogon_vgc_mcp.fetcher.showdown_auth import (
    AuthenticationError,
    ShowdownSession,
    authenticate_showdown,
    verify_session,
)
from smogon_vgc_mcp.fetcher.smogon import fetch_and_store_all, fetch_vgc_data

__all__ = [
    "fetch_vgc_data",
    "fetch_and_store_all",
    "fetch_and_store_moveset_all",
    "fetch_and_store_pokedex_all",
    "fetch_pokepaste",
    "parse_pokepaste",
    "fetch_and_store_pokepaste_teams",
    "ReplayListEntry",
    "ReplayListResult",
    "ReplayListError",
    "fetch_public_replay_list",
    "fetch_private_replay_list",
    "AuthenticationError",
    "ShowdownSession",
    "authenticate_showdown",
    "verify_session",
]
