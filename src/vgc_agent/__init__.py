"""VGC Multi-Agent Teambuilder."""

from vgc_agent.core import (
    Event,
    EventEmitter,
    EventType,
    MatchupAnalysis,
    Phase,
    PokemonSet,
    SessionState,
    TeamDesign,
    Weakness,
    WeaknessReport,
)
from vgc_agent.orchestrator import TeambuilderOrchestrator, build_team

__version__ = "0.1.0"

__all__ = [
    "build_team",
    "Event",
    "EventEmitter",
    "EventType",
    "MatchupAnalysis",
    "Phase",
    "PokemonSet",
    "SessionState",
    "TeambuilderOrchestrator",
    "TeamDesign",
    "Weakness",
    "WeaknessReport",
]
