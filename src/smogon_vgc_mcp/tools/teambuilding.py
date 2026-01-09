"""Team building tools for MCP server."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import (
    find_by_item,
    find_by_move,
    find_by_tera_type,
    get_counters_for,
    get_teammates,
)
from smogon_vgc_mcp.formats import DEFAULT_FORMAT
from smogon_vgc_mcp.utils import (
    ValidationError,
    cap_limit,
    make_error_response,
    round_percent,
    validate_elo_bracket,
    validate_format_code,
    validate_limit,
    validate_type_name,
)


def register_teambuilding_tools(mcp: FastMCP) -> None:
    """Register team building tools with the MCP server."""

    @mcp.tool()
    async def get_pokemon_teammates(
        pokemon: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
        limit: int = 10,
    ) -> dict:
        """Get the most common teammates for a Pokemon.

        Args:
            pokemon: Pokemon name (e.g., "Incineroar")
            format: VGC format code (e.g., "regf")
            month: Stats month
            elo: ELO bracket
            limit: Number of teammates to return

        Returns:
            List of most common teammates with usage percentages
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            limit = validate_limit(limit)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        limit = cap_limit(limit)
        teammates = await get_teammates(pokemon, format, month, elo, limit)

        if not teammates:
            return make_error_response(
                f"No teammate data found for '{pokemon}'",
                hint="Check if the Pokemon name is correct or if data exists for this period",
            )

        return {
            "pokemon": pokemon,
            "format": format,
            "month": month,
            "elo": elo,
            "teammates": [
                {"teammate": t.teammate, "percent": round_percent(t.percent)} for t in teammates
            ],
        }

    @mcp.tool()
    async def find_pokemon_by_item(
        item: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
        limit: int = 10,
    ) -> dict:
        """Find Pokemon that commonly use a specific item.

        Args:
            item: Item name (e.g., "assaultvest", "choicescarf")
            format: VGC format code (e.g., "regf")
            month: Stats month
            elo: ELO bracket
            limit: Number of Pokemon to return

        Returns:
            List of Pokemon that use this item most frequently
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            limit = validate_limit(limit)
            if not item or not item.strip():
                raise ValidationError("Item name cannot be empty")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        limit = cap_limit(limit)
        results = await find_by_item(item, format, month, elo, limit)

        if not results:
            return make_error_response(
                f"No Pokemon found using '{item}'",
                hint="Item names are lowercase without spaces (e.g., 'assaultvest', 'choicescarf')",
            )

        return {
            "item": item,
            "format": format,
            "month": month,
            "elo": elo,
            "pokemon": [
                {"pokemon": r["pokemon"], "percent": round_percent(r["percent"])} for r in results
            ],
        }

    @mcp.tool()
    async def find_pokemon_by_move(
        move: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
        limit: int = 10,
    ) -> dict:
        """Find Pokemon that commonly use a specific move.

        Args:
            move: Move name (e.g., "fakeout", "protect")
            format: VGC format code (e.g., "regf")
            month: Stats month
            elo: ELO bracket
            limit: Number of Pokemon to return

        Returns:
            List of Pokemon that use this move most frequently
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            limit = validate_limit(limit)
            if not move or not move.strip():
                raise ValidationError("Move name cannot be empty")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        limit = cap_limit(limit)
        results = await find_by_move(move, format, month, elo, limit)

        if not results:
            return make_error_response(
                f"No Pokemon found using '{move}'",
                hint="Move names are lowercase without spaces (e.g., 'fakeout', 'protect')",
            )

        return {
            "move": move,
            "format": format,
            "month": month,
            "elo": elo,
            "pokemon": [
                {"pokemon": r["pokemon"], "percent": round_percent(r["percent"])} for r in results
            ],
        }

    @mcp.tool()
    async def find_pokemon_by_tera(
        tera_type: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
        limit: int = 10,
    ) -> dict:
        """Find Pokemon that commonly use a specific Tera Type.

        Args:
            tera_type: Tera Type name (e.g., "Fairy", "Ghost", "Grass")
            format: VGC format code (e.g., "regf")
            month: Stats month
            elo: ELO bracket
            limit: Number of Pokemon to return

        Returns:
            List of Pokemon that use this Tera Type most frequently
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            limit = validate_limit(limit)
            tera_type = validate_type_name(tera_type)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        limit = cap_limit(limit)
        results = await find_by_tera_type(tera_type, format, month, elo, limit)

        if not results:
            return make_error_response(
                f"No Pokemon found using Tera {tera_type}",
                hint="Tera Type data requires running refresh_moveset_data first. "
                "Type names are capitalized (e.g., 'Fairy', 'Ghost').",
            )

        return {
            "tera_type": tera_type,
            "format": format,
            "month": month,
            "elo": elo,
            "pokemon": [
                {"pokemon": r["pokemon"], "percent": round_percent(r["percent"])} for r in results
            ],
        }

    @mcp.tool()
    async def get_pokemon_counters(
        pokemon: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
        limit: int = 10,
    ) -> dict:
        """Get Pokemon that counter a specific Pokemon.

        Based on Smogon's checks and counters data, which tracks win rates
        and how often the target Pokemon is KOed or forced to switch.

        Args:
            pokemon: Pokemon name to find counters for (e.g., "Flutter Mane")
            format: VGC format code (e.g., "regf")
            month: Stats month
            elo: ELO bracket
            limit: Number of counters to return

        Returns:
            List of Pokemon that perform best against the target, with win rates
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            limit = validate_limit(limit)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        limit = cap_limit(limit)
        counters = await get_counters_for(pokemon, format, month, elo, limit)

        if not counters:
            return make_error_response(
                f"No counter data found for '{pokemon}'",
                hint="Counter data requires running refresh_moveset_data first. "
                "Check if the Pokemon name is correct.",
            )

        return {
            "pokemon": pokemon,
            "format": format,
            "month": month,
            "elo": elo,
            "counters": [
                {
                    "pokemon": c.counter,
                    "score": round_percent(c.score),
                    "win_percent": round_percent(c.win_percent),
                    "ko_percent": round_percent(c.ko_percent),
                    "switch_percent": round_percent(c.switch_percent),
                }
                for c in counters
            ],
        }
