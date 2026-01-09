"""Event emitter for observable teambuilding sessions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

from vgc_agent.core.types import Event, EventType, Phase


class EventEmitter:
    """Emits events during teambuilding for UI consumption."""

    def __init__(self):
        self._listeners: list[Callable[[Event], None]] = []
        self._async_listeners: list[Callable[[Event], Any]] = []
        self._queue: asyncio.Queue[Event] | None = None
        self._current_phase: Phase = Phase.INITIALIZED

    def set_phase(self, phase: Phase) -> None:
        self._current_phase = phase

    def add_listener(self, listener: Callable[[Event], None]) -> None:
        self._listeners.append(listener)

    def add_async_listener(self, listener: Callable[[Event], Any]) -> None:
        self._async_listeners.append(listener)

    def remove_listener(self, listener: Callable[[Event], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)
        if listener in self._async_listeners:
            self._async_listeners.remove(listener)

    def enable_queue(self) -> None:
        self._queue = asyncio.Queue()

    async def events(self) -> AsyncIterator[Event]:
        if self._queue is None:
            raise RuntimeError("Call enable_queue() before iterating")
        while True:
            event = await self._queue.get()
            yield event
            if event.type in (EventType.SESSION_COMPLETED, EventType.SESSION_FAILED):
                break

    def emit(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        phase: Phase | None = None,
    ) -> Event:
        event = Event(
            type=event_type,
            timestamp=datetime.now(),
            phase=phase or self._current_phase,
            data=data or {},
        )
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass
        if self._queue is not None:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    async def emit_async(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        phase: Phase | None = None,
    ) -> Event:
        event = self.emit(event_type, data, phase)
        for listener in self._async_listeners:
            try:
                await listener(event)
            except Exception:
                pass
        return event

    def session_started(self, session_id: str, requirements: str) -> Event:
        return self.emit(
            EventType.SESSION_STARTED,
            {"session_id": session_id, "requirements": requirements},
        )

    def session_completed(self, session_id: str, final_team: str) -> Event:
        return self.emit(
            EventType.SESSION_COMPLETED,
            {"session_id": session_id, "final_team": final_team},
        )

    def session_failed(self, session_id: str, error: str) -> Event:
        return self.emit(
            EventType.SESSION_FAILED,
            {"session_id": session_id, "error": error},
        )

    def phase_started(self, phase: Phase, agent: str) -> Event:
        self.set_phase(phase)
        return self.emit(
            EventType.PHASE_STARTED,
            {"phase": phase.value, "agent": agent},
            phase=phase,
        )

    def phase_completed(self, phase: Phase, result_summary: str) -> Event:
        return self.emit(
            EventType.PHASE_COMPLETED,
            {"phase": phase.value, "result_summary": result_summary},
            phase=phase,
        )

    def agent_thinking(self, agent: str, thought: str = "") -> Event:
        return self.emit(EventType.AGENT_THINKING, {"agent": agent, "thought": thought})

    def agent_tool_call(self, agent: str, tool: str, args: dict) -> Event:
        return self.emit(EventType.AGENT_TOOL_CALL, {"agent": agent, "tool": tool, "args": args})

    def agent_tool_result(self, agent: str, tool: str, success: bool, summary: str = "") -> Event:
        return self.emit(
            EventType.AGENT_TOOL_RESULT,
            {"agent": agent, "tool": tool, "success": success, "summary": summary},
        )

    def agent_response(self, agent: str, response_preview: str) -> Event:
        return self.emit(
            EventType.AGENT_RESPONSE,
            {"agent": agent, "response_preview": response_preview[:200]},
        )

    def iteration_started(self, iteration: int, reason: str = "") -> Event:
        return self.emit(
            EventType.ITERATION_STARTED,
            {"iteration": iteration, "reason": reason},
        )

    def iteration_completed(self, iteration: int, continue_iterating: bool) -> Event:
        return self.emit(
            EventType.ITERATION_COMPLETED,
            {"iteration": iteration, "continue_iterating": continue_iterating},
        )

    def team_updated(self, team_summary: list[str]) -> Event:
        return self.emit(EventType.TEAM_UPDATED, {"team_summary": team_summary})

    def weakness_found(self, weakness: str, severity: str) -> Event:
        return self.emit(EventType.WEAKNESS_FOUND, {"weakness": weakness, "severity": severity})
