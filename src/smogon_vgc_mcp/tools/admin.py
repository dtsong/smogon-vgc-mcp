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
from smogon_vgc_mcp.resilience import get_all_circuit_states
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    validate_elo_bracket,
    validate_format_code,
    validate_month,
)


def register_admin_tools(mcp: FastMCP) -> None:
    """Register admin tools with the MCP server."""

    @mcp.tool()
    async def refresh_usage_stats(
        format: str = DEFAULT_FORMAT,
        month: str | None = None,
        elo: int | None = None,
    ) -> dict:
        """Fetch latest VGC usage stats from Smogon and update the local database.

        Run this first to populate Pokemon usage data (usage rates, moves, items, abilities,
        teammates, spreads). Required before using get_pokemon, get_top_pokemon, and other
        usage-based tools.

        Returns: status, format, successful_fetches, failed_fetches, total_pokemon_records,
        details[], errors[].

        Examples:
        - "Refresh the usage stats"
        - "Fetch latest Smogon data for Reg F"

        Args:
            format: VGC format code (e.g., "regf" for Regulation F).
            month: Specific month to refresh (None = all available months).
            elo: Specific ELO bracket (None = all brackets: 0, 1500, 1630, 1760).
        """
        try:
            validate_format_code(format)
            if month is not None:
                month = validate_month(month)
            if elo is not None:
                validate_elo_bracket(elo)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        months = [month] if month else None
        elos = [elo] if elo else None

        results = await fetch_and_store_all(format_code=format, months=months, elos=elos)

        status = "completed" if not results["failed"] else "partial"

        response = {
            "status": status,
            "format": format,
            "successful_fetches": len(results["success"]),
            "failed_fetches": len(results["failed"]),
            "total_pokemon_records": results["total_pokemon"],
            "details": results["success"],
        }

        if results["failed"]:
            response["failed_details"] = results["failed"]
        if results.get("errors"):
            response["error_details"] = results["errors"][:5]
        if results.get("circuit_states"):
            response["circuit_states"] = results["circuit_states"]

        return response

    @mcp.tool()
    async def get_usage_stats_status(format: str | None = None) -> dict:
        """Check if VGC usage stats data is cached and what months/ELOs are available.

        Use this to verify data availability before querying. Shows when data was fetched.
        Run refresh_usage_stats to populate data if status shows no_data.

        Returns: status (ready/no_data), format, total_snapshots, formats_available[],
        by_format{format: {month: [{elo, battles, fetched_at}]}}.

        Examples:
        - "Is the usage data loaded?"
        - "What months of data are available?"

        Args:
            format: VGC format code to filter by (e.g., "regf"). None for all formats.
        """
        try:
            if format:
                validate_format_code(format)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

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
        """Fetch Tera Type and Checks/Counters data from Smogon to augment usage stats.

        Run this AFTER refresh_usage_stats to add Tera type distributions and counter data.
        Required for find_pokemon_by_tera and get_pokemon_counters tools.

        Returns: status, format, successful_fetches, failed_fetches, total_pokemon_updated,
        details[], errors[].

        Examples:
        - "Refresh the moveset data for Tera types"
        - "Fetch checks and counters data"

        Constraints: Requires refresh_usage_stats to be run first.

        Args:
            format: VGC format code (e.g., "regf").
            month: Specific month to refresh (None = all months).
            elo: Specific ELO bracket (None = all brackets).
        """
        try:
            validate_format_code(format)
            if month is not None:
                month = validate_month(month)
            if elo is not None:
                validate_elo_bracket(elo)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        months = [month] if month else None
        elos = [elo] if elo else None

        results = await fetch_and_store_moveset_all(format_code=format, months=months, elos=elos)

        status = "completed" if not results["failed"] else "partial"

        response = {
            "status": status,
            "format": format,
            "successful_fetches": len(results["success"]),
            "failed_fetches": len(results["failed"]),
            "total_pokemon_updated": results["total_pokemon_updated"],
            "details": results["success"],
        }

        if results["failed"]:
            response["failed_details"] = results["failed"]
        if results.get("circuit_states"):
            response["circuit_states"] = results["circuit_states"]

        return response

    @mcp.tool()
    async def refresh_pokepaste_data(
        format: str = DEFAULT_FORMAT,
        max_teams: int | None = None,
    ) -> dict:
        """Fetch tournament teams from VGC Pastes Repository and parse their pokepastes.

        Run this to populate tournament team data (full team details with EVs, moves, items).
        Required for search_tournament_teams, get_tournament_team, and team-related tools.

        Returns: status, format, total_teams, successfully_parsed, failed_to_fetch,
        skipped, sample_success[], sample_failures[].

        Examples:
        - "Fetch tournament team data"
        - "Load pokepaste teams for Reg F"

        Args:
            format: VGC format code (e.g., "regf").
            max_teams: Optional limit for testing (None = all teams).
        """
        try:
            validate_format_code(format)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        results = await fetch_and_store_pokepaste_teams(format_code=format, max_teams=max_teams)

        # Check if the initial sheet fetch failed
        if results.get("error"):
            return {
                "status": "failed",
                "format": format,
                "error": results["error"],
                "circuit_states": results.get("circuit_states"),
            }

        status = "completed" if results["failed"] == 0 else "partial"

        response = {
            "status": status,
            "format": format,
            "total_teams": results["total_teams"],
            "successfully_parsed": results["success"],
            "failed_to_fetch": results["failed"],
            "skipped": results["skipped"],
            "sample_success": results["success_details"],
            "sample_failures": results["failed_details"],
        }

        if results.get("circuit_states"):
            response["circuit_states"] = results["circuit_states"]

        return response

    @mcp.tool()
    async def get_pokepaste_data_status(format: str | None = None) -> dict:
        """Check if tournament team data is cached and how many teams are available.

        Use this to verify team data availability. Run refresh_pokepaste_data to
        populate if status shows no_data.

        Returns: status (ready/no_data), format, total_teams, source.

        Examples:
        - "Is tournament team data loaded?"
        - "How many teams are in the database?"

        Args:
            format: VGC format code to filter by (e.g., "regf"). None for all formats.
        """
        try:
            if format:
                validate_format_code(format)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

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
        """Fetch Pokedex data (Pokemon, moves, abilities, items, learnsets) from Pokemon Showdown.

        Run this to populate static Pokedex data. Required for dex_pokemon, dex_move,
        dex_ability, dex_item, dex_learnset, and type-related tools.

        Returns: status, pokemon_count, moves_count, abilities_count, items_count,
        learnsets_count, type_chart_count, errors[].

        Examples:
        - "Fetch Pokedex data"
        - "Load Pokemon Showdown data"
        """
        results = await fetch_and_store_pokedex_all()

        has_errors = bool(results.get("errors"))
        status = "completed" if not has_errors else "partial"

        response = {
            "status": status,
            "pokemon_count": results["pokemon"],
            "moves_count": results["moves"],
            "abilities_count": results["abilities"],
            "items_count": results["items"],
            "learnsets_count": results["learnsets"],
            "type_chart_count": results["type_chart"],
        }

        if results.get("errors"):
            response["error_details"] = results["errors"]
        if results.get("circuit_states"):
            response["circuit_states"] = results["circuit_states"]

        return response

    @mcp.tool()
    async def get_pokedex_data_status() -> dict:
        """Check if Pokedex data is cached and how many entries are available.

        Use this to verify Pokedex data availability. Run refresh_pokedex_data to
        populate if status shows no_data.

        Returns: status (ready/no_data), source, counts{pokemon, moves, abilities,
        items, learnsets, type_chart}.

        Examples:
        - "Is Pokedex data loaded?"
        - "How many Pokemon are in the database?"
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
        """List all VGC formats supported by this server with their details.

        Use this to see available format codes and their configuration. Format codes
        are used as parameters in most other tools (e.g., "regf" for Regulation F).

        Returns: formats[]{code, name, smogon_format_id, available_months[],
        available_elos[], is_current, has_team_data}, current_format, default_format.

        Examples:
        - "What VGC formats are supported?"
        - "What's the current format code?"
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

    @mcp.tool()
    async def get_service_health() -> dict:
        """Get health status of external services including circuit breaker states.

        Use this to check if external services (Smogon, Pokemon Showdown, Google Sheets,
        Pokepaste) are available or experiencing issues. Shows circuit breaker states
        that protect against cascading failures.

        Returns: services{service_name: {state, failure_count, last_failure, recovery_at}},
        state_descriptions{}.

        States:
        - closed: Service operating normally
        - open: Service unavailable, requests being rejected until recovery_at
        - half_open: Testing if service has recovered

        Examples:
        - "Are external services healthy?"
        - "Why are my refresh requests failing?"
        """
        return {
            "services": get_all_circuit_states(),
            "state_descriptions": {
                "closed": "Service operating normally",
                "open": "Service unavailable, requests being rejected",
                "half_open": "Testing if service has recovered",
            },
        }
