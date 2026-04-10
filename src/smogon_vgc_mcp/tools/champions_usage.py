"""Champions usage MCP tool backed by Pikalytics data."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database.queries import get_champions_usage
from smogon_vgc_mcp.fetcher.pikalytics_champions import ELO_CUTOFFS
from smogon_vgc_mcp.utils import make_error_response, normalize_pokemon_id


def register_champions_usage_tools(mcp: FastMCP) -> None:
    """Register Champions usage tools with the MCP server."""

    @mcp.tool()
    async def get_champions_usage_stats(
        pokemon: str,
        elo_cutoff: str = "0+",
    ) -> dict:
        """Get Pikalytics usage statistics for a Pokemon in Champions format.

        Returns usage %, rank, top moves, items, abilities, and teammates
        for the given ELO cutoff.

        Only "0+" is currently supported; higher-ELO cutoffs will be added
        once Pikalytics exposes them via query parameter.

        Examples:
        - "Incineroar usage stats in Champions"
        - "What moves does Garchomp run in Champions?"

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Garchomp").
            elo_cutoff: ELO cutoff. Currently only "0+" is supported.
        """
        if elo_cutoff not in ELO_CUTOFFS:
            return make_error_response(
                f"Invalid elo_cutoff '{elo_cutoff}'",
                hint=f"Must be one of: {ELO_CUTOFFS}",
            )

        pokemon_id = normalize_pokemon_id(pokemon)
        result = await get_champions_usage(pokemon_id, elo_cutoff=elo_cutoff)
        if result is None:
            return make_error_response(
                f"No Champions usage data for '{pokemon}' at {elo_cutoff}",
                hint="Run the Pikalytics fetcher first, or try a different Pokemon/ELO",
            )
        return result
