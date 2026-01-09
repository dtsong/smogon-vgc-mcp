"""Admin tools for MCP server (refresh, status)."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import get_all_snapshots, get_pokedex_stats, get_team_count
from smogon_vgc_mcp.fetcher import (
    fetch_and_store_all,
    fetch_and_store_moveset_all,
    fetch_and_store_pokedex_all,
    fetch_and_store_pokepaste_teams,
)
from smogon_vgc_mcp.formats import DEFAULT_FORMAT, FORMATS, get_format


def register_admin_tools(mcp: FastMCP) -> None:
    """Register admin tools with the MCP server."""

    @mcp.tool()
    async def refresh_usage_stats(
        format: str = DEFAULT_FORMAT,
        month: str | None = None,
        elo: int | None = None,
    ) -> dict:
        """Fetch latest VGC data from Smogon and update the local database.

        Args:
            format: VGC format code (e.g., "regf" for Regulation F)
            month: Specific month to refresh (None = all months)
            elo: Specific ELO bracket to refresh (None = all brackets)

        Returns:
            Summary of fetched data
        """
        months = [month] if month else None
        elos = [elo] if elo else None

        results = await fetch_and_store_all(format_code=format, months=months, elos=elos)

        return {
            "status": "completed",
            "format": format,
            "successful_fetches": len(results["success"]),
            "failed_fetches": len(results["failed"]),
            "total_pokemon_records": results["total_pokemon"],
            "details": results["success"],
            "errors": results["failed"] if results["failed"] else None,
        }

    @mcp.tool()
    async def get_usage_stats_status(format: str | None = None) -> dict:
        """Get the current status of cached VGC data.

        Args:
            format: VGC format code to filter by (e.g., "regf"), None for all formats

        Returns:
            Information about available data snapshots
        """
        snapshots = await get_all_snapshots(format)

        if not snapshots:
            return {
                "status": "no_data",
                "format": format,
                "message": "No data cached. Run refresh_usage_stats to fetch stats from Smogon.",
                "snapshots": [],
            }

        by_format: dict[str, dict[str, list]] = {}
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

        return {
            "status": "ready",
            "format": format,
            "total_snapshots": len(snapshots),
            "formats_available": list(by_format.keys()),
            "by_format": by_format,
        }

    @mcp.tool()
    async def refresh_moveset_data(
        format: str = DEFAULT_FORMAT,
        month: str | None = None,
        elo: int | None = None,
    ) -> dict:
        """Fetch moveset data (Tera Types, Checks/Counters) from Smogon.

        This fetches the moveset text files and extracts Tera Type distributions
        and Checks/Counters data that isn't available in the chaos JSON.

        IMPORTANT: Run refresh_usage_stats first to populate the base Pokemon usage data.
        This tool augments that data with additional information.

        Args:
            format: VGC format code (e.g., "regf" for Regulation F)
            month: Specific month to refresh (None = all months)
            elo: Specific ELO bracket to refresh (None = all brackets)

        Returns:
            Summary of fetched moveset data
        """
        months = [month] if month else None
        elos = [elo] if elo else None

        results = await fetch_and_store_moveset_all(format_code=format, months=months, elos=elos)

        return {
            "status": "completed",
            "format": format,
            "successful_fetches": len(results["success"]),
            "failed_fetches": len(results["failed"]),
            "total_pokemon_updated": results["total_pokemon_updated"],
            "details": results["success"],
            "errors": results["failed"] if results["failed"] else None,
        }

    @mcp.tool()
    async def refresh_pokepaste_data(
        format: str = DEFAULT_FORMAT,
        max_teams: int | None = None,
    ) -> dict:
        """Fetch tournament teams from Google Sheet and parse their pokepastes.

        This fetches the VGC Pastes Repository spreadsheet and parses each
        pokepaste link to extract full team details.

        Args:
            format: VGC format code (e.g., "regf" for Regulation F)
            max_teams: Optional limit on number of teams to process (for testing)

        Returns:
            Summary of fetched and parsed teams
        """
        results = await fetch_and_store_pokepaste_teams(format_code=format, max_teams=max_teams)

        return {
            "status": "completed",
            "format": format,
            "total_teams": results["total_teams"],
            "successfully_parsed": results["success"],
            "failed_to_fetch": results["failed"],
            "skipped": results["skipped"],
            "sample_success": results["success_details"],
            "sample_failures": results["failed_details"],
        }

    @mcp.tool()
    async def get_pokepaste_data_status(format: str | None = None) -> dict:
        """Get the current status of the pokepaste team database.

        Args:
            format: VGC format code to filter by (e.g., "regf"), None for all formats

        Returns:
            Information about cached tournament team data
        """
        team_count = await get_team_count(format)

        if team_count == 0:
            return {
                "status": "no_data",
                "format": format,
                "message": "No team data cached. Run refresh_pokepaste_data to fetch teams.",
                "total_teams": 0,
            }

        fmt_name = get_format(format).name if format else "All formats"

        return {
            "status": "ready",
            "format": format,
            "total_teams": team_count,
            "source": f"VGC Pastes Repository ({fmt_name})",
        }

    @mcp.tool()
    async def refresh_pokedex_data() -> dict:
        """Fetch Pokedex data from Pokemon Showdown.

        This fetches Pokemon species, moves, abilities, items, learnsets,
        and type chart data from Pokemon Showdown's data files.

        Returns:
            Summary of fetched Pokedex data
        """
        results = await fetch_and_store_pokedex_all()

        return {
            "status": "completed",
            "pokemon_count": results["pokemon"],
            "moves_count": results["moves"],
            "abilities_count": results["abilities"],
            "items_count": results["items"],
            "learnsets_count": results["learnsets"],
            "type_chart_count": results["type_chart"],
            "errors": results.get("errors"),
        }

    @mcp.tool()
    async def get_pokedex_data_status() -> dict:
        """Get the current status of the Pokedex database.

        Returns:
            Information about cached Pokedex data
        """
        stats = await get_pokedex_stats()

        total = sum(stats.values())

        if total == 0:
            return {
                "status": "no_data",
                "message": "No Pokedex data cached. Run refresh_pokedex_data to fetch data.",
                "counts": stats,
            }

        return {
            "status": "ready",
            "source": "Pokemon Showdown",
            "counts": stats,
        }

    @mcp.tool()
    async def list_available_formats() -> dict:
        """List all available VGC formats supported by this server.

        Returns:
            List of format codes with their details
        """
        formats = []
        for code, fmt in FORMATS.items():
            formats.append(
                {
                    "code": code,
                    "name": fmt.name,
                    "smogon_format_id": fmt.smogon_format_id,
                    "available_months": fmt.available_months,
                    "available_elos": fmt.available_elos,
                    "is_current": fmt.is_current,
                    "has_team_data": fmt.sheet_gid is not None,
                }
            )

        current = next((f for f in formats if f["is_current"]), None)

        return {
            "formats": formats,
            "current_format": current["code"] if current else None,
            "default_format": DEFAULT_FORMAT,
        }
