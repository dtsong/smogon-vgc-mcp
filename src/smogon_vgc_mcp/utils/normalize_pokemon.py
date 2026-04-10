"""Pokemon name normalization for historical archive lookups.

The Nugget Bridge corpus (VGC12-VGC17) refers to the same Pokemon many ways:
``Landorus-T``, ``Landorus (Therian)``, ``Landorus-Therian``, ``Lando-T``.
This module collapses all of those to a single canonical key
(``landorustherian``) matching Showdown/pokedex conventions, so ``nb_sets``
rows can be keyed and queried uniformly.

Canonical form: lowercase ASCII, with every character outside ``[a-z0-9]``
removed. Accent marks are NFKD-decomposed and stripped (``Flabébé`` →
``flabebe``). Forme suffix codes (``-T``, ``-W``) are only expanded when the
species is known to have that forme, so ``Jangmo-o`` and ``Ho-Oh`` are left
intact. Deliberately string-only, no DB calls — safe for ingest pipeline
and unit tests.
"""

from __future__ import annotations

import re
import unicodedata

# Species → {suffix_code: expansion}. Empty string expansion means "drop the
# suffix" (default forme). Suffix keys are already normalized (lowercase,
# alphanumeric only).
SPECIES_SUFFIX_RULES: dict[str, dict[str, str]] = {
    "landorus": {"t": "therian", "therian": "therian", "i": "", "incarnate": ""},
    "thundurus": {"t": "therian", "therian": "therian", "i": "", "incarnate": ""},
    "tornadus": {"t": "therian", "therian": "therian", "i": "", "incarnate": ""},
    "rotom": {
        "w": "wash",
        "wash": "wash",
        "h": "heat",
        "heat": "heat",
        "f": "frost",
        "frost": "frost",
        "c": "mow",
        "mow": "mow",
        "fan": "fan",
    },
    "giratina": {"o": "origin", "origin": "origin", "altered": ""},
    "shaymin": {"sky": "sky", "s": "sky", "land": ""},
    "deoxys": {
        "a": "attack",
        "attack": "attack",
        "d": "defense",
        "defense": "defense",
        "speed": "speed",
        "normal": "",
    },
    "kyurem": {"b": "black", "black": "black", "w": "white", "white": "white"},
    "zygarde": {
        "10": "10",
        "10percent": "10",
        "complete": "complete",
        "50": "",
        "50percent": "",
    },
    "necrozma": {
        "duskmane": "duskmane",
        "dawnwings": "dawnwings",
        "ultra": "ultra",
    },
    "meloetta": {"pirouette": "pirouette", "aria": ""},
    "keldeo": {"resolute": "resolute", "ordinary": ""},
    "hoopa": {"unbound": "unbound", "confined": ""},
    "aegislash": {"blade": "blade", "shield": ""},
    "wishiwashi": {"school": "school", "solo": ""},
    "lycanroc": {"midnight": "midnight", "dusk": "dusk", "midday": ""},
    "greninja": {"ash": "ash"},
    "oricorio": {
        "baile": "",
        "pompom": "pompom",
        "pau": "pau",
        "sensu": "sensu",
    },
    "wormadam": {
        "g": "ground",
        "ground": "ground",
        "s": "sandy",
        "sandy": "sandy",
        "trash": "trash",
    },
    # Alolan regional forms (gen 7 era)
    "ninetales": {"alola": "alola", "alolan": "alola"},
    "vulpix": {"alola": "alola", "alolan": "alola"},
    "raichu": {"alola": "alola", "alolan": "alola"},
    "marowak": {"alola": "alola", "alolan": "alola"},
    "sandslash": {"alola": "alola", "alolan": "alola"},
    "dugtrio": {"alola": "alola", "alolan": "alola"},
    "persian": {"alola": "alola", "alolan": "alola"},
    "muk": {"alola": "alola", "alolan": "alola"},
}

# Universal forme suffixes that can attach to any species.
UNIVERSAL_SUFFIXES: dict[str, str] = {
    "mega": "mega",
    "megax": "megax",
    "megay": "megay",
    "primal": "primal",
    "gmax": "gmax",
}

