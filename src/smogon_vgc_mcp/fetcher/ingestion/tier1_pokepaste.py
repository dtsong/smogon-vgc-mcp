"""Tier 1 pokepaste handler for Champions ingestion.

Reuses the existing pokepaste parser and translates its Gen 9 EV
output directly into Champions SP fields (same numeric values — a
pokepaste authored for Champions uses identical text syntax but the
numbers now represent Stat Points).
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
