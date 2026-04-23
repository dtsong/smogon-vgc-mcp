"""Autocomplete data loader.

Pulls the species / move / ability universe from ``champions_dex_*``
tables (near-universal coverage) plus static nature and stat lists.
Items have no dedicated dex table yet, so the item list is seeded from
distinct values already present in ``nb_sets``.
"""

from __future__ import annotations

import aiosqlite

from smogon_vgc_mcp.data.pokemon_data import NATURE_MODIFIERS

_STATS = ["hp", "atk", "def", "spa", "spd", "spe"]


async def load_autocomplete(db: aiosqlite.Connection) -> dict[str, list[str]]:
    db.row_factory = aiosqlite.Row

    async with db.execute("SELECT name FROM champions_dex_pokemon ORDER BY name") as cursor:
        pokemon = [row["name"] for row in await cursor.fetchall()]

    async with db.execute("SELECT name FROM champions_dex_moves ORDER BY name") as cursor:
        moves = [row["name"] for row in await cursor.fetchall()]

    async with db.execute("SELECT name FROM champions_dex_abilities ORDER BY name") as cursor:
        abilities = [row["name"] for row in await cursor.fetchall()]

    async with db.execute(
        "SELECT DISTINCT item FROM nb_sets WHERE item IS NOT NULL ORDER BY item"
    ) as cursor:
        items = [row["item"] for row in await cursor.fetchall()]

    natures = sorted(n.title() for n in NATURE_MODIFIERS)

    return {
        "pokemon": pokemon,
        "moves": moves,
        "abilities": abilities,
        "items": items,
        "natures": natures,
        "stats": _STATS,
    }
