from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon
from smogon_vgc_mcp.fetcher.ingestion.validator import validate


def _draft(*pokes: ChampionsTeamPokemon) -> ChampionsTeamDraft:
    return ChampionsTeamDraft(
        source_type="pokepaste",
        source_url="https://pokepast.es/x",
        tier_baseline_confidence=1.0,
        pokemon=list(pokes),
    )


def test_valid_team_passes():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="Koraidon", sp_atk=32, sp_spe=32)))
    assert rep.passed
    assert rep.hard_failures == []


def test_sp_over_per_stat_flagged():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X", sp_atk=33)))
    assert not rep.passed
    assert "sp_over_per_stat" in rep.hard_failures


def test_sp_over_total_flagged():
    rep = validate(_draft(ChampionsTeamPokemon(
        slot=1, pokemon="X", sp_hp=32, sp_atk=32, sp_def=10,
    )))
    assert not rep.passed
    assert "sp_over_total" in rep.hard_failures


def test_sp_negative_flagged():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X", sp_atk=-1)))
    assert not rep.passed
    assert "sp_negative" in rep.hard_failures


def test_boundary_32_ok():
    rep = validate(_draft(ChampionsTeamPokemon(slot=1, pokemon="X", sp_atk=32)))
    assert "sp_over_per_stat" not in rep.hard_failures


def test_boundary_66_total_ok():
    # 11 each across 6 stats = 66
    rep = validate(_draft(ChampionsTeamPokemon(
        slot=1, pokemon="X",
        sp_hp=11, sp_atk=11, sp_def=11, sp_spa=11, sp_spd=11, sp_spe=11,
    )))
    assert "sp_over_total" not in rep.hard_failures


def test_empty_team_flagged():
    rep = validate(_draft())
    assert "slot_count" in rep.hard_failures


def test_seven_slots_flagged():
    pokes = [ChampionsTeamPokemon(slot=i, pokemon=f"P{i}") for i in range(1, 8)]
    rep = validate(_draft(*pokes))
    assert "slot_count" in rep.hard_failures


def test_six_slots_ok():
    pokes = [ChampionsTeamPokemon(slot=i, pokemon=f"P{i}") for i in range(1, 7)]
    rep = validate(_draft(*pokes))
    assert "slot_count" not in rep.hard_failures


def test_duplicate_species_flagged():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"),
        ChampionsTeamPokemon(slot=2, pokemon="Flutter Mane"),
    ))
    assert "duplicate_species" in rep.hard_failures


def test_species_clause_case_insensitive():
    rep = validate(_draft(
        ChampionsTeamPokemon(slot=1, pokemon="Flutter Mane"),
        ChampionsTeamPokemon(slot=2, pokemon="flutter mane"),
    ))
    assert "duplicate_species" in rep.hard_failures


FAKE_DEX = {
    "flutter mane": {
        "abilities": ["Protosynthesis"],
        "moves": ["Moonblast", "Shadow Ball", "Protect", "Dazzling Gleam", "Icy Wind"],
    },
    "koraidon": {
        "abilities": ["Orichalcum Pulse"],
        "moves": ["Flare Blitz", "Collision Course", "Protect", "Dragon Claw"],
    },
}


def test_pokemon_unknown_flagged():
    rep = validate(
        _draft(ChampionsTeamPokemon(slot=1, pokemon="Fake Pokemon")),
        dex_lookup=FAKE_DEX,
    )
    assert "pokemon_unknown" in rep.hard_failures


def test_ability_illegal_flagged_as_soft():
    rep = validate(
        _draft(ChampionsTeamPokemon(
            slot=1, pokemon="Flutter Mane", ability="Levitate",
        )),
        dex_lookup=FAKE_DEX,
    )
    assert "ability_illegal" in rep.soft_failures
    assert rep.passed  # soft failures don't fail the report


def test_move_illegal_flagged_as_soft():
    rep = validate(
        _draft(ChampionsTeamPokemon(
            slot=1, pokemon="Flutter Mane",
            move1="Flare Blitz",  # not in Flutter Mane learnset
        )),
        dex_lookup=FAKE_DEX,
    )
    assert "move_illegal" in rep.soft_failures


def test_legal_ability_and_moves_ok():
    rep = validate(
        _draft(ChampionsTeamPokemon(
            slot=1, pokemon="Flutter Mane",
            ability="Protosynthesis",
            move1="Moonblast", move2="Shadow Ball", move3="Protect", move4="Icy Wind",
        )),
        dex_lookup=FAKE_DEX,
    )
    assert "ability_illegal" not in rep.soft_failures
    assert "move_illegal" not in rep.soft_failures
