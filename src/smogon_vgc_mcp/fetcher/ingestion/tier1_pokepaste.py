"""Tier 1 pokepaste handler for Champions ingestion.

Reuses the existing pokepaste parser and maps its EV fields directly
onto Champions SP fields (same ``EVs:`` line syntax — the numbers are
reinterpreted as Stat Points). Standard VGC spreads (e.g. 252/252/4)
will exceed Champions SP bounds (max 32 per stat, 66 total) and fail
validation as hard failures; this is intentional — the ingestion
pipeline uses the validator to reject non-Champions pastes rather
than silently truncating the values.
"""

from __future__ import annotations

from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon
from smogon_vgc_mcp.fetcher.pokepaste import parse_pokepaste


def parse_pokepaste_to_champions_draft(
    text: str,
    *,
    source_url: str,
) -> ChampionsTeamDraft:
    """Parse raw pokepaste text into a ChampionsTeamDraft."""
    parsed = parse_pokepaste(text)
    pokemon = [
        ChampionsTeamPokemon(
            slot=tp.slot,
            pokemon=tp.pokemon,
            item=tp.item,
            ability=tp.ability,
            nature=tp.nature,
            tera_type=tp.tera_type,
            level=50,
            sp_hp=tp.hp_ev,
            sp_atk=tp.atk_ev,
            sp_def=tp.def_ev,
            sp_spa=tp.spa_ev,
            sp_spd=tp.spd_ev,
            sp_spe=tp.spe_ev,
            move1=tp.move1,
            move2=tp.move2,
            move3=tp.move3,
            move4=tp.move4,
        )
        for tp in parsed
    ]
    return ChampionsTeamDraft(
        source_type="pokepaste",
        source_url=source_url,
        tier_baseline_confidence=1.0,
        pokemon=pokemon,
    )
