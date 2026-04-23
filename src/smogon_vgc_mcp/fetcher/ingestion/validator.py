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


def validate(draft: ChampionsTeamDraft) -> ValidationReport:
    """Validate a team draft. Returns a ValidationReport."""
    hard: list[str] = []
    soft: list[str] = []

    for code in _check_team_shape(draft.pokemon):
        if code not in hard:
            hard.append(code)

    for poke in draft.pokemon:
        for code in _check_sp_numeric(poke):
            if code not in hard:
                hard.append(code)

    return ValidationReport(
        passed=not hard,
        hard_failures=hard,
        soft_failures=soft,
    )
