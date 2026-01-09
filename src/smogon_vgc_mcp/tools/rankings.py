"""Usage rankings tools for MCP server."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import get_pokemon_stats, get_usage_rankings
from smogon_vgc_mcp.formats import DEFAULT_FORMAT, get_format
from smogon_vgc_mcp.utils import (
    RANKINGS_MAX_LIMIT,
    ValidationError,
    cap_limit,
    make_error_response,
    round_percent,
    validate_elo_bracket,
    validate_format_code,
    validate_limit,
)


def register_rankings_tools(mcp: FastMCP) -> None:
    """Register rankings tools with the MCP server."""

    @mcp.tool()
    async def get_top_pokemon(
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
        elo: int = 1500,
        limit: int = 20,
    ) -> dict:
        """Get top Pokemon by usage rate.

        Args:
            format: VGC format code (e.g., "regf" for Regulation F)
            month: Stats month (format-dependent)
            elo: ELO bracket (0=all, 1500, 1630, 1760)
            limit: Number of Pokemon to return (max 50)

        Returns:
            List of top Pokemon with usage stats
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            limit = validate_limit(limit, max_limit=RANKINGS_MAX_LIMIT)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        limit = cap_limit(limit, RANKINGS_MAX_LIMIT)
        rankings = await get_usage_rankings(format, month, elo, limit)

        if not rankings:
            return make_error_response(
                f"No data found for {format} {month} at ELO {elo}",
                hint="Try running refresh_data first to fetch stats",
            )

        return {
            "format": format,
            "month": month,
            "elo": elo,
            "rankings": [
                {
                    "rank": r.rank,
                    "pokemon": r.pokemon,
                    "usage_percent": r.usage_percent,
                }
                for r in rankings
            ],
        }

    @mcp.tool()
    async def compare_pokemon_usage(
        pokemon: str,
        format: str = DEFAULT_FORMAT,
        elo: int = 1500,
    ) -> dict:
        """Compare a Pokemon's usage across available months for a format.

        Args:
            pokemon: Pokemon name
            format: VGC format code (e.g., "regf")
            elo: ELO bracket to compare

        Returns:
            Usage comparison between months
        """
        try:
            validate_format_code(format)
            validate_elo_bracket(elo)
            if not pokemon or not pokemon.strip():
                raise ValidationError("Pokemon name cannot be empty")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        fmt = get_format(format)
        months = fmt.available_months

        if len(months) < 2:
            return {
                "error": f"Not enough months available for {fmt.name} to compare",
                "available_months": months,
            }

        # Compare first and last available months
        first_month = months[0]
        last_month = months[-1]

        first_stats = await get_pokemon_stats(pokemon, format, first_month, elo)
        last_stats = await get_pokemon_stats(pokemon, format, last_month, elo)

        if not first_stats and not last_stats:
            return {
                "error": f"Pokemon '{pokemon}' not found in either month for {fmt.name}",
            }

        result = {
            "pokemon": pokemon,
            "format": format,
            "elo": elo,
            first_month: None,
            last_month: None,
            "change": None,
        }

        if first_stats:
            result[first_month] = {
                "usage_percent": round_percent(first_stats.usage_percent, 2),
                "raw_count": first_stats.raw_count,
            }

        if last_stats:
            result[last_month] = {
                "usage_percent": round_percent(last_stats.usage_percent, 2),
                "raw_count": last_stats.raw_count,
            }

        if first_stats and last_stats:
            change = last_stats.usage_percent - first_stats.usage_percent
            result["change"] = {
                "usage_percent_change": round_percent(change, 2),
                "direction": "up" if change > 0 else "down" if change < 0 else "stable",
            }

        return result

    @mcp.tool()
    async def compare_elo_brackets(
        pokemon: str,
        format: str = DEFAULT_FORMAT,
        month: str = "2025-12",
    ) -> dict:
        """Compare a Pokemon's usage across different ELO brackets.

        Args:
            pokemon: Pokemon name
            format: VGC format code (e.g., "regf")
            month: Stats month

        Returns:
            Usage comparison across ELO brackets
        """
        try:
            validate_format_code(format)
            if not pokemon or not pokemon.strip():
                raise ValidationError("Pokemon name cannot be empty")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        fmt = get_format(format)
        elos = fmt.available_elos
        results = {}

        for elo in elos:
            stats = await get_pokemon_stats(pokemon, format, month, elo)
            if stats:
                results[str(elo)] = {
                    "usage_percent": round_percent(stats.usage_percent, 2),
                    "raw_count": stats.raw_count,
                }
            else:
                results[str(elo)] = None

        if not any(results.values()):
            return {
                "error": f"Pokemon '{pokemon}' not found in any ELO bracket for {fmt.name} {month}",
            }

        return {
            "pokemon": pokemon,
            "format": format,
            "month": month,
            "by_elo": results,
        }
