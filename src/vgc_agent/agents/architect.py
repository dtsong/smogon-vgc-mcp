"""Architect agent - designs team structure and composition."""

from __future__ import annotations

from anthropic import Anthropic

from vgc_agent.agents.base import AgentConfig, BaseAgent
from vgc_agent.core.events import EventEmitter
from vgc_agent.core.mcp import MCPConnection
from vgc_agent.core.types import PokemonSet, SessionState, TeamDesign, WeaknessReport

ARCHITECT_SYSTEM_PROMPT = """You are the Architect, an expert VGC teambuilder.

Your job is to:
1. Analyze the current meta using usage statistics
2. Identify a strong core (2-3 Pokemon) based on the user's requirements
3. Select complementary teammates that cover weaknesses
4. Define win conditions and game plan

You have access to tools for top Pokemon, Pokemon details, teammates, and tournament teams.

IMPORTANT: Always output your team design as JSON:
{
    "core": ["Pokemon1", "Pokemon2"],
    "mode": "sun/rain/trick room/tailwind/goodstuffs/etc",
    "game_plan": "Description of how the team wins",
    "synergies": ["Synergy 1", "Synergy 2"],
    "pokemon": [
        {
            "species": "Pokemon Name",
            "role": "lead/support/sweeper/tank/restricted/etc",
            "item": "Item Name",
            "ability": "Ability Name",
            "tera_type": "Type",
            "key_moves": ["Move1", "Move2", "Move3", "Move4"],
            "notes": "Why this Pokemon"
        }
    ]
}"""

ARCHITECT_TOOLS = [
    "get_top_pokemon",
    "get_pokemon",
    "get_pokemon_teammates",
    "search_tournament_teams",
    "find_teams_with_pokemon_core",
    "find_pokemon_by_move",
]


class ArchitectAgent(BaseAgent):
    def __init__(
        self,
        mcp: MCPConnection,
        events: EventEmitter,
        anthropic: Anthropic | None = None,
    ):
        config = AgentConfig(
            name="Architect",
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            tools=ARCHITECT_TOOLS,
        )
        super().__init__(config, mcp, events, anthropic)

    async def execute(self, state: SessionState) -> TeamDesign:
        context = ""
        if state.weakness_report and state.iteration > 1:
            context = self._build_iteration_context(state.weakness_report)
        iteration_note = ""
        if state.iteration > 1:
            iteration_note = (
                f"This is iteration {state.iteration}. "
                "Address the weaknesses from the previous iteration."
            )
        task = (
            f"Design a VGC team based on these requirements:\n\n{state.requirements}\n\n"
            f"{iteration_note}\n\nUse tools to research the meta. Output as JSON."
        )
        response = await self.run(task, context)
        return self._parse_response(response)

    def _build_iteration_context(self, weakness_report: WeaknessReport) -> str:
        lines = ["Previous team had these issues:"]
        for w in weakness_report.weaknesses:
            lines.append(f"- {w.threat}: {w.description} ({w.severity})")
        if weakness_report.suggestions:
            lines.append("\nSuggestions:")
            for s in weakness_report.suggestions:
                lines.append(f"- {s}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> TeamDesign:
        data = self._extract_json(response)
        if not data:
            return TeamDesign(game_plan="Could not parse team design")
        team = TeamDesign(
            core=data.get("core", []),
            mode=data.get("mode", ""),
            game_plan=data.get("game_plan", ""),
            synergies=data.get("synergies", []),
        )
        for p in data.get("pokemon", []):
            team.pokemon.append(
                PokemonSet(
                    species=p.get("species", "Unknown"),
                    role=p.get("role", ""),
                    item=p.get("item"),
                    ability=p.get("ability"),
                    tera_type=p.get("tera_type"),
                    moves=p.get("key_moves", []),
                )
            )
        self.events.team_updated([f"{p.species} ({p.role})" for p in team.pokemon])
        return team
