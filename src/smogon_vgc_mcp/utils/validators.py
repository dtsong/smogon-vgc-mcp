"""Input validation utilities for MCP tools."""

import re

from smogon_vgc_mcp.data.pokemon_data import ALL_TYPES, NATURE_MODIFIERS, get_base_stats
from smogon_vgc_mcp.formats import FORMATS
from smogon_vgc_mcp.utils.ev_iv_parser import parse_ev_string, parse_iv_string
from smogon_vgc_mcp.utils.stat_names import STAT_ORDER

VALID_WEATHER = ["Sun", "Rain", "Sand", "Snow"]
VALID_TERRAIN = ["Grassy", "Electric", "Psychic", "Misty"]
VALID_ELO_BRACKETS = [0, 1500, 1630, 1760]


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str, hint: str | None = None):
        self.message = message
        self.hint = hint
        super().__init__(message)


def validate_pokemon_name(name: str) -> str:
    """Validate Pokemon name exists in base stats.

    Args:
        name: Pokemon name (case-insensitive)

    Returns:
        Normalized Pokemon name

    Raises:
        ValidationError: If Pokemon not found
    """
    if not name or not name.strip():
        raise ValidationError("Pokemon name cannot be empty")

    base = get_base_stats(name)
    if base is None:
        raise ValidationError(
            f"Pokemon '{name}' not found",
            hint="Check spelling or use search_dex to find the correct name",
        )
    return name.strip()


def validate_type_name(type_name: str) -> str:
    """Validate type name against ALL_TYPES.

    Args:
        type_name: Type name (case-insensitive)

    Returns:
        Normalized type name (capitalized)

    Raises:
        ValidationError: If type not valid
    """
    if not type_name or not type_name.strip():
        raise ValidationError("Type name cannot be empty")

    normalized = type_name.strip().capitalize()
    if normalized not in ALL_TYPES:
        raise ValidationError(
            f"Invalid type '{type_name}'",
            hint=f"Valid types: {', '.join(ALL_TYPES)}",
        )
    return normalized


def validate_nature(nature: str) -> str:
    """Validate nature name against NATURE_MODIFIERS.

    Args:
        nature: Nature name (case-insensitive)

    Returns:
        Normalized nature name (capitalized)

    Raises:
        ValidationError: If nature not valid
    """
    if not nature or not nature.strip():
        raise ValidationError("Nature cannot be empty")

    normalized = nature.strip().lower()
    if normalized not in NATURE_MODIFIERS:
        valid_natures = [n.capitalize() for n in NATURE_MODIFIERS.keys()]
        raise ValidationError(
            f"Invalid nature '{nature}'",
            hint=f"Valid natures: {', '.join(sorted(valid_natures))}",
        )
    return nature.strip().capitalize()


def validate_format_code(code: str) -> str:
    """Validate format code exists.

    Args:
        code: Format code (e.g., "regf")

    Returns:
        Validated format code

    Raises:
        ValidationError: If format not found
    """
    if not code or not code.strip():
        raise ValidationError("Format code cannot be empty")

    normalized = code.strip().lower()
    if normalized not in FORMATS:
        raise ValidationError(
            f"Unknown format '{code}'",
            hint=f"Valid formats: {', '.join(FORMATS.keys())}",
        )
    return normalized


def validate_weather(weather: str | None) -> str | None:
    """Validate weather value.

    Args:
        weather: Weather type or None

    Returns:
        Validated weather or None

    Raises:
        ValidationError: If weather not valid
    """
    if weather is None:
        return None

    if not weather.strip():
        return None

    normalized = weather.strip().capitalize()
    if normalized not in VALID_WEATHER:
        raise ValidationError(
            f"Invalid weather '{weather}'",
            hint=f"Valid weather: {', '.join(VALID_WEATHER)}",
        )
    return normalized


def validate_terrain(terrain: str | None) -> str | None:
    """Validate terrain value.

    Args:
        terrain: Terrain type or None

    Returns:
        Validated terrain or None

    Raises:
        ValidationError: If terrain not valid
    """
    if terrain is None:
        return None

    if not terrain.strip():
        return None

    normalized = terrain.strip().capitalize()
    if normalized not in VALID_TERRAIN:
        raise ValidationError(
            f"Invalid terrain '{terrain}'",
            hint=f"Valid terrain: {', '.join(VALID_TERRAIN)}",
        )
    return normalized


def validate_ev_spread(evs: str) -> dict[str, int]:
    """Parse and validate EV spread.

    Args:
        evs: EV spread string (e.g., "252/4/0/252/0/0" or "252 HP / 4 Def / 252 SpA")

    Returns:
        Dict with validated EV values

    Raises:
        ValidationError: If EVs invalid (out of range or total > 510)
    """
    if not evs or not evs.strip():
        raise ValidationError("EV spread cannot be empty")

    ev_dict = parse_ev_string(evs)

    for stat, value in ev_dict.items():
        if value < 0 or value > 252:
            raise ValidationError(
                f"Invalid EV value for {stat}: {value}",
                hint="Each stat must be 0-252",
            )

    total = sum(ev_dict.values())
    if total > 510:
        raise ValidationError(
            f"Total EVs ({total}) exceed maximum of 510",
            hint=f"Current spread: {'/'.join(str(ev_dict[s]) for s in STAT_ORDER)}",
        )

    return ev_dict


