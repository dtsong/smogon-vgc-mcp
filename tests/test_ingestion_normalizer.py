from smogon_vgc_mcp.database.models import ChampionsTeamDraft, ChampionsTeamPokemon
from smogon_vgc_mcp.fetcher.ingestion.normalizer import normalize


def _draft(*pokes: ChampionsTeamPokemon) -> ChampionsTeamDraft:
    return ChampionsTeamDraft(
        source_type="pokepaste",
        source_url="https://x",
        tier_baseline_confidence=1.0,
        pokemon=list(pokes),
    )


def test_pokemon_alias_expanded():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="urshifu-s"))
    normed, log = normalize(d)
    assert normed.pokemon[0].pokemon == "Urshifu-Single-Strike"
    assert any("pokemon_alias" in entry for entry in log)


def test_move_fuzzy_match_distance_2():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Close Combatt"))
    known_moves = {"Close Combat", "Moonblast", "Protect"}
    normed, log = normalize(d, known_moves=known_moves)
    assert normed.pokemon[0].move1 == "Close Combat"
    assert any("move_fuzzy" in entry for entry in log)


def test_move_fuzzy_no_match_left_alone():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Completely Unknown"))
    normed, log = normalize(d, known_moves={"Close Combat"})
    assert normed.pokemon[0].move1 == "Completely Unknown"


def test_nature_title_case():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", nature="timid"))
    normed, log = normalize(d)
    assert normed.pokemon[0].nature == "Timid"


def test_tera_title_case():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", tera_type="fairy"))
    normed, log = normalize(d)
    assert normed.pokemon[0].tera_type == "Fairy"


def test_item_strip_consumed():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", item="Focus Sash (consumed)"))
    normed, log = normalize(d)
    assert normed.pokemon[0].item == "Focus Sash"


def test_item_strip_consumed_uppercase():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", item="Focus Sash (CONSUMED)"))
    normed, log = normalize(d)
    assert normed.pokemon[0].item == "Focus Sash"
    assert any("item_strip_consumed" in entry for entry in log)


def test_item_strip_consumed_titlecase():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", item="Focus Sash (Consumed)"))
    normed, log = normalize(d)
    assert normed.pokemon[0].item == "Focus Sash"
    assert any("item_strip_consumed" in entry for entry in log)


def test_move_fuzzy_match_distance_1():
    # Single-character typo — should be corrected.
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Protct"))
    normed, log = normalize(d, known_moves={"Protect"})
    assert normed.pokemon[0].move1 == "Protect"
    assert any("move_fuzzy" in entry for entry in log)


def test_move_fuzzy_match_distance_3_rejected():
    # Three edits — past the distance-2 threshold; must stay unchanged.
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Protxyz"))
    normed, log = normalize(d, known_moves={"Protect"})
    assert normed.pokemon[0].move1 == "Protxyz"
    assert not any("move_fuzzy" in entry for entry in log)


def test_pokemon_alias_no_op_when_already_canonical():
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="Urshifu-Single-Strike"))
    normed, log = normalize(d)
    assert normed.pokemon[0].pokemon == "Urshifu-Single-Strike"
    assert not any("pokemon_alias" in entry for entry in log)


def test_move_fuzzy_exact_match_left_unchanged():
    # When a move already matches a known_moves entry exactly, it must
    # be preserved and NOT produce a move_fuzzy log entry — otherwise
    # every clean team would ship with spurious normalizations.
    d = _draft(ChampionsTeamPokemon(slot=1, pokemon="X", move1="Close Combat"))
    normed, log = normalize(d, known_moves={"Close Combat", "Protect"})
    assert normed.pokemon[0].move1 == "Close Combat"
    assert not any("move_fuzzy" in entry for entry in log)
