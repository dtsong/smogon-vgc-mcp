"""Pokemon lookup tools for MCP server."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import get_pokemon_stats, search_pokemon
from smogon_vgc_mcp.formats import DEFAULT_FORMAT


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
        stats = await get_pokemon_stats(pokemon, format, month, elo)

        if not stats:
            return {
                "error": f"Pokemon '{pokemon}' not found for {format} {month} at ELO {elo}",
                "hint": "Try using find_pokemon to find the correct name",
            }

        result = {
            "pokemon": stats.pokemon,
            "format": format,
            "month": month,
            "elo": elo,
            "usage_percent": round(stats.usage_percent, 2),
            "raw_count": stats.raw_count,
            "viability_ceiling": stats.viability_ceiling,
            "abilities": [
                {"ability": a.ability, "percent": round(a.percent, 1)} for a in stats.abilities[:5]
            ],
            "items": [{"item": i.item, "percent": round(i.percent, 1)} for i in stats.items[:10]],
            "moves": [{"move": m.move, "percent": round(m.percent, 1)} for m in stats.moves[:10]],
            "teammates": [
                {"teammate": t.teammate, "percent": round(t.percent, 1)}
                for t in stats.teammates[:8]
            ],
            "spreads": [
                {
                    "nature": s.nature,
                    "evs": f"{s.hp}/{s.atk}/{s.def_}/{s.spa}/{s.spd}/{s.spe}",
                    "percent": round(s.percent, 1),
                }
                for s in stats.spreads[:5]
            ],
        }

        # Add tera types if available (from moveset data)
        if stats.tera_types:
            result["tera_types"] = [
                {"type": t.tera_type, "percent": round(t.percent, 1)} for t in stats.tera_types[:5]
            ]

        # Add checks/counters if available (from moveset data)
        if stats.checks_counters:
            result["checks_counters"] = [
                {
                    "pokemon": c.counter,
                    "score": round(c.score, 1),
                    "ko_percent": round(c.ko_percent, 1),
                    "switch_percent": round(c.switch_percent, 1),
                }
                for c in stats.checks_counters[:5]
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
