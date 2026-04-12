"""Alias cases for normalize_pokemon_name.

These cover the VGC12-VGC17 Nugget Bridge corpus naming conventions (lots
of ``-T`` suffixes, ``(Therian)`` qualifiers, ``Mega X`` prefixes). If any
of these regress, the historical set lookup breaks at ingest time.
"""

import pytest

from smogon_vgc_mcp.utils.normalize_pokemon import normalize_pokemon_name

# (input, expected) — ≥50 cases covering every common era pattern.
ALIAS_CASES: list[tuple[str, str]] = [
    # Plain names
    ("Kartana", "kartana"),
    ("kartana", "kartana"),
    ("  Garchomp  ", "garchomp"),
    ("Pikachu", "pikachu"),
    # Therian / Incarnate genies
    ("Landorus-T", "landorustherian"),
    ("Landorus (Therian)", "landorustherian"),
    ("Landorus-Therian", "landorustherian"),
    ("Landorus (Therian Forme)", "landorustherian"),
    ("Landorus-I", "landorus"),
    ("Landorus (Incarnate)", "landorus"),
    ("Landorus", "landorus"),
    ("Thundurus-T", "thundurustherian"),
    ("Thundurus-I", "thundurus"),
    ("Tornadus-T", "tornadustherian"),
    # Mega forms (both prefix and suffix)
    ("Mega Kangaskhan", "kangaskhanmega"),
    ("Kangaskhan-Mega", "kangaskhanmega"),
    ("Kangaskhan (Mega)", "kangaskhanmega"),
    ("Mega Charizard Y", "charizardmegay"),
    ("Mega Charizard X", "charizardmegax"),
    ("Charizard-Mega-Y", "charizardmegay"),
    ("Mega Salamence", "salamencemega"),
    ("Mega Gengar", "gengarmega"),
    ("Mega Metagross", "metagrossmega"),
    # Primals
    ("Primal Groudon", "groudonprimal"),
    ("Groudon-Primal", "groudonprimal"),
    ("Primal Kyogre", "kyogreprimal"),
    # Tapu islands
    ("Tapu Lele", "tapulele"),
    ("Tapu Koko", "tapukoko"),
    ("Tapu Bulu", "tapubulu"),
    ("Tapu Fini", "tapufini"),
    # Punctuation quirks
    ("Mr. Mime", "mrmime"),
    ("Mime Jr.", "mimejr"),
    ("Ho-Oh", "hooh"),
    ("Porygon-Z", "porygonz"),
    ("Porygon2", "porygon2"),
    ("Farfetch'd", "farfetchd"),
    ("Type: Null", "typenull"),
    ("Flabébé", "flabebe"),
    # Alola-era oddities
    ("Jangmo-o", "jangmoo"),
    ("Hakamo-o", "hakamoo"),
    ("Kommo-o", "kommoo"),
    # Rotom appliances
    ("Rotom-W", "rotomwash"),
    ("Rotom-Wash", "rotomwash"),
    ("Rotom-H", "rotomheat"),
    ("Rotom-Heat", "rotomheat"),
    ("Rotom-C", "rotommow"),
    # Greninja-Ash (both directions)
    ("Greninja-Ash", "greninjaash"),
    ("Ash-Greninja", "greninjaash"),
    # Giratina
    ("Giratina-O", "giratinaorigin"),
    ("Giratina (Origin)", "giratinaorigin"),
    ("Giratina-Altered", "giratina"),
    # Zygarde
    ("Zygarde", "zygarde"),
    ("Zygarde-10%", "zygarde10"),
    ("Zygarde-Complete", "zygardecomplete"),
    # Deoxys
    ("Deoxys-A", "deoxysattack"),
    ("Deoxys-D", "deoxysdefense"),
    ("Deoxys-Speed", "deoxysspeed"),
    # Shaymin
    ("Shaymin-Sky", "shayminsky"),
    ("Shaymin-Land", "shaymin"),
    # Regional forms
    ("Ninetales-Alola", "ninetalesalola"),
    ("Ninetales (Alolan)", "ninetalesalola"),
    # Case / whitespace
    ("  LANDORUS-T  ", "landorustherian"),
    ("landorus-t", "landorustherian"),
]


@pytest.mark.parametrize("raw,expected", ALIAS_CASES)
def test_normalize_cases(raw: str, expected: str) -> None:
    assert normalize_pokemon_name(raw) == expected


def test_empty_input() -> None:
    assert normalize_pokemon_name("") == ""


def test_idempotent() -> None:
    for raw, expected in ALIAS_CASES:
        assert normalize_pokemon_name(normalize_pokemon_name(raw)) == expected
