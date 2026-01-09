"""VGC data resources for MCP server."""

import json

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import (
    get_all_snapshots,
    get_pokemon_stats,
    get_usage_rankings,
)
from smogon_vgc_mcp.formats import DEFAULT_FORMAT


def register_vgc_resources(mcp: FastMCP) -> None:
    """Register VGC data resources with the MCP server."""

    @mcp.resource("vgc://pokemon/{name}")
    async def pokemon_resource(name: str) -> str:
        """Get full stats for a Pokemon (default: latest month, 1500 ELO, current format).

        Args:
            name: Pokemon name (e.g., "Incineroar", "Flutter Mane")

        Returns:
            JSON string with Pokemon stats
        """
        stats = await get_pokemon_stats(name, DEFAULT_FORMAT, month="2025-12", elo=1500)

        if not stats:
            return json.dumps(
                {
                    "error": f"Pokemon '{name}' not found",
                    "hint": "Try using the find_pokemon tool to search for correct name",
                }
            )

        return json.dumps(
            {
                "pokemon": stats.pokemon,
                "format": DEFAULT_FORMAT,
                "month": "2025-12",
                "elo": 1500,
                "usage_percent": round(stats.usage_percent, 2),
                "raw_count": stats.raw_count,
                "viability_ceiling": stats.viability_ceiling,
                "abilities": [
                    {"ability": a.ability, "percent": round(a.percent, 1)}
                    for a in stats.abilities[:5]
                ],
                "items": [
                    {"item": i.item, "percent": round(i.percent, 1)} for i in stats.items[:10]
                ],
                "moves": [
                    {"move": m.move, "percent": round(m.percent, 1)} for m in stats.moves[:10]
                ],
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
        )

    @mcp.resource("vgc://rankings/{month}/{elo}")
    async def rankings_resource(month: str, elo: str) -> str:
        """Get top 50 Pokemon by usage for a specific month and ELO bracket.

        Args:
            month: Stats month (e.g., "2025-12")
            elo: ELO bracket (0, 1500, 1630, 1760)

        Returns:
            JSON string with usage rankings
        """
        try:
            elo_int = int(elo)
        except ValueError:
            return json.dumps({"error": f"Invalid ELO bracket: {elo}"})

        rankings = await get_usage_rankings(DEFAULT_FORMAT, month, elo_int, limit=50)

        if not rankings:
            return json.dumps(
                {
                    "error": f"No data found for {month} at ELO {elo}",
                    "hint": "Run refresh_usage_stats tool to fetch stats from Smogon",
                }
            )

        return json.dumps(
            {
                "format": DEFAULT_FORMAT,
                "month": month,
                "elo": elo_int,
                "rankings": [
                    {
                        "rank": r.rank,
                        "pokemon": r.pokemon,
                        "usage_percent": r.usage_percent,
                    }
                    for r in rankings
                ],
            }
        )

    @mcp.resource("vgc://meta/status")
    async def status_resource() -> str:
        """Get database status and available data snapshots.

        Returns:
            JSON string with database status information
        """
        snapshots = await get_all_snapshots()

        if not snapshots:
            return json.dumps(
                {
                    "status": "no_data",
                    "message": "No data cached. Run refresh_usage_stats to fetch stats.",
                    "snapshots": [],
                }
            )

        by_format: dict[str, dict[str, list[dict]]] = {}
        for s in snapshots:
            if s.format not in by_format:
                by_format[s.format] = {}
            if s.month not in by_format[s.format]:
                by_format[s.format][s.month] = []
            by_format[s.format][s.month].append(
                {
                    "elo": s.elo_bracket,
                    "battles": s.num_battles,
                    "fetched_at": s.fetched_at,
                }
            )

        return json.dumps(
            {
                "status": "ready",
                "total_snapshots": len(snapshots),
                "formats_available": list(by_format.keys()),
                "by_format": by_format,
            }
        )
