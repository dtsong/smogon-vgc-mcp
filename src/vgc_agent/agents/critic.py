"""Critic agent - identifies team weaknesses and failure modes."""

from __future__ import annotations

from anthropic import Anthropic

from vgc_agent.agents.base import AgentConfig, BaseAgent
from vgc_agent.core.events import EventEmitter
from vgc_agent.core.mcp import MCPConnection
from vgc_agent.core.types import (
    MatchupAnalysis,
    SessionState,
    TeamDesign,
    Weakness,
    WeaknessReport,
)

CRITIC_SYSTEM_PROMPT = """You are the Critic, a VGC expert responsible for stress-testing teams.

Your job is to:
1. Identify Pokemon/strategies that threaten multiple team members
2. Find problematic lead matchups
3. Look for common strategies the team struggles against
4. Check for over-reliance on specific conditions

Severity ratings: minor, moderate, severe, critical

Output as JSON:
{
    "weaknesses": [
        {"threat": "Pokemon", "severity": "severe", "description": "Why",
         "affected_pokemon": [], "suggested_answers": []}
    ],
    "bad_matchups": [{"opponent_lead": [], "problem": "Why", "our_best_lead": []}],
    "overall_severity": "minor/moderate/severe",
    "iteration_needed": true/false,
    "suggestions": ["Improvement suggestions"]
}"""

CRITIC_TOOLS = [
    "get_pokemon_counters",
    "calculate_damage",
    "get_top_pokemon",
    "get_pokemon",
    "find_teams_with_pokemon_core",
]


class CriticAgent(BaseAgent):
    def __init__(
        self,
        mcp: MCPConnection,
        events: EventEmitter,
        anthropic: Anthropic | None = None,
    ):
        config = AgentConfig(
            name="Critic",
            system_prompt=CRITIC_SYSTEM_PROMPT,
            tools=CRITIC_TOOLS,
            max_tool_calls=25,
        )
        super().__init__(config, mcp, events, anthropic)

    async def execute(self, state: SessionState) -> WeaknessReport:
        if not state.team_design:
            raise ValueError("No team design to analyze")
        team_summary = self._format_team(state.team_design)
        calc_summary = self._format_calcs(state.matchup_analysis)
        task = (
            f"Analyze this VGC team for weaknesses:\n\n{team_summary}\n\n"
            f"Calc summary:\n{calc_summary}\n\n"
            "Find threats, bad matchups, and issues. Output as JSON."
        )
        response = await self.run(task)
        report = self._parse_response(response)
        for w in report.weaknesses:
            self.events.weakness_found(w.threat, w.severity)
        return report

    def _format_team(self, team: TeamDesign) -> str:
        lines = [f"Mode: {team.mode}", f"Core: {', '.join(team.core)}", ""]
        for p in team.pokemon:
            lines.append(
                f"- {p.species} @ {p.item or '?'} | {p.ability or '?'} | Tera: {p.tera_type or '?'}"
            )
        return "\n".join(lines)

    def _format_calcs(self, analysis: MatchupAnalysis | None) -> str:
        if not analysis:
            return "No calculations available."
        lines = []
        if analysis.offensive_coverage:
            lines.append(f"Offensive: {', '.join(analysis.offensive_coverage)}")
        if analysis.defensive_concerns:
            lines.append(f"Defensive concerns: {', '.join(analysis.defensive_concerns)}")
        return "\n".join(lines) or "No summary."

    def _parse_response(self, response: str) -> WeaknessReport:
        data = self._extract_json(response)
        if not data:
            return WeaknessReport(overall_severity="unknown")
        weaknesses = [
            Weakness(
                threat=w.get("threat", "?"),
                severity=w.get("severity", "moderate"),
                description=w.get("description", ""),
                affected_pokemon=w.get("affected_pokemon", []),
                suggested_answers=w.get("suggested_answers", []),
            )
            for w in data.get("weaknesses", [])
        ]
        return WeaknessReport(
            weaknesses=weaknesses,
            bad_matchups=data.get("bad_matchups", []),
            overall_severity=data.get("overall_severity", "moderate"),
            iteration_needed=data.get("iteration_needed", False),
            suggestions=data.get("suggestions", []),
        )
