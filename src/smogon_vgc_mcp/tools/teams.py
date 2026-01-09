"""Team lookup tools for MCP server (pokepaste repository)."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.database import (
    get_team,
    get_team_count,
    get_teams_with_core,
    get_tournament_ev_spreads,
    search_teams,
)
from smogon_vgc_mcp.formats import get_format
from smogon_vgc_mcp.utils import cap_limit, make_error_response


def register_team_tools(mcp: FastMCP) -> None:
    """Register team lookup tools with the MCP server."""

    @mcp.tool()
    async def get_tournament_team(team_id: str) -> dict:
        """Get a specific tournament team by ID with full Pokemon details.

        Args:
            team_id: Team ID (e.g., "F123", "F456")

        Returns:
            Full team details including all Pokemon with EVs, moves, items, etc.
        """
        team = await get_team(team_id)

        if not team:
            return make_error_response(
                f"Team '{team_id}' not found",
                hint="Team IDs start with format prefix + number (e.g., F123 for Reg F)",
            )

        return {
            "team_id": team.team_id,
            "description": team.description,
            "owner": team.owner,
            "tournament": team.tournament,
            "rank": team.rank,
            "rental_code": team.rental_code,
            "pokepaste_url": team.pokepaste_url,
            "pokemon": [
                {
                    "slot": p.slot,
                    "pokemon": p.pokemon,
                    "item": p.item,
                    "ability": p.ability,
                    "tera_type": p.tera_type,
                    "nature": p.nature,
                    "evs": f"{p.hp_ev}/{p.atk_ev}/{p.def_ev}/{p.spa_ev}/{p.spd_ev}/{p.spe_ev}",
                    "ivs": f"{p.hp_iv}/{p.atk_iv}/{p.def_iv}/{p.spa_iv}/{p.spd_iv}/{p.spe_iv}",
                    "moves": [p.move1, p.move2, p.move3, p.move4],
                }
                for p in team.pokemon
            ],
        }

    @mcp.tool()
    async def search_tournament_teams(
        pokemon: str | None = None,
        tournament: str | None = None,
        owner: str | None = None,
        format: str | None = None,
        limit: int = 10,
    ) -> dict:
        """Search tournament teams by Pokemon, tournament name, or owner.

        At least one of pokemon, tournament, or owner must be provided.

        Args:
            pokemon: Pokemon name, partial match (e.g., "Incin" matches "Incineroar")
            tournament: Tournament name, partial match (e.g., "Worlds", "Regional")
            owner: Team owner/player name, partial match (e.g., "Wolfe")
            format: VGC format code to filter by (e.g., "regf"). Optional.
            limit: Maximum teams to return (default 10, max 50)

        Returns:
            List of matching teams with Pokemon summaries
        """
        if not pokemon and not tournament and not owner:
            return make_error_response(
                "At least one search parameter required",
                hint="Provide pokemon, tournament, or owner parameter",
            )

        limit = cap_limit(limit)
        teams = await search_teams(
            pokemon=pokemon, tournament=tournament, owner=owner, format_code=format, limit=limit
        )

        if not teams:
            return {
                "query": {
                    "pokemon": pokemon,
                    "tournament": tournament,
                    "owner": owner,
                    "format": format,
                },
                "count": 0,
                "teams": [],
                "message": "No teams found matching criteria",
            }

        return {
            "query": {
                "pokemon": pokemon,
                "tournament": tournament,
                "owner": owner,
                "format": format,
            },
            "count": len(teams),
            "teams": [
                {
                    "team_id": t.team_id,
                    "description": t.description,
                    "owner": t.owner,
                    "tournament": t.tournament,
                    "rank": t.rank,
                    "rental_code": t.rental_code,
                    "pokemon": [p.pokemon for p in t.pokemon],
                }
                for t in teams
            ],
        }

    @mcp.tool()
    async def get_pokemon_tournament_spreads(
        pokemon: str,
        format: str | None = None,
        limit: int = 10,
    ) -> dict:
        """Get EV spreads for a Pokemon from tournament teams.

        This shows how top players actually EV their Pokemon in tournaments,
        which may differ from ladder usage statistics.

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane")
            format: VGC format code to filter by (e.g., "regf")
            limit: Maximum number of spreads to return

        Returns:
            List of EV spreads with frequency and team IDs
        """
        limit = cap_limit(limit)
        spreads = await get_tournament_ev_spreads(pokemon, format, limit)

        if not spreads:
            return {
                "pokemon": pokemon,
                "format": format,
                "count": 0,
                "spreads": [],
                "message": f"No tournament data found for '{pokemon}'",
            }

        return {
            "pokemon": pokemon,
            "format": format,
            "count": len(spreads),
            "spreads": [
                {
                    "nature": s["nature"],
                    "evs": s["evs"],
                    "count": s["count"],
                    "sample_teams": s["team_ids"][:3],
                }
                for s in spreads
            ],
        }

    @mcp.tool()
    async def find_teams_with_pokemon_core(
        pokemon1: str,
        pokemon2: str,
        pokemon3: str | None = None,
        pokemon4: str | None = None,
        format: str | None = None,
        limit: int = 10,
    ) -> dict:
        """Find tournament teams that use a specific Pokemon core/combination.

        Args:
            pokemon1: First Pokemon in the core
            pokemon2: Second Pokemon in the core
            pokemon3: Optional third Pokemon
            pokemon4: Optional fourth Pokemon
            format: VGC format code to filter by (e.g., "regf")
            limit: Maximum number of teams to return

        Returns:
            Teams containing all specified Pokemon
        """
        core = [pokemon1, pokemon2]
        if pokemon3:
            core.append(pokemon3)
        if pokemon4:
            core.append(pokemon4)

        limit = cap_limit(limit)
        teams = await get_teams_with_core(core, format, limit)

        if not teams:
            return {
                "core": core,
                "format": format,
                "count": 0,
                "teams": [],
                "message": f"No teams found using core: {', '.join(core)}",
            }

        return {
            "core": core,
            "format": format,
            "count": len(teams),
            "teams": [
                {
                    "team_id": t.team_id,
                    "description": t.description,
                    "owner": t.owner,
                    "tournament": t.tournament,
                    "rank": t.rank,
                    "rental_code": t.rental_code,
                    "pokemon": [p.pokemon for p in t.pokemon],
                }
                for t in teams
            ],
        }

    @mcp.tool()
    async def get_team_database_stats(format: str | None = None) -> dict:
        """Get statistics about the tournament team database.

        Args:
            format: VGC format code to filter by (e.g., "regf"), None for all formats

        Returns:
            Number of teams and Pokemon entries in the database
        """
        team_count = await get_team_count(format)

        fmt_name = get_format(format).name if format else "All formats"

        return {
            "format": format,
            "total_teams": team_count,
            "source": f"VGC Pastes Repository ({fmt_name})",
            "data_type": "Tournament teams with pokepaste details",
        }
