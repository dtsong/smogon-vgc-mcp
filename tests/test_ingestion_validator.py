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
