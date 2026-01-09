"""Tests for event emitter."""

from vgc_agent.core.events import EventEmitter
from vgc_agent.core.types import EventType, Phase


class TestEventEmitter:
    def test_emit_event(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.emit(EventType.SESSION_STARTED, {"test": "data"})
        assert len(events) == 1
        assert events[0].type == EventType.SESSION_STARTED
        assert events[0].data["test"] == "data"

    def test_set_phase(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.set_phase(Phase.ARCHITECTING)
        emitter.emit(EventType.AGENT_THINKING)
        assert events[0].phase == Phase.ARCHITECTING

    def test_remove_listener(self):
        emitter = EventEmitter()
        events: list = []

        def listener(e):
            events.append(e)

        emitter.add_listener(listener)
        emitter.emit(EventType.SESSION_STARTED)
        assert len(events) == 1
        emitter.remove_listener(listener)
        emitter.emit(EventType.SESSION_STARTED)
        assert len(events) == 1

    def test_convenience_methods(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.session_started("id", "requirements")
        emitter.phase_started(Phase.ARCHITECTING, "Architect")
        emitter.agent_tool_call("Architect", "get_pokemon", {"pokemon": "Incineroar"})
        assert len(events) == 3
        assert events[0].type == EventType.SESSION_STARTED
        assert events[1].type == EventType.PHASE_STARTED
        assert events[2].type == EventType.AGENT_TOOL_CALL

    def test_session_started(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.session_started("abc123", "Build a rain team")
        assert events[0].data["session_id"] == "abc123"
        assert events[0].data["requirements"] == "Build a rain team"

    def test_phase_started_sets_phase(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.phase_started(Phase.CALCULATING, "Calculator")
        assert emitter._current_phase == Phase.CALCULATING
        assert events[0].phase == Phase.CALCULATING

    def test_agent_tool_result(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.agent_tool_result("Architect", "get_pokemon", success=True, summary="Got data")
        assert events[0].type == EventType.AGENT_TOOL_RESULT
        assert events[0].data["success"] is True

    def test_team_updated(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.team_updated(["Incineroar (support)", "Flutter Mane (sweeper)"])
        assert events[0].type == EventType.TEAM_UPDATED
        assert len(events[0].data["team_summary"]) == 2

    def test_weakness_found(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.weakness_found("Urshifu", "severe")
        assert events[0].type == EventType.WEAKNESS_FOUND
        assert events[0].data["weakness"] == "Urshifu"
        assert events[0].data["severity"] == "severe"

    def test_iteration_events(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.iteration_started(1, "Initial design")
        emitter.iteration_completed(1, continue_iterating=True)
        assert events[0].type == EventType.ITERATION_STARTED
        assert events[0].data["iteration"] == 1
        assert events[1].type == EventType.ITERATION_COMPLETED
        assert events[1].data["continue_iterating"] is True

    def test_session_completed(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.session_completed("abc123", "Incineroar @ Safety Goggles\n...")
        assert events[0].type == EventType.SESSION_COMPLETED
        assert "Incineroar" in events[0].data["final_team"]

    def test_session_failed(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.session_failed("abc123", "Connection timeout")
        assert events[0].type == EventType.SESSION_FAILED
        assert events[0].data["error"] == "Connection timeout"

    def test_event_to_dict(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        emitter.emit(EventType.AGENT_THINKING, {"agent": "Architect"})
        d = events[0].to_dict()
        assert d["type"] == "agent_thinking"
        assert "timestamp" in d
        assert d["data"]["agent"] == "Architect"

    def test_listener_exception_does_not_break_emit(self):
        emitter = EventEmitter()
        events = []

        def bad_listener(e):
            raise ValueError("oops")

        emitter.add_listener(bad_listener)
        emitter.add_listener(lambda e: events.append(e))
        emitter.emit(EventType.SESSION_STARTED)
        assert len(events) == 1

    def test_agent_response_truncates_preview(self):
        emitter = EventEmitter()
        events = []
        emitter.add_listener(lambda e: events.append(e))
        long_response = "x" * 500
        emitter.agent_response("Architect", long_response)
        assert len(events[0].data["response_preview"]) == 200
