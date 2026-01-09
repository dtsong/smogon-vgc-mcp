"""Orchestrator for multi-agent VGC teambuilding."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from anthropic import Anthropic

from vgc_agent.agents import ArchitectAgent, CalculatorAgent, CriticAgent, RefinerAgent
from vgc_agent.core import Event, EventEmitter, MCPConnection, Phase, SessionState


class TeambuilderOrchestrator:
    """Orchestrates multi-agent teambuilding pipeline."""

    def __init__(
        self,
        mcp_command: list[str],
        anthropic: Anthropic | None = None,
        max_iterations: int = 3,
    ):
        self.mcp_command = mcp_command
        self.anthropic = anthropic or Anthropic()
        self.max_iterations = max_iterations
        self._mcp: MCPConnection | None = None
        self._events: EventEmitter | None = None
        self._state: SessionState | None = None
        self._architect: ArchitectAgent | None = None
        self._calculator: CalculatorAgent | None = None
        self._critic: CriticAgent | None = None
        self._refiner: RefinerAgent | None = None

    @property
    def events(self) -> EventEmitter:
        if self._events is None:
            raise RuntimeError("Not initialized")
        return self._events

    @property
    def state(self) -> SessionState:
        if self._state is None:
            raise RuntimeError("No active session")
        return self._state

    async def connect(self) -> None:
        self._events = EventEmitter()
        self._mcp = MCPConnection(command=self.mcp_command)
        await self._mcp.connect()
        self._architect = ArchitectAgent(self._mcp, self._events, self.anthropic)
        self._calculator = CalculatorAgent(self._mcp, self._events, self.anthropic)
        self._critic = CriticAgent(self._mcp, self._events, self.anthropic)
        self._refiner = RefinerAgent(self._mcp, self._events, self.anthropic)

    async def disconnect(self) -> None:
        if self._mcp:
            await self._mcp.disconnect()

    async def build_team(self, requirements: str) -> SessionState:
        if self._mcp is None:
            await self.connect()
        session_id = str(uuid.uuid4())[:8]
        self._state = SessionState(
            session_id=session_id,
            requirements=requirements,
            max_iterations=self.max_iterations,
            started_at=datetime.now(),
        )
        self._events.session_started(session_id, requirements)
        try:
            await self._run_pipeline()
            self._state.phase = Phase.COMPLETE
            self._state.completed_at = datetime.now()
            self._events.session_completed(session_id, self._state.final_team or "")
        except Exception as e:
            self._state.phase = Phase.FAILED
            self._state.error = str(e)
            self._state.completed_at = datetime.now()
            self._events.session_failed(session_id, str(e))
            raise
        return self._state

    async def build_team_streaming(self, requirements: str) -> AsyncIterator[Event]:
        if self._mcp is None:
            await self.connect()
        self._events.enable_queue()
        build_task = asyncio.create_task(self.build_team(requirements))
        async for event in self._events.events():
            yield event
        await build_task

    async def _run_pipeline(self) -> None:
        state = self._state
        if state is None:
            raise RuntimeError("No active session")
        if self._architect is None or self._calculator is None:
            raise RuntimeError("Agents not initialized")
        if self._critic is None or self._refiner is None:
            raise RuntimeError("Agents not initialized")

        for iteration in range(1, self.max_iterations + 1):
            state.iteration = iteration
            reason = "Initial design" if iteration == 1 else "Addressing weaknesses"
            self._events.iteration_started(iteration, reason)

            state.phase = Phase.ARCHITECTING
            self._events.phase_started(Phase.ARCHITECTING, "Architect")
            state.team_design = await self._architect.execute(state)
            pokemon_count = len(state.team_design.pokemon)
            self._events.phase_completed(Phase.ARCHITECTING, f"Designed {pokemon_count} Pokemon")

            state.phase = Phase.CALCULATING
            self._events.phase_started(Phase.CALCULATING, "Calculator")
            state.matchup_analysis = await self._calculator.execute(state)
            concern_count = len(state.matchup_analysis.defensive_concerns)
            self._events.phase_completed(Phase.CALCULATING, f"{concern_count} concerns")

            state.phase = Phase.CRITIQUING
            self._events.phase_started(Phase.CRITIQUING, "Critic")
            state.weakness_report = await self._critic.execute(state)
            severity = state.weakness_report.overall_severity
            self._events.phase_completed(Phase.CRITIQUING, f"Severity: {severity}")

            should_iterate = (
                state.weakness_report.iteration_needed
                and state.weakness_report.overall_severity in ("severe", "critical")
                and iteration < self.max_iterations
            )
            self._events.iteration_completed(iteration, should_iterate)
            if not should_iterate:
                break

        state.phase = Phase.REFINING
        self._events.phase_started(Phase.REFINING, "Refiner")
        state.final_team = await self._refiner.execute(state)
        self._events.phase_completed(Phase.REFINING, "Optimized sets")


async def build_team(
    requirements: str,
    mcp_command: list[str] | None = None,
) -> SessionState:
    if mcp_command is None:
        mcp_command = ["uv", "run", "smogon-vgc-mcp"]
    orchestrator = TeambuilderOrchestrator(mcp_command)
    try:
        return await orchestrator.build_team(requirements)
    finally:
        await orchestrator.disconnect()