def validate_iv_spread(ivs: str) -> dict[str, int]:
    """Parse and validate IV spread.

    Args:
        ivs: IV spread string (e.g., "31/31/31/31/31/31" or "31/0/31/31/31/31")

    Returns:
        Dict with validated IV values

    Raises:
        ValidationError: If IVs invalid (out of range)
    """
    if not ivs or not ivs.strip():
        raise ValidationError("IV spread cannot be empty")

    iv_dict = parse_iv_string(ivs)

    for stat, value in iv_dict.items():
        if value < 0 or value > 31:
            raise ValidationError(
                f"Invalid IV value for {stat}: {value}",
                hint="Each stat must be 0-31",
            )

    return iv_dict


def validate_level(level: int) -> int:
    """Validate Pokemon level.

    Args:
        level: Pokemon level

    Returns:
        Validated level

    Raises:
        ValidationError: If level out of range
    """
    if not isinstance(level, int):
        raise ValidationError(f"Level must be an integer, got {type(level).__name__}")

    if level < 1 or level > 100:
        raise ValidationError(
            f"Invalid level {level}",
            hint="Level must be 1-100",
        )
    return level


def validate_stat_boost(boost: int, stat_name: str = "stat") -> int:
    """Validate stat boost value.

    Args:
        boost: Stat boost value
        stat_name: Name of stat for error message

    Returns:
        Validated boost

    Raises:
        ValidationError: If boost out of range
    """
    if not isinstance(boost, int):
        raise ValidationError(f"{stat_name} boost must be an integer")

    if boost < -6 or boost > 6:
        raise ValidationError(
            f"Invalid {stat_name} boost: {boost}",
            hint="Stat boosts must be -6 to +6",
        )
    return boost


def validate_elo_bracket(elo: int) -> int:
    """Validate ELO bracket.

    Args:
        elo: ELO bracket value

    Returns:
        Validated ELO

    Raises:
        ValidationError: If ELO not a valid bracket
    """
    if not isinstance(elo, int):
        raise ValidationError(f"ELO must be an integer, got {type(elo).__name__}")

    if elo not in VALID_ELO_BRACKETS:
        raise ValidationError(
            f"Invalid ELO bracket {elo}",
            hint=f"Valid ELO brackets: {', '.join(str(e) for e in VALID_ELO_BRACKETS)}",
        )
    return elo


def validate_limit(limit: int, max_limit: int = 50) -> int:
    """Validate and cap a limit parameter.

    Args:
        limit: Requested limit
        max_limit: Maximum allowed limit

    Returns:
        Validated limit (capped if necessary)

    Raises:
        ValidationError: If limit is not positive
    """
    if not isinstance(limit, int):
        raise ValidationError(f"Limit must be an integer, got {type(limit).__name__}")

    if limit < 1:
        raise ValidationError(
            f"Invalid limit {limit}",
            hint="Limit must be a positive integer",
        )

    return min(limit, max_limit)


def validate_pokemon_list(
    pokemon_list: list[str],
    min_size: int = 1,
    max_size: int = 6,
) -> list[str]:
    """Validate a list of Pokemon names.

    Args:
        pokemon_list: List of Pokemon names
        min_size: Minimum list size
        max_size: Maximum list size

    Returns:
        List of validated Pokemon names

    Raises:
        ValidationError: If list size wrong or Pokemon invalid
    """
    if not isinstance(pokemon_list, list):
        raise ValidationError("Pokemon list must be a list")

    if len(pokemon_list) < min_size:
        raise ValidationError(
            f"Pokemon list too short: {len(pokemon_list)} < {min_size}",
            hint=f"Provide at least {min_size} Pokemon",
        )

    if len(pokemon_list) > max_size:
        raise ValidationError(
            f"Pokemon list too long: {len(pokemon_list)} > {max_size}",
            hint=f"Maximum {max_size} Pokemon allowed",
        )

    validated = []
    for i, name in enumerate(pokemon_list):
        try:
            validated.append(validate_pokemon_name(name))
        except ValidationError as e:
            raise ValidationError(
                f"Invalid Pokemon at position {i + 1}: {e.message}",
                hint=e.hint,
            ) from e

    return validated


