"""Core types and utilities for VGC agent system."""

from vgc_agent.core.events import EventEmitter
from vgc_agent.core.mcp import MCPConnection, MCPConnectionPool, Tool
from vgc_agent.core.types import (
    Event,
    EventType,
    MatchupAnalysis,
    Phase,
    PokemonSet,
    SessionState,
    TeamDesign,
    Weakness,
    WeaknessReport,
)

__all__ = [
    "Event",
    "EventEmitter",
    "EventType",
    "MatchupAnalysis",
    "MCPConnection",
    "MCPConnectionPool",
    "Phase",
    "PokemonSet",
    "SessionState",
    "TeamDesign",
    "Tool",
    "Weakness",
    "WeaknessReport",
]
