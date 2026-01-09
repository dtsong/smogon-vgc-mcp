"""MCP tools for Smogon VGC stats."""

from smogon_vgc_mcp.tools.admin import register_admin_tools
from smogon_vgc_mcp.tools.calculator import register_calculator_tools
from smogon_vgc_mcp.tools.damage import register_damage_tools
from smogon_vgc_mcp.tools.ev_generator import register_ev_generator_tools
from smogon_vgc_mcp.tools.pokedex import register_pokedex_tools
from smogon_vgc_mcp.tools.pokemon import register_pokemon_tools
from smogon_vgc_mcp.tools.rankings import register_rankings_tools
from smogon_vgc_mcp.tools.replay import register_replay_tools
from smogon_vgc_mcp.tools.teambuilding import register_teambuilding_tools
from smogon_vgc_mcp.tools.teams import register_team_tools

__all__ = [
    "register_pokemon_tools",
    "register_rankings_tools",
    "register_teambuilding_tools",
    "register_admin_tools",
    "register_team_tools",
    "register_calculator_tools",
    "register_damage_tools",
    "register_pokedex_tools",
    "register_ev_generator_tools",
    "register_replay_tools",
]
