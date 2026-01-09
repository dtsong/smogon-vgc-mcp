"""Replay analysis MCP tools."""

from mcp.server.fastmcp import FastMCP

from smogon_vgc_mcp.parser.replay import fetch_and_parse_replay
from smogon_vgc_mcp.utils import ValidationError, make_error_response, validate_replay_url


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
