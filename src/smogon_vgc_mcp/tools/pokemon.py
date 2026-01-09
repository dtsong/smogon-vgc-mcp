"""Pokemon lookup tools for MCP server."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import get_pokemon_stats, search_pokemon
from smogon_vgc_mcp.formats import DEFAULT_FORMAT
from smogon_vgc_mcp.utils import (
    MAX_ABILITIES_DISPLAY,
    MAX_COUNTERS_DISPLAY,
    MAX_ITEMS_DISPLAY,
    MAX_MOVES_DISPLAY,
    MAX_SPREADS_DISPLAY,
    MAX_TEAMMATES_DISPLAY,
    MAX_TERA_TYPES_DISPLAY,
    ValidationError,
    make_error_response,
    round_percent,
    validate_elo_bracket,
    validate_format_code,
)


def register_pokemon_tools(mcp: FastMCP) -> None:
    """Register Pokemon lookup tools with the MCP server."""

    @mcp.tool()
    async def get_pokemon(
        pokemon: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
    ) -> dict:
        """Get comprehensive stats for a Pokemon.

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane")
            format: VGC format code (e.g., "regf" for Regulation F)
            month: Stats month (format-dependent)
            elo: ELO bracket (0=all, 1500, 1630, 1760)

        Returns:
            Pokemon stats including usage, abilities, items, moves, teammates, spreads
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        stats = await get_pokemon_stats(pokemon, format, month, elo)

        if not stats:
            return make_error_response(
                f"Pokemon '{pokemon}' not found for {format} {month} at ELO {elo}",
                hint="Try using find_pokemon to find the correct name",
            )

        result = {
            "pokemon": stats.pokemon,
            "format": format,
            "month": month,
            "elo": elo,
            "usage_percent": round_percent(stats.usage_percent, 2),
            "raw_count": stats.raw_count,
            "viability_ceiling": stats.viability_ceiling,
            "abilities": [
                {"ability": a.ability, "percent": round_percent(a.percent)}
                for a in stats.abilities[:MAX_ABILITIES_DISPLAY]
            ],
            "items": [
                {"item": i.item, "percent": round_percent(i.percent)}
                for i in stats.items[:MAX_ITEMS_DISPLAY]
            ],
            "moves": [
                {"move": m.move, "percent": round_percent(m.percent)}
                for m in stats.moves[:MAX_MOVES_DISPLAY]
            ],
            "teammates": [
                {"teammate": t.teammate, "percent": round_percent(t.percent)}
                for t in stats.teammates[:MAX_TEAMMATES_DISPLAY]
            ],
            "spreads": [
                {
                    "nature": s.nature,
                    "evs": f"{s.hp}/{s.atk}/{s.def_}/{s.spa}/{s.spd}/{s.spe}",
                    "percent": round_percent(s.percent),
                }
                for s in stats.spreads[:MAX_SPREADS_DISPLAY]
            ],
        }

        # Add tera types if available (from moveset data)
        if stats.tera_types:
            result["tera_types"] = [
                {"type": t.tera_type, "percent": round_percent(t.percent)}
                for t in stats.tera_types[:MAX_TERA_TYPES_DISPLAY]
            ]

        # Add checks/counters if available (from moveset data)
        if stats.checks_counters:
            result["checks_counters"] = [
                {
                    "pokemon": c.counter,
                    "score": round_percent(c.score),
                    "ko_percent": round_percent(c.ko_percent),
                    "switch_percent": round_percent(c.switch_percent),
                }
                for c in stats.checks_counters[:MAX_COUNTERS_DISPLAY]
            ]

        return result

    @mcp.tool()
    async def find_pokemon(
        query: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
    ) -> dict:
        """Search for Pokemon by partial name match.

        Args:
            query: Search query (partial name match)
            format: VGC format code (e.g., "regf" for Regulation F)
            month: Stats month
            elo: ELO bracket

        Returns:
            List of matching Pokemon names
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            if not query or not query.strip():
                raise ValidationError("Search query cannot be empty")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        matches = await search_pokemon(query, format, month, elo)

        if not matches:
            return {
                "query": query,
                "format": format,
                "matches": [],
                "message": f"No Pokemon found matching '{query}'",
            }

        return {
            "query": query,
            "format": format,
            "matches": matches,
            "count": len(matches),
        }
