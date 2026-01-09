"""Core types for the VGC multi-agent teambuilder."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Phase(str, Enum):
    """Phases of the teambuilding pipeline."""

    INITIALIZED = "initialized"
    ARCHITECTING = "architecting"
    CALCULATING = "calculating"
    CRITIQUING = "critiquing"
    REFINING = "refining"
    COMPLETE = "complete"
    FAILED = "failed"


class EventType(str, Enum):
    """Types of events emitted during teambuilding."""

    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    AGENT_THINKING = "agent_thinking"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"
    AGENT_RESPONSE = "agent_response"
    ITERATION_STARTED = "iteration_started"
    ITERATION_COMPLETED = "iteration_completed"
    TEAM_UPDATED = "team_updated"
    WEAKNESS_FOUND = "weakness_found"


@dataclass
class Event:
    """An event emitted during teambuilding."""

    type: EventType
    timestamp: datetime
    phase: Phase
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "phase": self.phase.value,
            "data": self.data,
        }


@dataclass
class PokemonSet:
    """A Pokemon set in the team."""

    species: str
    role: str = ""
    item: str | None = None
    ability: str | None = None
    tera_type: str | None = None
    moves: list[str] = field(default_factory=list)
    nature: str | None = None
    evs: dict[str, int] = field(default_factory=dict)
    ivs: dict[str, int] = field(default_factory=dict)
    benchmarks: list[str] = field(default_factory=list)

    def to_showdown(self) -> str:
        """Convert to Pokemon Showdown format."""
        lines = []
        if self.item:
            lines.append(f"{self.species} @ {self.item}")
        else:
            lines.append(self.species)
        if self.ability:
            lines.append(f"Ability: {self.ability}")
        lines.append("Level: 50")
        if self.tera_type:
            lines.append(f"Tera Type: {self.tera_type}")
        if self.evs:
            stat_names = {
                "hp": "HP",
                "atk": "Atk",
                "def": "Def",
                "spa": "SpA",
                "spd": "SpD",
                "spe": "Spe",
            }
            ev_parts = [f"{v} {stat_names[k]}" for k, v in self.evs.items() if v > 0]
            if ev_parts:
                lines.append(f"EVs: {' / '.join(ev_parts)}")
        if self.nature:
            lines.append(f"{self.nature} Nature")
        if self.ivs:
            stat_names = {
                "hp": "HP",
                "atk": "Atk",
                "def": "Def",
                "spa": "SpA",
                "spd": "SpD",
                "spe": "Spe",
            }
            iv_parts = [f"{v} {stat_names[k]}" for k, v in self.ivs.items() if v != 31]
            if iv_parts:
                lines.append(f"IVs: {' / '.join(iv_parts)}")
        for move in self.moves[:4]:
            lines.append(f"- {move}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "species": self.species,
            "role": self.role,
            "item": self.item,
            "ability": self.ability,
            "tera_type": self.tera_type,
            "moves": self.moves,
            "nature": self.nature,
            "evs": self.evs,
            "ivs": self.ivs,
            "benchmarks": self.benchmarks,
        }


@dataclass
class TeamDesign:
    """A team design with 6 Pokemon."""

    pokemon: list[PokemonSet] = field(default_factory=list)
    core: list[str] = field(default_factory=list)
    game_plan: str = ""
    synergies: list[str] = field(default_factory=list)
    mode: str = ""

    def to_showdown(self) -> str:
        return "\n\n".join(p.to_showdown() for p in self.pokemon)

    def to_dict(self) -> dict:
        return {
            "pokemon": [p.to_dict() for p in self.pokemon],
            "core": self.core,
            "game_plan": self.game_plan,
            "synergies": self.synergies,
            "mode": self.mode,
        }


@dataclass
class MatchupAnalysis:
    """Analysis of team matchups from the Calculator."""

    pokemon_calcs: dict[str, dict] = field(default_factory=dict)
    offensive_coverage: list[str] = field(default_factory=list)
    defensive_concerns: list[str] = field(default_factory=list)
    speed_tiers: list[dict] = field(default_factory=list)
    recommended_evs: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pokemon_calcs": self.pokemon_calcs,
            "offensive_coverage": self.offensive_coverage,
            "defensive_concerns": self.defensive_concerns,
            "speed_tiers": self.speed_tiers,
            "recommended_evs": self.recommended_evs,
        }


@dataclass
class Weakness:
    """A weakness identified by the Critic."""

    threat: str
    severity: str
    description: str
    affected_pokemon: list[str] = field(default_factory=list)
    suggested_answers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "threat": self.threat,
            "severity": self.severity,
            "description": self.description,
            "affected_pokemon": self.affected_pokemon,
            "suggested_answers": self.suggested_answers,
        }


@dataclass
class WeaknessReport:
    """Full weakness report from the Critic."""

    weaknesses: list[Weakness] = field(default_factory=list)
    bad_matchups: list[dict] = field(default_factory=list)
    overall_severity: str = "unknown"
    iteration_needed: bool = False
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "weaknesses": [w.to_dict() for w in self.weaknesses],
            "bad_matchups": self.bad_matchups,
            "overall_severity": self.overall_severity,
            "iteration_needed": self.iteration_needed,
            "suggestions": self.suggestions,
        }


@dataclass
class SessionState:
    """Complete state of a teambuilding session."""

    session_id: str
    requirements: str
    phase: Phase = Phase.INITIALIZED
    iteration: int = 0
    max_iterations: int = 3
    team_design: TeamDesign | None = None
    matchup_analysis: MatchupAnalysis | None = None
    weakness_report: WeaknessReport | None = None
    final_team: str | None = None
    events: list[Event] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "requirements": self.requirements,
            "phase": self.phase.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "team_design": self.team_design.to_dict() if self.team_design else None,
            "matchup_analysis": self.matchup_analysis.to_dict() if self.matchup_analysis else None,
            "weakness_report": self.weakness_report.to_dict() if self.weakness_report else None,
            "final_team": self.final_team,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }
