"""Deterministic validator for Champions team drafts.

Runs on every extracted team. Pure functions — no network, no LLM.
Emits a ValidationReport with hard/soft failure reason codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon

SP_PER_STAT_MAX = 32
SP_TOTAL_MAX = 66


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    hard_failures: list[str] = field(default_factory=list)
    soft_failures: list[str] = field(default_factory=list)
    normalizations: list[str] = field(default_factory=list)


def _check_sp_numeric(poke: ChampionsTeamPokemon) -> list[str]:
    """Return list of reason codes for this Pokemon's SP values."""
    sp_values = [poke.sp_hp, poke.sp_atk, poke.sp_def, poke.sp_spa, poke.sp_spd, poke.sp_spe]
    reasons: list[str] = []
    if any(v < 0 for v in sp_values):
        reasons.append("sp_negative")
    if any(v > SP_PER_STAT_MAX for v in sp_values):
        reasons.append("sp_over_per_stat")
    if sum(sp_values) > SP_TOTAL_MAX:
        reasons.append("sp_over_total")
    return reasons


def _check_team_shape(pokes: list[ChampionsTeamPokemon]) -> list[str]:
    reasons: list[str] = []
    if not (1 <= len(pokes) <= 6):
        reasons.append("slot_count")
    names_cf = [p.pokemon.casefold() for p in pokes]
    if len(set(names_cf)) != len(names_cf):
        reasons.append("duplicate_species")
    return reasons


NATURES = frozenset({
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
})

TYPES = frozenset({
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
})

DexLookup = dict[str, dict[str, list[str]]]  # name_casefold -> {"abilities": [...], "moves": [...]}


def _check_pokemon_identity(poke: ChampionsTeamPokemon, dex: DexLookup | None) -> list[str]:
    if dex is None:
        return []
    if poke.pokemon.casefold() not in dex:
        return ["pokemon_unknown"]
    return []


def _check_ability_and_moves(
    poke: ChampionsTeamPokemon, dex: DexLookup | None
) -> list[str]:
    if dex is None:
        return []
    entry = dex.get(poke.pokemon.casefold())
    if entry is None:
        return []
    soft: list[str] = []
    if poke.ability and poke.ability not in entry["abilities"]:
        soft.append("ability_illegal")
    moves = [poke.move1, poke.move2, poke.move3, poke.move4]
    for move in moves:
        if move and move not in entry["moves"]:
            soft.append("move_illegal")
            break
    return soft


def _check_vocab_and_moves(poke: ChampionsTeamPokemon) -> list[str]:
    soft: list[str] = []
    if poke.nature is not None and poke.nature not in NATURES:
        soft.append("nature_unknown")
    if poke.tera_type is not None and poke.tera_type not in TYPES:
        soft.append("tera_type_unknown")
    moves = [m for m in (poke.move1, poke.move2, poke.move3, poke.move4) if m]
    if not (1 <= len(moves) <= 4):
        soft.append("move_count")
    return soft


def validate(
    draft: ChampionsTeamDraft,
    *,
    dex_lookup: DexLookup | None = None,
) -> ValidationReport:
    hard: list[str] = []
    soft: list[str] = []

    for code in _check_team_shape(draft.pokemon):
        if code not in hard:
            hard.append(code)

    for poke in draft.pokemon:
        for code in _check_sp_numeric(poke):
            if code not in hard:
                hard.append(code)
        for code in _check_pokemon_identity(poke, dex_lookup):
            if code not in hard:
                hard.append(code)
        for code in _check_ability_and_moves(poke, dex_lookup):
            if code not in soft:
                soft.append(code)
        for code in _check_vocab_and_moves(poke):
            if code not in soft:
                soft.append(code)

    return ValidationReport(
        passed=not hard,
        hard_failures=hard,
        soft_failures=soft,
    )
