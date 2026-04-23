from pathlib import Path

from smogon_vgc_mcp.fetcher.ingestion.tier1_pokepaste import (
    parse_pokepaste_to_champions_draft,
)

FIXTURE = Path(__file__).parent / "fixtures" / "champions_pokepaste_sample.txt"


def test_tier1_parses_two_pokemon():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(text, source_url="https://pokepast.es/fixt")
    assert len(draft.pokemon) == 2
    assert draft.pokemon[0].pokemon == "Koraidon"
    assert draft.pokemon[1].pokemon == "Flutter Mane"


def test_tier1_maps_evs_to_sp():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(text, source_url="https://pokepast.es/fixt")
    kor = draft.pokemon[0]
    assert kor.sp_atk == 32
    assert kor.sp_spe == 32
    assert kor.sp_hp == 0


def test_tier1_captures_item_ability_nature_tera():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(text, source_url="https://pokepast.es/fixt")
    kor = draft.pokemon[0]
    assert kor.item == "Life Orb"
    assert kor.ability == "Orichalcum Pulse"
    assert kor.nature == "Adamant"
    assert kor.tera_type == "Fire"


def test_tier1_captures_moves():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(text, source_url="https://pokepast.es/fixt")
    kor = draft.pokemon[0]
    assert kor.move1 == "Flare Blitz"
    assert kor.move4 == "Dragon Claw"


def test_tier1_sets_source_type_and_baseline_confidence():
    text = FIXTURE.read_text()
    draft = parse_pokepaste_to_champions_draft(text, source_url="https://pokepast.es/fixt")
    assert draft.source_type == "pokepaste"
    assert draft.tier_baseline_confidence == 1.0
