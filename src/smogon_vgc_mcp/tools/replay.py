"""Replay analysis MCP tools."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.fetcher.replay_list import ReplayListError, fetch_public_replay_list
from smogon_vgc_mcp.parser.replay import fetch_and_parse_replay
from smogon_vgc_mcp.utils import (
    ValidationError,
    make_error_response,
    validate_limit,
    validate_replay_url,
)
from smogon_vgc_mcp.utils.validators import validate_showdown_username


def register_replay_tools(mcp: FastMCP) -> None:
    """Register replay analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_replay(url: str) -> dict:
        """Parse a Pokemon Showdown replay and extract teams, leads, and battle result.

        Use this to analyze a specific battle: see what Pokemon each player brought,
        their leads, items/abilities revealed, and who won. For damage-specific analysis,
        use get_damage_observations. For a quick summary, use get_battle_summary.

        Returns: replay_id, format, player1{name, rating, team[], brought[]},
        player2{...}, winner, turn_count.

        Examples:
        - "Analyze this replay: https://replay.pokemonshowdown.com/gen9vgc2026regf-123456"
        - "What teams were used in this battle?"

        Args:
            url: Pokemon Showdown replay URL.
        """
        try:
            url = validate_replay_url(url)
            replay = await fetch_and_parse_replay(url)

            def format_team(team) -> list[dict]:
                return [
                    {
                        "species": mon.species,
                        "item": mon.item,
                        "ability": mon.ability,
                        "tera_type": mon.tera_type,
                        "moves": mon.moves if mon.moves else None,
                    }
                    for mon in team.pokemon
                ]

            return {
                "replay_id": replay.replay_id,
                "format": replay.format,
                "player1": {
                    "name": replay.player1.name,
                    "rating": replay.player1.rating,
                    "team": format_team(replay.player1.team),
                    "brought": replay.player1.brought,
                    "leads": replay.get_lead_pokemon("p1"),
                },
                "player2": {
                    "name": replay.player2.name,
                    "rating": replay.player2.rating,
                    "team": format_team(replay.player2.team),
                    "brought": replay.player2.brought,
                    "leads": replay.get_lead_pokemon("p2"),
                },
                "winner": replay.winner,
                "turn_count": len(replay.turns),
            }

        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)
        except Exception as e:
            return make_error_response(
                f"Failed to parse replay: {e}",
                hint="Check that the replay URL is valid and accessible",
            )

    @mcp.tool()
    async def get_damage_observations(url: str, min_damage: float = 0.0) -> dict:
        """Extract damage events from a replay for spread inference analysis.

        Use this to gather damage data points for EV optimization. Each observation
        shows attacker, defender, move, and damage dealt. Filter by min_damage to
        focus on significant hits. For full replay analysis, use analyze_replay.

        Returns: replay_id, observations[]{turn, attacker, defender, move, damage_percent,
        effectiveness, critical_hit}, observation_count.

        Examples:
        - "What damage rolls happened in this replay?"
        - "Get damage observations over 30% from this battle"

        Args:
            url: Pokemon Showdown replay URL.
            min_damage: Minimum damage percent to include (default 0).
        """
        try:
            url = validate_replay_url(url)
            replay = await fetch_and_parse_replay(url)
            damage_events = replay.get_all_damage_events()

            observations = []
            for event in damage_events:
                if event.damage and event.damage.damage_dealt >= min_damage:
                    observations.append(
                        {
                            "turn": event.turn,
                            "attacker": event.user_species,
                            "attacker_player": event.user,
                            "defender": event.target_species,
                            "defender_player": event.target,
                            "move": event.move,
                            "damage_percent": event.damage.damage_dealt,
                            "effectiveness": event.effectiveness,
                            "critical_hit": event.critical_hit,
                        }
                    )

            return {
                "replay_id": replay.replay_id,
                "format": replay.format,
                "observations": observations,
                "observation_count": len(observations),
            }

        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)
        except Exception as e:
            return make_error_response(
                f"Failed to parse replay: {e}",
                hint="Check that the replay URL is valid and accessible",
            )

    @mcp.tool()
    async def get_battle_summary(url: str) -> dict:
        """Get a concise summary of key battle moments: Tera usage, KOs, and result.

        Use this for a quick overview of what happened in a battle without full
        turn-by-turn details. Shows who Terastallized what and final KO counts.
        For full analysis, use analyze_replay.

        Returns: replay_id, format, players[], winner, turn_count, tera_usage{p1, p2},
        ko_count{p1, p2}, key_kos[].

        Examples:
        - "Summarize this battle"
        - "Who won and what did they Tera?"

        Args:
            url: Pokemon Showdown replay URL.
        """
        try:
            url = validate_replay_url(url)
            replay = await fetch_and_parse_replay(url)

            tera_usage = replay.get_tera_usage()
            ko_count = replay.get_ko_count()

            tera_p1 = None
            tera_p2 = None
            if tera_usage["p1"]:
                tera_p1 = {
                    "species": tera_usage["p1"].species,
                    "tera_type": tera_usage["p1"].tera_type,
                    "turn": tera_usage["p1"].turn,
                }
            if tera_usage["p2"]:
                tera_p2 = {
                    "species": tera_usage["p2"].species,
                    "tera_type": tera_usage["p2"].tera_type,
                    "turn": tera_usage["p2"].turn,
                }

            key_kos = []
            for turn in replay.turns:
                for faint in turn.faints:
                    key_kos.append(
                        {
                            "turn": turn.number,
                            "pokemon": faint.species,
                            "player": faint.player,
                        }
                    )

            return {
                "replay_id": replay.replay_id,
                "format": replay.format,
                "players": [
                    {"name": replay.player1.name, "rating": replay.player1.rating},
                    {"name": replay.player2.name, "rating": replay.player2.rating},
                ],
                "winner": replay.winner,
                "turn_count": len(replay.turns),
                "tera_usage": {
                    "p1": tera_p1,
                    "p2": tera_p2,
                },
                "ko_count": ko_count,
                "key_kos": key_kos,
            }

        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)
        except Exception as e:
            return make_error_response(
                f"Failed to parse replay: {e}",
                hint="Check that the replay URL is valid and accessible",
            )

    @mcp.tool()
    async def fetch_user_public_replays(
        username: str, format: str = "", max_pages: int = 5
    ) -> dict:
        """Fetch a user's public Pokemon Showdown replays.

        Search for replays by username, optionally filtered by format.
        Each page returns up to 50 replays. Use max_pages to control depth.

        Returns: username, format_filter, replays[]{replay_id, url, format, players,
        rating, upload_time, is_private}, total_found, pages_fetched, has_more.

        Examples:
        - "Find all public replays for user Heliosan"
        - "Get Heliosan's gen9vgc2026regf replays"

        Args:
            username: Pokemon Showdown username.
            format: Optional format filter (e.g., "gen9vgc2026regf").
            max_pages: Maximum pages to fetch (1-20, default 5).
        """
        try:
            username = validate_showdown_username(username)
            max_pages = validate_limit(max_pages, max_limit=20)

            result = await fetch_public_replay_list(
                username=username,
                format=format,
                max_pages=max_pages,
            )

            return {
                "username": username,
                "format_filter": format or None,
                "replays": [
                    {
                        "replay_id": r.replay_id,
                        "url": r.url,
                        "format": r.format,
                        "players": r.players,
                        "rating": r.rating,
                        "upload_time": r.upload_time,
                        "is_private": r.is_private,
                    }
                    for r in result.replays
                ],
                "total_found": result.total_fetched,
                "pages_fetched": result.pages_fetched,
                "has_more": result.has_more,
            }

        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)
        except ReplayListError as e:
            return make_error_response(f"Showdown API error: {e}")
        except Exception as e:
            return make_error_response(
                f"Failed to fetch replays: {e}",
                hint="Check that the username is correct",
            )

    @mcp.tool()
    async def fetch_private_replays(
        username: str, password: str, format: str = "", max_pages: int = 5
    ) -> dict:
        """Fetch a user's private Pokemon Showdown replays.

        Requires Showdown login credentials. Credentials are used transiently
        for authentication and never stored or logged. Requires the playwright
        optional dependency.

        Returns: username, format_filter, replays[]{replay_id, url, format, players,
        rating, upload_time, is_private}, total_found, pages_fetched, has_more.

        Examples:
        - "Fetch my private replays (username: X, password: Y)"
        - "Get my private gen9vgc2026regf replays"

        Args:
            username: Pokemon Showdown username.
            password: Pokemon Showdown password (used transiently, never stored).
            format: Optional format filter (e.g., "gen9vgc2026regf").
            max_pages: Maximum pages to fetch (1-20, default 5).
        """
        try:
            from smogon_vgc_mcp.fetcher.replay_list import fetch_private_replay_list
            from smogon_vgc_mcp.fetcher.showdown_auth import (
                AuthenticationError,
                authenticate_showdown,
            )

            username = validate_showdown_username(username)
            max_pages = validate_limit(max_pages, max_limit=20)

            session = await authenticate_showdown(username, password)

            result = await fetch_private_replay_list(
                username=session.username,
                sid_cookie=session.sid_cookie,
                format=format,
                max_pages=max_pages,
            )

            return {
                "username": session.username,
                "format_filter": format or None,
                "replays": [
                    {
                        "replay_id": r.replay_id,
                        "url": r.url,
                        "format": r.format,
                        "players": r.players,
                        "rating": r.rating,
                        "upload_time": r.upload_time,
                        "is_private": r.is_private,
                    }
                    for r in result.replays
                ],
                "total_found": result.total_fetched,
                "pages_fetched": result.pages_fetched,
                "has_more": result.has_more,
            }

        except ImportError as e:
            return make_error_response(
                str(e),
                hint="Install with: pip install smogon-vgc-mcp[browser]"
                " && playwright install chromium",
            )
        except AuthenticationError as e:
            return make_error_response(f"Authentication failed: {e}")
        except ValidationError as e:
            return make_error_response(e.message, hint=e.hint)
        except ReplayListError as e:
            return make_error_response(f"Showdown API error: {e}")
        except Exception as e:
            return make_error_response(
                f"Failed to fetch private replays: {e}",
                hint="Check credentials and ensure playwright is installed",
            )