# Whole-name override map applied AFTER the main pipeline. Handles cases
# where callers wrote the forme prefix first ("Ash-Greninja") or where the
# canonical Showdown ID differs from the naive concatenation.
NAME_ALIASES: dict[str, str] = {
    "ashgreninja": "greninjaash",
    "megakangaskhan": "kangaskhanmega",
    "megasalamence": "salamencemega",
    "megacharizardy": "charizardmegay",
    "megacharizardx": "charizardmegax",
    "megagengar": "gengarmega",
    "megamawile": "mawilemega",
    "megamanectric": "manectricmega",
    "megalucario": "lucariomega",
    "megametagross": "metagrossmega",
    "megagardevoir": "gardevoirmega",
    "primalgroudon": "groudonprimal",
    "primalkyogre": "kyogreprimal",
}

# Matches a trailing ``(Qualifier)`` or ``(Qualifier Forme)``.
_PAREN_QUALIFIER = re.compile(r"\s*\(([^)]+)\)\s*$")
_MEGA_PREFIX = re.compile(r"^(mega|primal)\s+(.+)$", re.IGNORECASE)
_MEGA_XY_SUFFIX = re.compile(r"^(.+?)\s+([xy])$", re.IGNORECASE)


def _to_ascii(s: str) -> str:
    """NFKD-decompose and drop combining marks so ``Flabébé`` → ``Flabebe``."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def _strip_non_alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _to_ascii(s).lower())


def normalize_pokemon_name(raw: str) -> str:
    """Return the canonical lowercase-alphanumeric form of a Pokemon name.

    Examples:
        >>> normalize_pokemon_name("Landorus-T")
        'landorustherian'
        >>> normalize_pokemon_name("Landorus (Therian)")
        'landorustherian'
        >>> normalize_pokemon_name("Kartana")
        'kartana'
        >>> normalize_pokemon_name("Mr. Mime")
        'mrmime'
        >>> normalize_pokemon_name("Jangmo-o")
        'jangmoo'
        >>> normalize_pokemon_name("")
        ''
    """
    if not raw:
        return ""

    name = _to_ascii(raw).strip()

    # Pull trailing ``(Qualifier)`` into a hyphen suffix.
    paren_match = _PAREN_QUALIFIER.search(name)
    if paren_match:
        qualifier = paren_match.group(1).strip()
        name = name[: paren_match.start()].rstrip()
        qualifier_clean = re.sub(r"\s+forme?$", "", qualifier, flags=re.IGNORECASE).strip()
        if qualifier_clean:
            name = f"{name}-{qualifier_clean}"

    # ``Mega Kangaskhan`` / ``Primal Groudon`` → suffix form.
    # ``Mega Charizard Y`` → ``Charizard-mega-Y``.
    mega_match = _MEGA_PREFIX.match(name)
    if mega_match:
        prefix = mega_match.group(1).lower()
        base = mega_match.group(2).strip()
        xy = _MEGA_XY_SUFFIX.match(base)
        if xy:
            name = f"{xy.group(1).strip()}-{prefix}-{xy.group(2)}"
        else:
            name = f"{base}-{prefix}"

    parts = re.split(r"[-\s]+", name)
    if not parts:
        return ""

    head_key = _strip_non_alnum(parts[0])
    species_rules = SPECIES_SUFFIX_RULES.get(head_key, {})

    tail: list[str] = []
    for seg in parts[1:]:
        seg_key = _strip_non_alnum(seg)
        if not seg_key:
            continue
        if seg_key in UNIVERSAL_SUFFIXES:
            expansion = UNIVERSAL_SUFFIXES[seg_key]
            if expansion:
                tail.append(expansion)
        elif seg_key in species_rules:
            expansion = species_rules[seg_key]
            if expansion:
                tail.append(expansion)
        else:
            tail.append(seg_key)

    normalized = head_key + "".join(tail)

    return NAME_ALIASES.get(normalized, normalized)
