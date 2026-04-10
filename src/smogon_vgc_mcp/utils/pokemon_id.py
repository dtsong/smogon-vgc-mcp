"""Pokemon identifier normalization utilities."""


def normalize_pokemon_id(pokemon: str) -> str:
    """Normalize a Pokemon name to the canonical DB ID format.

    Converts to lowercase and strips spaces and hyphens so that
    user-supplied names like "Nidoran-F" or "Mega Charizard X" resolve
    to the same key used in the database (e.g. "nidoranf", "megacharizardx").
    """
    return pokemon.lower().replace(" ", "").replace("-", "")
