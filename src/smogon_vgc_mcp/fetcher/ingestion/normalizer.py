"""Deterministic normalizer for Champions team drafts.

Runs before the validator. Fixes common surface-level issues (case,
aliases, whitespace, fuzzy move spelling) and logs every change so the
stored ``normalizations`` column provides an auditable diff between
raw extraction and final values.
"""

from __future__ import annotations

import re
from dataclasses import replace

from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon

_CONSUMED_RE = re.compile(r"\(consumed\)", flags=re.IGNORECASE)

# Minimal alias table — extend as real data exposes gaps. Keys are
# casefolded inputs; values are canonical Pokemon names in the dex.
POKEMON_ALIASES: dict[str, str] = {
    "urshifu-s": "Urshifu-Single-Strike",
    "urshifu-r": "Urshifu-Rapid-Strike",
    "ogerpon-w": "Ogerpon-Wellspring",
    "ogerpon-h": "Ogerpon-Hearthflame",
    "ogerpon-c": "Ogerpon-Cornerstone",
    "landorus-t": "Landorus-Therian",
    "landorus-i": "Landorus-Incarnate",
}


def _levenshtein(a: str, b: str) -> int:
    """Classic iterative Levenshtein distance."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            ins = curr[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


def _closest_move(name: str, known: set[str]) -> str | None:
    """Return the closest known move within distance 2, else None.

    Ties at the same distance are broken by choosing the
    lexicographically smallest name, so the result is deterministic
    regardless of ``known`` iteration order.
    """
    best: tuple[int, str] | None = None
    for known_name in known:
        d = _levenshtein(name.casefold(), known_name.casefold())
        if d > 2:
            continue
        candidate = (d, known_name)
        if best is None or candidate < best:
            best = candidate
    return best[1] if best else None


def _normalize_pokemon(
    poke: ChampionsTeamPokemon,
    *,
    known_moves: set[str] | None,
    log: list[str],
) -> ChampionsTeamPokemon:
    updates: dict[str, object] = {}

    alias = POKEMON_ALIASES.get(poke.pokemon.casefold())
    if alias and alias != poke.pokemon:
        log.append(f"pokemon_alias:{poke.pokemon}->{alias}")
        updates["pokemon"] = alias

    if poke.nature:
        title = poke.nature.strip().title()
        if title != poke.nature:
            log.append(f"nature_case:{poke.nature}->{title}")
            updates["nature"] = title

    if poke.tera_type:
        title = poke.tera_type.strip().title()
        if title != poke.tera_type:
            log.append(f"tera_case:{poke.tera_type}->{title}")
            updates["tera_type"] = title

    if poke.item and _CONSUMED_RE.search(poke.item):
        stripped = _CONSUMED_RE.sub("", poke.item).strip()
        log.append(f"item_strip_consumed:{poke.item}->{stripped}")
        updates["item"] = stripped

    if known_moves:
        for attr in ("move1", "move2", "move3", "move4"):
            current = getattr(poke, attr)
            if not current or current in known_moves:
                continue
            fixed = _closest_move(current, known_moves)
            if fixed and fixed != current:
                log.append(f"move_fuzzy:{current}->{fixed}")
                updates[attr] = fixed

    if not updates:
        return poke
    return replace(poke, **updates)


def normalize(
    draft: ChampionsTeamDraft,
    *,
    known_moves: set[str] | None = None,
) -> tuple[ChampionsTeamDraft, list[str]]:
    """Return a normalized copy of the draft plus a list of change entries."""
    log: list[str] = []
    new_pokes = [_normalize_pokemon(p, known_moves=known_moves, log=log) for p in draft.pokemon]
    return replace(draft, pokemon=new_pokes), log