def validate_type_list(
    type_list: list[str],
    min_size: int = 1,
    max_size: int = 4,
) -> list[str]:
    """Validate a list of type names.

    Args:
        type_list: List of type names
        min_size: Minimum list size
        max_size: Maximum list size

    Returns:
        List of validated type names

    Raises:
        ValidationError: If list size wrong or type invalid
    """
    if not isinstance(type_list, list):
        raise ValidationError("Type list must be a list")

    if len(type_list) < min_size:
        raise ValidationError(
            f"Type list too short: {len(type_list)} < {min_size}",
            hint=f"Provide at least {min_size} type(s)",
        )

    if len(type_list) > max_size:
        raise ValidationError(
            f"Type list too long: {len(type_list)} > {max_size}",
            hint=f"Maximum {max_size} types allowed",
        )

    validated = []
    for i, type_name in enumerate(type_list):
        try:
            validated.append(validate_type_name(type_name))
        except ValidationError as e:
            raise ValidationError(
                f"Invalid type at position {i + 1}: {e.message}",
                hint=e.hint,
            ) from e

    return validated


def validate_stat_boosts(boosts: dict[str, int] | None) -> dict[str, int] | None:
    """Validate a dict of stat boosts.

    Args:
        boosts: Dict mapping stat names to boost values, or None

    Returns:
        Validated boosts dict or None

    Raises:
        ValidationError: If any boost is invalid
    """
    if boosts is None:
        return None

    if not isinstance(boosts, dict):
        raise ValidationError("Stat boosts must be a dictionary")

    valid_stats = set(STAT_ORDER)
    validated = {}

    for stat, boost in boosts.items():
        stat_lower = stat.lower()
        if stat_lower not in valid_stats:
            raise ValidationError(
                f"Invalid stat name '{stat}' in boosts",
                hint=f"Valid stats: {', '.join(STAT_ORDER)}",
            )
        validated[stat_lower] = validate_stat_boost(boost, stat)

    return validated


def validate_move_name(move: str) -> str:
    """Validate move name is not empty.

    Args:
        move: Move name

    Returns:
        Stripped move name

    Raises:
        ValidationError: If move name is empty
    """
    if not move or not move.strip():
        raise ValidationError("Move name cannot be empty")
    return move.strip()


def validate_item_name(item: str) -> str:
    """Validate item name is not empty.

    Args:
        item: Item name

    Returns:
        Stripped item name

    Raises:
        ValidationError: If item name is empty
    """
    if not item or not item.strip():
        raise ValidationError("Item name cannot be empty")
    return item.strip()


def validate_ability_name(ability: str) -> str:
    """Validate ability name is not empty.

    Args:
        ability: Ability name

    Returns:
        Stripped ability name

    Raises:
        ValidationError: If ability name is empty
    """
    if not ability or not ability.strip():
        raise ValidationError("Ability name cannot be empty")
    return ability.strip()


def validate_month(month: str) -> str:
    """Validate month is in YYYY-MM format.

    Args:
        month: Month string (e.g., "2025-12")

    Returns:
        Validated month string

    Raises:
        ValidationError: If month format is invalid
    """
    if not month or not month.strip():
        raise ValidationError("Month cannot be empty")

    month = month.strip()
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
        raise ValidationError(
            f"Invalid month format: '{month}'",
            hint="Use YYYY-MM format (e.g., '2025-12')",
        )
    return month


def validate_replay_url(url: str) -> str:
    """Validate Pokemon Showdown replay URL.

    Args:
        url: Replay URL

    Returns:
        Stripped URL

    Raises:
        ValidationError: If URL is empty or not from Pokemon Showdown
    """
    if not url or not url.strip():
        raise ValidationError("Replay URL cannot be empty")

    url = url.strip()
    if "replay.pokemonshowdown.com" not in url:
        raise ValidationError(
            "Invalid replay URL",
            hint="URL must be from replay.pokemonshowdown.com",
        )
    return url


def validate_query_string(query: str, field_name: str = "query") -> str:
    """Validate search query is not empty and reasonable length.

    Args:
        query: Search query string
        field_name: Name of field for error messages

    Returns:
        Stripped query string

    Raises:
        ValidationError: If query is empty or too long
    """
    if not query or not query.strip():
        raise ValidationError(f"{field_name} cannot be empty")

    query = query.strip()
    if len(query) > 100:
        raise ValidationError(
            f"{field_name} too long (max 100 characters)",
            hint="Use a shorter search term",
        )
    return query


def validate_team_id(team_id: str) -> str:
    """Validate team ID format (e.g., 'F123').

    Args:
        team_id: Team ID string

    Returns:
        Stripped team ID

    Raises:
        ValidationError: If team ID is empty or invalid format
    """
    if not team_id or not team_id.strip():
        raise ValidationError("Team ID cannot be empty")

    team_id = team_id.strip()
    if not re.match(r"^[A-Z]\d+$", team_id):
        raise ValidationError(
            f"Invalid team ID format: '{team_id}'",
            hint="Team IDs are format letter + number (e.g., 'F123')",
        )
    return team_id
