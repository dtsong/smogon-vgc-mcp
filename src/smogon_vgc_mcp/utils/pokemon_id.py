"""Pokemon identifier normalization utilities."""

import re

# Matches every character that Showdown's toID() strips:
# anything outside the lowercase alphanumeric set. This covers spaces,
# hyphens, apostrophes (Farfetch'd), periods (Mr. Mime), colons
# (Type: Null), and gender symbols (Nidoran♀).
_NON_ID_CHARS = re.compile(r"[^a-z0-9]+")


def normalize_pokemon_id(pokemon: str) -> str:
    """Normalize a Pokemon name to the canonical DB ID format.

    Mirrors Showdown's toID(): lowercase, then strip every non-alphanumeric
    character. Handles spaces, hyphens, apostrophes, periods, colons, and
    gender symbols so names like "Mr. Mime", "Farfetch'd", "Type: Null",
    and "Nidoran-F" all resolve to the same key used in the database
    ("mrmime", "farfetchd", "typenull", "nidoranf").
    """
    return _NON_ID_CHARS.sub("", pokemon.lower())
