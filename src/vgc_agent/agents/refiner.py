"""Refiner agent - optimizes EV spreads and finalizes sets."""

from __future__ import annotations

import re

from anthropic import Anthropic

from vgc_agent.agents.base import AgentConfig, BaseAgent
from vgc_agent.core.events import EventEmitter
from vgc_agent.core.mcp import MCPConnection
from vgc_agent.core.types import SessionState, TeamDesign, TokenUsage

REFINER_SYSTEM_PROMPT = """You are the Refiner, optimizing Pokemon sets and EV spreads.

CRITICAL RULES:
1. Call get_pokemon_tournament_spreads for each Pokemon to see real tournament builds
2. Call get_pokemon for ladder spread data as backup
3. Prioritize tournament spreads - these are proven competitive builds
4. Use calculate_damage to verify benchmarks are met
5. Use suggest_ev_spread only when you need custom optimization

Your workflow for each Pokemon:
1. get_pokemon_tournament_spreads(pokemon) - see what top players use
2. get_pokemon(pokemon) - see ladder spreads for comparison
3. Pick the most common spread OR use suggest_ev_spread for custom needs
4. Verify key benchmarks with calculate_damage

Output the final team in Pokemon Showdown format:

# Benchmarks: Survives X from Y, OHKOs Z
Pokemon @ Item
Ability: Ability
Level: 50
Tera Type: Type
EVs: X HP / X Atk / X Def / X SpA / X SpD / X Spe
Nature Nature
- Move 1
- Move 2
- Move 3
- Move 4

Include all 6 Pokemon with complete, legal sets."""

REFINER_TOOLS = [
    "calculate_damage",
    "suggest_ev_spread",
    "get_pokemon",
    "get_pokemon_tournament_spreads",
]


class RefinerAgent(BaseAgent):
    def __init__(
        self,
        mcp: MCPConnection,
        events: EventEmitter,
        anthropic: Anthropic | None = None,
        token_usage: TokenUsage | None = None,
        budget: float | None = None,
    ):
        config = AgentConfig(
            name="Refiner",
            system_prompt=REFINER_SYSTEM_PROMPT,
            tools=REFINER_TOOLS,
            max_tool_calls=40,
        )
        super().__init__(config, mcp, events, anthropic, token_usage, budget)

    async def execute(self, state: SessionState) -> str:
        if not state.team_design:
            raise ValueError("No team design to refine")
        team_summary = self._format_team(state.team_design)
        benchmarks = self._format_benchmarks(state)
        weakness_notes = self._format_weaknesses(state)
        task = (
            f"Create optimized Showdown sets:\n\n{team_summary}\n\n"
            f"Benchmarks:\n{benchmarks}\n\n"
            f"Weakness notes:\n{weakness_notes}\n\n"
            "Output complete Showdown format team."
        )
        response = await self.run(task)
        return self._clean_output(response)

    def _format_team(self, team: TeamDesign) -> str:
        lines = [f"Mode: {team.mode}", f"Game Plan: {team.game_plan}", ""]
        for p in team.pokemon:
            lines.append(
                f"{p.species} ({p.role}): {p.item or '?'} | {p.ability or '?'} | "
                f"Tera: {p.tera_type or '?'}"
            )
            if p.moves:
                lines.append(f"  Moves: {', '.join(p.moves)}")
        return "\n".join(lines)

    def _format_benchmarks(self, state: SessionState) -> str:
        if not state.matchup_analysis or not state.matchup_analysis.recommended_evs:
            return "Use standard competitive spreads."
        lines = []
        for pokemon, rec in state.matchup_analysis.recommended_evs.items():
            lines.append(f"{pokemon}: {rec.get('benchmark', '')}")
        return "\n".join(lines) or "Use standard spreads."

    def _format_weaknesses(self, state: SessionState) -> str:
        if not state.weakness_report:
            return "No specific notes."
        lines = []
        for w in state.weakness_report.weaknesses:
            if w.severity in ("severe", "critical"):
                lines.append(f"- Address {w.threat}: {w.description}")
        return "\n".join(lines) or "No critical weaknesses."

    def _clean_output(self, response: str) -> str:
        lines = response.split("\n")
        team_lines = []
        in_team = False
        for line in lines:
            if re.match(r"^[A-Z][a-zA-Z\-\s]+(@|$)", line.strip()) or line.strip().startswith("#"):
                in_team = True
            if in_team:
                if line.strip().startswith("```") and team_lines:
                    break
                team_lines.append(line)
        if not team_lines:
            return response
        return re.sub(r"```\w*\n?", "", "\n".join(team_lines)).strip()
