"""Calculator agent - validates team through damage calculations."""

from __future__ import annotations

from anthropic import Anthropic

from vgc_agent.agents.base import AgentConfig, BaseAgent
from vgc_agent.core.events import EventEmitter
from vgc_agent.core.mcp import MCPConnection
from vgc_agent.core.types import MatchupAnalysis, SessionState, TeamDesign, TokenUsage

CALCULATOR_SYSTEM_PROMPT = """You are the Calculator, a VGC damage calculation expert.

FORMAT AWARENESS:
- Gen 9 formats: use EVs (0-252 per stat, 508 total) and IVs.
- Champions format: use Stat Points (0-32 per stat, 66 total) instead of EVs/IVs.
Recommend stat investments appropriate to the format. Never mix conventions.

CRITICAL RULES:
1. Call get_top_pokemon first to identify the REAL meta threats
2. Prefer usage data over general knowledge for threat identification
3. Use analyze_matchup for head-to-head comparisons
4. Use get_speed_benchmarks to verify speed tiers

SPARSE-DATA FALLBACK:
If usage data is unavailable, analyze matchups against known meta-relevant Pokemon \
from the Pokedex. State explicitly that calcs are based on dex data, not usage stats.

Your workflow:
1. get_top_pokemon(limit=20) to see what Pokemon are actually common
2. If results are empty/sparse, identify threats via dex_pokemon by stats and typing
3. For each team member, analyze_matchup against top threats
4. Identify OHKOs, 2HKOs, and survival benchmarks
5. Use get_speed_benchmarks to check speed tiers
6. Recommend stat investments (EVs for Gen 9, Stat Points for Champions) based on calc results

Output as JSON:
{
    "pokemon_calcs": {"Pokemon1": {"offensive": [...], "defensive": [...]}},
    "offensive_coverage": ["What the team threatens well"],
    "defensive_concerns": ["What threatens the team"],
    "speed_tiers": [{"pokemon": "Name", "speed": 150, "outspeeds": [], "outsped_by": []}],
    "recommended_evs": {"Pokemon1": {"benchmark": "Survives X",
        "spread": "252 HP / 252 SpD (Gen 9) or 32 HP / 32 SpD (Champions)"}}
}"""

CALCULATOR_TOOLS = [
    "calculate_damage",
    "analyze_matchup",
    "get_pokemon",
    "get_top_pokemon",
    "get_speed_benchmarks",
    "analyze_team_type_coverage",
]


class CalculatorAgent(BaseAgent):
    def __init__(
        self,
        mcp: MCPConnection,
        events: EventEmitter,
        anthropic: Anthropic | None = None,
        token_usage: TokenUsage | None = None,
        budget: float | None = None,
    ):
        config = AgentConfig(
            name="Calculator",
            system_prompt=CALCULATOR_SYSTEM_PROMPT,
            tools=CALCULATOR_TOOLS,
            max_tool_calls=30,
        )
        super().__init__(config, mcp, events, anthropic, token_usage, budget)

    async def execute(self, state: SessionState) -> MatchupAnalysis:
        if not state.team_design:
            raise ValueError("No team design to analyze")
        team_summary = self._format_team(state.team_design)
        task = (
            f"Validate this VGC team:\n\n{team_summary}\n\n"
            "1. Get top 10 meta Pokemon\n"
            "2. Calc offensive matchups\n"
            "3. Calc defensive benchmarks\n"
            "4. Identify speed tiers\n"
            "5. Recommend EVs\n\n"
            "Output as JSON."
        )
        response = await self.run(task)
        return self._parse_response(response)

    def _format_team(self, team: TeamDesign) -> str:
        lines = [f"Mode: {team.mode}", f"Game Plan: {team.game_plan}", "", "Pokemon:"]
        for p in team.pokemon:
            tera_part = f" | Tera: {p.tera_type}" if p.tera_type is not None else ""
            lines.append(f"- {p.species} @ {p.item or '?'} | {p.ability or '?'}{tera_part}")
            if p.moves:
                lines.append(f"  Moves: {', '.join(p.moves)}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> MatchupAnalysis:
        data = self._extract_json(response)
        if not data:
            return MatchupAnalysis()
        return MatchupAnalysis(
            pokemon_calcs=data.get("pokemon_calcs", {}),
            offensive_coverage=data.get("offensive_coverage", []),
            defensive_concerns=data.get("defensive_concerns", []),
            speed_tiers=data.get("speed_tiers", []),
            recommended_evs=data.get("recommended_evs", {}),
        )
