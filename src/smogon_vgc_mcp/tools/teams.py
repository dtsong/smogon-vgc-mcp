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
from smogon_vgc_mcp.utils import (
    ValidationError,
    cap_limit,
    make_error_response,
    validate_format_code,
    validate_limit,
)


def register_team_tools(mcp: FastMCP) -> None:
    """Register team lookup tools with the MCP server."""

    @mcp.tool()
    async def get_tournament_team(team_id: str) -> dict:
        """Get full details of a specific tournament team by its ID.

        Use this when you have a team ID and want complete team information including
        all Pokemon with EVs, IVs, moves, items, abilities, and Tera types. To find
        team IDs, use search_tournament_teams first.

        Returns: team_id, description, owner, tournament, rank, rental_code, pokepaste_url,
        pokemon[]{slot, pokemon, item, ability, tera_type, nature, evs, ivs, moves[]}.

        Examples:
        - "Show me team F123"
        - "Get the full details of team F456"

        Args:
            team_id: Team ID (e.g., "F123", "G456"). Format prefix + number.
        """
        if not team_id or not team_id.strip():
            return make_error_response(
                "Team ID cannot be empty",
                hint="Team IDs start with format prefix + number (e.g., F123 for Reg F)",
            )

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
        """Search tournament teams by Pokemon, tournament name, or player name.

        Use this to find teams matching criteria. Returns team summaries with IDs.
        For full team details, use get_tournament_team with the team ID.

        Returns: query{pokemon, tournament, owner, format}, count, teams[]{team_id,
        description, owner, tournament, rank, rental_code, pokemon[]}.

        Examples:
        - "Find teams with Incineroar and Flutter Mane"
        - "Show Wolfe's tournament teams"
        - "Find Worlds teams"

        Constraints: At least one of pokemon, tournament, or owner must be provided.

        Args:
            pokemon: Pokemon name, partial match (e.g., "Incin" matches "Incineroar").
            tournament: Tournament name, partial match (e.g., "Worlds", "Regional").
            owner: Player name, partial match (e.g., "Wolfe").
            format: VGC format code to filter by (e.g., "regf").
            limit: Max teams to return (default 10, max 50).
        """
        if not pokemon and not tournament and not owner:
            return make_error_response(
                "At least one search parameter required",
                hint="Provide pokemon, tournament, or owner parameter",
            )

        try:
            if format:
                validate_format_code(format)
            limit = validate_limit(limit)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

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
        """Get EV spreads for a Pokemon used by top players in tournaments.

        Use this to see how competitive players build a Pokemon (may differ from ladder
        stats). For ladder-based spreads, use get_pokemon instead.

        Returns: pokemon, format, count, spreads[]{nature, evs, count, sample_teams[]}.

        Examples:
        - "How do tournament players EV Incineroar?"
        - "What spreads do pros use on Flutter Mane?"

        Args:
            pokemon: Pokemon name (e.g., "Incineroar", "Flutter Mane").
            format: VGC format code to filter by (e.g., "regf").
            limit: Max spreads to return.
        """
        try:
            if not pokemon or not pokemon.strip():
                raise ValidationError("Pokemon name cannot be empty")
            if format:
                validate_format_code(format)
            limit = validate_limit(limit)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

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
        """Find tournament teams that use a specific Pokemon core (2-4 Pokemon together).

        Use this to find real teams built around a specific core. For common teammates
        based on ladder data, use get_pokemon_teammates instead.

        Returns: core[], format, count, teams[]{team_id, description, owner, tournament,
        rank, rental_code, pokemon[]}.

        Examples:
        - "Find teams with Incineroar and Flutter Mane"
        - "Show teams using the Kyogre/Torkoal core"

        Args:
            pokemon1: First Pokemon in the core.
            pokemon2: Second Pokemon in the core.
            pokemon3: Optional third Pokemon.
            pokemon4: Optional fourth Pokemon.
            format: VGC format code to filter by (e.g., "regf").
            limit: Max teams to return.
        """
        try:
            if not pokemon1 or not pokemon1.strip():
                raise ValidationError("pokemon1 cannot be empty")
            if not pokemon2 or not pokemon2.strip():
                raise ValidationError("pokemon2 cannot be empty")
            if format:
                validate_format_code(format)
            limit = validate_limit(limit)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

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
        """Get statistics about the tournament team database (total teams available).

        Use this to check how much team data is available. For detailed status including
        cache state, use get_pokepaste_data_status instead.

        Returns: format, total_teams, source, data_type.

        Examples:
        - "How many tournament teams are in the database?"
        - "How much Reg F team data is available?"

        Args:
            format: VGC format code to filter by (e.g., "regf"). None for all formats.
        """
        try:
            if format:
                validate_format_code(format)
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)

        team_count = await get_team_count(format)

        fmt_name = get_format(format).name if format else "All formats"

        return {
            "format": format,
            "total_teams": team_count,
            "source": f"VGC Pastes Repository ({fmt_name})",
            "data_type": "Tournament teams with pokepaste details",
        }
